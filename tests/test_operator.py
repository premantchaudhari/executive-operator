import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from operator_app.core import Operator, validate
from operator_app.providers import Providers
from operator_app.server import make_handler

SEND = {'action': 'gmail.send', 'arguments': {'recipient_email': 'owner@example.com', 'subject': 'Review', 'body': 'Exact content'}}
READ = {'action': 'gmail.read', 'arguments': {'query': 'is:unread'}}

class RecordingProvider(Providers):
    def __init__(self):
        super().__init__(True)
        self.calls = []
    def execute(self, owner, plan):
        self.calls.append((owner, plan))
        return super().execute(owner, plan)

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = RecordingProvider()
        self.op = Operator(self.tmp.name+'/tasks.db', self.provider)
    def tearDown(self):
        self.op.db.close()
        self.tmp.cleanup()
    def test_read_simulation(self):
        self.assertEqual(self.op.submit('a', '1', READ)['status'], 'simulated')
    def test_write_waits_for_approval(self):
        t = self.op.submit('a', '1', SEND)
        self.assertEqual(t['status'], 'awaiting_approval')
        self.assertEqual(self.provider.calls, [])
        t = self.op.decide('a', t['id'], True)
        self.assertEqual(t['status'], 'simulated')
        self.assertEqual(len(self.provider.calls), 1)
    def test_reject(self):
        t = self.op.submit('a', '1', SEND)
        self.assertEqual(self.op.decide('a', t['id'], False)['status'], 'rejected')
        self.assertFalse(self.provider.calls)
    def test_duplicate_submission(self):
        a = self.op.submit('a', '1', READ)
        b = self.op.submit('a', '1', READ)
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(len(self.provider.calls), 1)
    def test_duplicate_approval(self):
        t = self.op.submit('a', '1', SEND)
        self.op.decide('a', t['id'], True)
        with self.assertRaises(ValueError): self.op.decide('a', t['id'], True)
        self.assertEqual(len(self.provider.calls), 1)
    def test_key_conflict(self):
        self.op.submit('a', '1', READ)
        with self.assertRaises(ValueError): self.op.submit('a', '1', SEND)
    def test_owner_isolation(self):
        t = self.op.submit('a', '1', SEND)
        with self.assertRaises(KeyError): self.op.decide('b', t['id'], True)
        self.assertEqual(self.op.list('b'), [])
    def test_expired_approval(self):
        t = self.op.submit('a', '1', SEND)
        self.op.db.execute('UPDATE tasks SET expires=?', (time.time()-1,))
        with self.assertRaises(ValueError): self.op.decide('a', t['id'], True)
        self.assertEqual(self.op.get('a', t['id'])['status'], 'expired')
        self.assertFalse(self.provider.calls)
    def test_tier_limit(self):
        self.op.tier=1
        with self.assertRaises(ValueError): self.op.submit('a', '1', {'action':'sandbox.python', 'arguments':{'code':'print(1)'}})
    def test_daily_limit(self):
        self.op.daily_limit=1
        self.op.submit('a', '1', READ)
        with self.assertRaises(ValueError): self.op.submit('a', '2', READ)
    def test_unsupported_actions(self):
        for action in ['payment.send', 'otp.verify', 'browser.click', 'shell.exec']:
            with self.assertRaises(ValueError): validate({'action':action, 'arguments':{}})
    def test_invalid_arguments(self):
        with self.assertRaises(ValueError): validate({'action':'gmail.read','arguments':{'query':'x','tool':'PAYMENT'}})
        with self.assertRaises(ValueError): validate({'action':'gmail.send','arguments':{**SEND['arguments'],'recipient_email':'x@example.com\r\nBcc:evil@example.com'}})
    def test_url_validation(self):
        for url in ['http://example.com','https://user:secret@example.com','https://example.com:8080']:
            with self.assertRaises(ValueError): validate({'action':'browser.inspect','arguments':{'url':url}})
    def test_persistence(self):
        t=self.op.submit('a','1',SEND)
        other=Operator(self.tmp.name+'/tasks.db',self.provider)
        self.assertEqual(other.get('a',t['id'])['status'],'awaiting_approval')
        other.db.close()
    def test_ambiguous_failure_not_retried(self):
        def fail(*_): raise TimeoutError()
        self.provider.execute=fail
        t=self.op.submit('a','1',READ)
        self.assertEqual(t['status'],'needs_review')
        self.assertEqual(self.op.submit('a','1',READ)['status'],'needs_review')
    def test_concurrent_approval_executes_once(self):
        t=self.op.submit('a','1',SEND)
        outcomes=[]
        def decide():
            try: outcomes.append(self.op.decide('a',t['id'],True)['status'])
            except ValueError: outcomes.append('blocked')
        threads=[threading.Thread(target=decide) for _ in range(5)]
        for th in threads: th.start()
        for th in threads: th.join()
        self.assertEqual(len(self.provider.calls),1)
        self.assertEqual(outcomes.count('blocked'),4)

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.op=Operator(':memory:',Providers())
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(cls.op,'x'*32,'owner','webhook-secret','123'))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.op.db.close()
    def request(self,path,body=None,auth=True,extra=None):
        headers={'Authorization':'Bearer '+'x'*32} if auth else {}
        headers.update(extra or {})
        req=urllib.request.Request(self.url+path,None if body is None else json.dumps(body).encode(),headers)
        try:
            with urllib.request.urlopen(req) as r: return r.status,r.read()
        except urllib.error.HTTPError as e: return e.code,e.read()
    def test_auth_required(self):
        self.assertEqual(self.request('/api/tasks',auth=False)[0],401)
    def test_dashboard(self):
        status,body=self.request('/',auth=False)
        self.assertEqual(status,200); self.assertIn(b'Executive Operator',body)
    def test_submit_and_decide(self):
        status,body=self.request('/api/tasks',{'plan':SEND},extra={'Idempotency-Key':'http1'})
        self.assertEqual(status,201)
        task=json.loads(body)
        self.assertEqual(self.request('/api/tasks/'+task['id']+'/decision',{'approve':True})[0],200)
    def test_pwa_assets(self):
        for path in ['/manifest.webmanifest', '/sw.js', '/icon.svg']:
            self.assertEqual(self.request(path, auth=False)[0], 200)
        _, manifest = self.request('/manifest.webmanifest', auth=False)
        self.assertEqual(json.loads(manifest)['display'], 'standalone')

    def test_missing_idempotency_key(self):
        self.assertEqual(self.request('/api/tasks',{'plan':READ})[0],400)
    def test_webhook_secret(self):
        self.assertEqual(self.request('/webhooks/telegram',{},False)[0],401)
    def test_webhook_wrong_owner(self):
        self.assertEqual(self.request('/webhooks/telegram',{'message':{'from':{'id':999},'chat':{'type':'private'}}},False,{'X-Telegram-Bot-Api-Secret-Token':'webhook-secret'})[0],403)
    def test_approval_boolean_required(self):
        self.assertEqual(self.request('/api/tasks/unknown/decision',{'approve':'yes'})[0],400)

if __name__=='__main__': unittest.main()
