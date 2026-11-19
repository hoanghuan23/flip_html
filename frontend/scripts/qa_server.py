"""Local browser QA only. Never contacts the configured external AI service.

Run from the repository root: python3 frontend/scripts/qa_server.py
"""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.test_scripts import screenplay


class FixtureAI(BaseHTTPRequestHandler):
    def do_POST(self):
        prompt = json.loads(self.rfile.read(int(self.headers['Content-Length'])))['prompt']
        time.sleep(1)
        if 'LOI_API' in prompt:
            self.send_response(503)
            self.end_headers()
            return
        if 'Chỉ trả về JSON:' in prompt:
            missing = 'THIEU_DU_KIEN' in prompt
            result = {'valid': not missing, 'reason': 'Cần bổ sung sự kiện và bối cảnh.' if missing else '', 'topic': 'Mưa'}
        else:
            result = screenplay()
            result['phases'] = []
            for index in range(1, 6):
                phase = copy.deepcopy(screenplay()['phases'][0])
                phase.update(id=index, name=f'Cảnh kiểm thử {index}', duration=.5)
                phase['actions'][0]['end'] = .5
                result['phases'].append(phase)
            result['total_duration'] = 2.5
        payload = json.dumps({'success': True, 'result': json.dumps(result, ensure_ascii=False)}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    ai = ThreadingHTTPServer(('127.0.0.1', 0), FixtureAI)
    threading.Thread(target=ai.serve_forever, daemon=True).start()
    os.environ.update(CODEX_API_URL=f'http://127.0.0.1:{ai.server_port}',
                      CODEX_API_TOKEN='local-qa-only', CODEX_MODEL='fixture')
    import uvicorn
    from backend.app import create_app
    try:
        uvicorn.run(create_app(ROOT / 'storage' / 'qa' / 'script-api'), host='127.0.0.1', port=8123)
    finally:
        ai.shutdown()
        ai.server_close()
