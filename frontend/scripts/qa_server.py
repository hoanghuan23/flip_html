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
from backend.test_graphics import phase_svg, png_response


class FixtureAI(BaseHTTPRequestHandler):
    fail_phase_two = False
    def do_POST(self):
        prompt = json.loads(self.rfile.read(int(self.headers['Content-Length'])))['prompt']
        time.sleep(1)
        if 'LOI_API' in prompt:
            self.send_response(503)
            self.end_headers()
            return
        if self.path == '/generate-image':
            payload = png_response()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload)
            return
        if '\nPHASE:\n' in prompt:
            phase = json.loads(prompt.split('\nPHASE:\n')[1].split('\nSTYLE:\n')[0])
            if phase['id'] == 2 and FixtureAI.fail_phase_two:
                FixtureAI.fail_phase_two = False
                self.send_response(503)
                self.end_headers()
                return
            result = phase_svg(phase)
        elif 'Chỉ trả về JSON:' in prompt:
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
        payload = json.dumps({'success': True, 'result': result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)}).encode()
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
                      CODEX_API_TOKEN='local-qa-only', CODEX_MODEL='fixture',
                      IMAGE_API_BASE_URL=f'http://127.0.0.1:{ai.server_port}/generate-image',
                      IMAGE_API_KEY='local-qa-only', IMAGE_MODEL='fixture')
    import uvicorn
    from backend.app import create_app
    app = create_app(ROOT / 'storage' / 'qa' / 'script-api')

    @app.post('/_qa/fail-next-phase')
    def fail_next_phase():
        FixtureAI.fail_phase_two = True
        return {'ok': True}

    # Register the QA-only route before the frontend catch-all mount.
    app.router.routes.insert(0, app.router.routes.pop())

    try:
        uvicorn.run(app, host='127.0.0.1', port=8123)
    finally:
        ai.shutdown()
        ai.server_close()
