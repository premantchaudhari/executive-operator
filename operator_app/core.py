"""Durable single-owner operator. No provider code executes on this host."""
import json
import sqlite3
import time
import uuid
from threading import RLock
from .native_tools import TOOLS,check_arguments

ACTIONS = {'gmail.read': 1, 'gmail.send': 2, 'calendar.cancel': 2, 'browser.inspect': 3, 'sandbox.python': 4}
ACTIONS.update({a:1 if s[1]=='read' else 2 for a,s in TOOLS.items()})
APPROVAL = {'sandbox.python'} | {a for a,s in TOOLS.items() if s[1]=='write'}


def validate(plan):
    if not isinstance(plan, dict) or set(plan) != {'action', 'arguments'}:
        raise ValueError('Plan must contain exactly action and arguments')
    action, args = plan['action'], plan['arguments']
    if not isinstance(action, str) or action not in ACTIONS or not isinstance(args, dict):
        raise ValueError('Unsupported action; payments, OTP and arbitrary browser writes are disabled')
    if action in TOOLS:
        check_arguments(action,args)
        if action!='gmail.send':return plan
    fields = {'gmail.read': {'query'}, 'gmail.send': {'recipient_email', 'subject', 'body'},
              'calendar.cancel': {'event_id'}, 'browser.inspect': {'url'}, 'sandbox.python': {'code'}}[action]
    if set(args) != fields or any(not isinstance(v, str) or not v.strip() or len(v) > 20000 for v in args.values()):
        raise ValueError('Invalid action arguments')
    if action == 'gmail.send':
        from email.utils import parseaddr
        address = args['recipient_email']
        if any(c in args['subject'] for c in '\r\n'):
            raise ValueError('Email subject cannot contain header line breaks')
        if parseaddr(address)[1] != address or '@' not in address or any(c in address for c in '\r\n,;'):
            raise ValueError('Use one plain recipient email address')
    if action == 'browser.inspect':
        from urllib.parse import urlsplit
        u = urlsplit(args['url'])
        if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
            raise ValueError('Browser requires an HTTPS URL without credentials')
    return plan


class Operator:
    def __init__(self, path, provider, tier=4, daily_limit=100):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = RLock()
        self.provider, self.tier, self.daily_limit = provider, tier, daily_limit
        self.db.executescript('''PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        PRAGMA busy_timeout=5000;
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
        request_key TEXT NOT NULL, plan TEXT NOT NULL, status TEXT NOT NULL,
        result TEXT, created REAL NOT NULL, expires REAL NOT NULL,
        UNIQUE(owner, request_key));
        CREATE INDEX IF NOT EXISTS tasks_owner_created ON tasks(owner,created);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, task_id TEXT, event TEXT, at REAL);
        ''')
        # Never retry an ambiguous external write after process death.
        self.db.execute("UPDATE tasks SET status='needs_review' WHERE status IN ('running','queued')")

    def event(self, task, event):
        self.db.execute('INSERT INTO audit(task_id,event,at) VALUES(?,?,?)', (task, event, time.time()))

    def get(self, owner, task_id):
        row = self.db.execute('SELECT * FROM tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
        if not row:
            raise KeyError('Task not found')
        item = dict(row)
        item['plan'] = json.loads(item['plan'])
        item['result'] = json.loads(item['result']) if item['result'] else None
        return item

    def list(self, owner):
        return [self.get(owner, r[0]) for r in self.db.execute('SELECT id FROM tasks WHERE owner=? ORDER BY created DESC LIMIT 100', (owner,)).fetchall()]

    def submit(self, owner, request_key, plan):
        validate(plan)
        if ACTIONS[plan['action']] > self.tier:
            raise ValueError('Action exceeds configured capability tier')
        with self.lock:
            existing = self.db.execute('SELECT id,plan FROM tasks WHERE owner=? AND request_key=?', (owner, request_key)).fetchone()
            if existing:
                if json.loads(existing['plan']) != plan:
                    raise ValueError('Idempotency key already used for another plan')
                return self.get(owner, existing['id'])
            used = self.db.execute('SELECT COUNT(*) FROM tasks WHERE owner=? AND created>?', (owner, time.time()-86400)).fetchone()[0]
            if used >= self.daily_limit:
                raise ValueError('Rolling daily task limit reached')
            task_id = str(uuid.uuid4())
            state = 'awaiting_approval' if plan['action'] in APPROVAL else 'queued'
            self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)', (task_id, owner, request_key, json.dumps(plan), state, None, time.time(), time.time()+900))
            self.event(task_id, state)
            if state == 'queued':
                self._execute(owner, task_id)
            return self.get(owner, task_id)

    def decide(self, owner, task_id, approve):
        with self.lock:
            task = self.get(owner, task_id)
            if task['status'] != 'awaiting_approval':
                raise ValueError('Task is no longer awaiting approval')
            if time.time() > task['expires']:
                self.db.execute("UPDATE tasks SET status='expired' WHERE id=?", (task_id,))
                raise ValueError('Approval expired; submit a fresh task')
            if not approve:
                self.db.execute("UPDATE tasks SET status='rejected' WHERE id=?", (task_id,))
                self.event(task_id, 'rejected')
            else:
                self.event(task_id, 'approved')
                self._execute(owner, task_id)
            return self.get(owner, task_id)

    def _execute(self, owner, task_id):
        task = self.get(owner, task_id)
        self.db.execute("UPDATE tasks SET status='running' WHERE id=?", (task_id,))
        self.event(task_id, 'running')
        try:
            result = self.provider.execute(owner, task['plan'])
            state = 'awaiting_connection' if result.get('connection_required') else ('simulated' if self.provider.demo else 'completed')
        except Exception:
            # External API timeouts may occur after a successful write. Never auto-retry.
            result, state = {'message': 'Provider failed or result uncertain. Check provider before retrying.'}, 'needs_review'
        self.db.execute('UPDATE tasks SET status=?,result=? WHERE id=?', (state, json.dumps(result), task_id))
        self.event(task_id, state)
