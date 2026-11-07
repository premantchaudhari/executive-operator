import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .core import Operator
from .providers import Providers, post
from .orchestration import submit_request


def make_handler(engine, token, owner, telegram_secret='', telegram_owner=''):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log authorization headers or user content.

        def reply(self, code, data, html=False):
            body = data.encode() if html else json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+token)

        def do_GET(self):
            if self.path == '/health':
                return self.reply(200, {'ok': True, 'demo': engine.provider.demo})
            if self.path == '/':
                return self.reply(200, Path(__file__).with_name('dashboard.html').read_text(), True)
            if self.path in ('/manifest.webmanifest', '/sw.js', '/icon.svg'):
                name = self.path[1:]
                content = Path(__file__).with_name(name).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', {'sw.js':'application/javascript', 'icon.svg':'image/svg+xml', 'manifest.webmanifest':'application/manifest+json'}[name])
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            if not self.authorized():
                return self.reply(401, {'error': 'Authentication required'})
            if self.path == '/api/tasks':
                return self.reply(200, {'tasks': engine.list(owner), 'demo': engine.provider.demo, 'tier': engine.tier})
            return self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            try:
                telegram = self.path == '/webhooks/telegram'
                if telegram:
                    if not telegram_secret or not hmac.compare_digest(self.headers.get('X-Telegram-Bot-Api-Secret-Token', ''), telegram_secret):
                        return self.reply(401, {'error': 'Invalid webhook secret'})
                elif not self.authorized():
                    return self.reply(401, {'error': 'Authentication required'})
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536:
                    return self.reply(413, {'error': 'Body must be 1–65536 bytes'})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('Expected JSON object')
                if telegram:
                    msg = data.get('message', {})
                    if str(msg.get('from', {}).get('id')) != telegram_owner or msg.get('chat', {}).get('type') != 'private':
                        return self.reply(403, {'error': 'Owner private chat required'})
                    text = msg.get('text', '')
                    # Approval remains in authenticated dashboard; no approval inferred from chat text.
                    task = submit_request(engine, owner, 'tg:'+str(data['update_id']), {'text': text})
                    if not engine.provider.demo:
                        bot = os.environ['TELEGRAM_BOT_TOKEN']
                        post(f'https://api.telegram.org/bot{bot}/sendMessage', {'chat_id': msg['chat']['id'], 'text': f"Task {task['id']}: {task['status']}. Review details in your Operator dashboard."}, {})
                    return self.reply(200, task)
                if self.path == '/api/tasks':
                    key = self.headers.get('Idempotency-Key', '')
                    if not 1 <= len(key) <= 128:
                        raise ValueError('Idempotency-Key header required (1–128 characters)')
                    return self.reply(201, submit_request(engine, owner, key, data))
                if self.path == '/api/connect':
                    return self.reply(200, engine.provider.connect(owner, data['app']))
                parts = self.path.split('/')
                if len(parts) == 5 and parts[1:3] == ['api', 'tasks'] and parts[4] == 'decision':
                    if type(data.get('approve')) is not bool:
                        raise ValueError('approve must be boolean')
                    return self.reply(200, engine.decide(owner, parts[3], data['approve']))
                return self.reply(404, {'error': 'Not found'})
            except KeyError:
                self.reply(404, {'error': 'Task or required configuration not found'})
            except (ValueError, TypeError, AttributeError) as e:
                self.reply(400, {'error': str(e)[:250]})
            except Exception:
                self.reply(503, {'error': 'Provider unavailable; check configuration. Secrets are never returned.'})
    return Handler


def main():
    token = os.getenv('OPERATOR_API_TOKEN', '')
    if len(token) < 32:
        raise SystemExit('Set OPERATOR_API_TOKEN to a random secret of at least 32 characters')
    demo = os.getenv('OPERATOR_MODE', 'demo') == 'demo'
    if os.getenv('OPERATOR_MODE', 'demo') not in ('demo', 'live'):
        raise SystemExit('OPERATOR_MODE must be demo or live')
    path = os.getenv('OPERATOR_DB', 'data/operator.db')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = Operator(path, Providers(demo), int(os.getenv('OPERATOR_TIER', '4')), int(os.getenv('DAILY_TASK_LIMIT', '100')))
    handler = make_handler(engine, token, os.getenv('OPERATOR_OWNER_ID', 'owner'), os.getenv('TELEGRAM_WEBHOOK_SECRET', ''), os.getenv('TELEGRAM_OWNER_ID', ''))
    server = ThreadingHTTPServer((os.getenv('HOST', '127.0.0.1'), int(os.getenv('PORT', '8080'))), handler)
    print(f"Operator listening on {server.server_address}; mode={'demo' if demo else 'live'}", flush=True)
    server.serve_forever()

if __name__ == '__main__':
    main()
