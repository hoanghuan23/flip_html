import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from fastapi.testclient import TestClient

import plant_kurzge as planner
from backend.app import create_app
from backend.models import ScriptRequest
from backend.script_worker import run as run_worker
from backend.scripts import ScriptJobManager, project_script


def screenplay():
    return {
        'title': 'Vì sao có mưa?', 'render_profile': 'flat', 'total_duration': 7.25,
        'style': {'palette': {'sky': '#ffffff'}, 'font': 'Arial', 'notes': 'Giữ màu nhất quán.'},
        'assets': [{'id': 'CLOUD', 'category': 'object', 'name': 'Mây', 'description': 'Mây trắng.'}],
        'phases': [{
            'id': 1, 'name': 'Mây chuyển động', 'duration': 7.25, 'branch_from': None,
            'narration': 'Không khí ẩm tạo thành mây.', 'caption': 'Những đám mây',
            'description': 'Mây xuất hiện và trôi qua bầu trời.', 'added': True,
            'camera': {'view': 'side', 'motion': 'static', 'detail': 'Góc ngang.'},
            'initial_state': 'Mây ở bên trái.', 'final_state': 'Mây ở bên phải.',
            'actions': [{'target': 'CLOUD', 'type': 'move', 'from': {'x': 200, 'y': 300},
                         'to': {'x': 1200, 'y': 300}, 'start': 0, 'end': 7.25,
                         'easing': 'linear', 'note': 'Mây được gió đưa đi.'}], 'sound': '',
        }],
    }


ACCEPTED = json.dumps({'valid': True, 'reason': '', 'topic': 'Mưa'})


class PlannerTests(unittest.TestCase):
    def test_missing_description_is_repaired_without_second_input_validation(self):
        script = screenplay()
        broken = copy.deepcopy(script)
        del broken['phases'][0]['description']
        self.assertEqual(planner.validate(broken), [])  # Legacy files still render.
        stages = []
        with patch.object(planner, 'request_text', side_effect=[ACCEPTED, json.dumps(broken), json.dumps(script)]) as call:
            self.assertEqual(planner.generate_script('Vì sao có mưa?', on_stage=stages.append), script)
        self.assertEqual(call.call_count, 3)
        self.assertEqual(stages, ['validating', 'generating'])
        self.assertIn('thiếu description', call.call_args.args[0])

    def test_invalid_json_and_exhausted_repairs(self):
        with patch.object(planner, 'request_text', side_effect=[ACCEPTED, 'no json', '{}', '{}']) as call:
            with self.assertRaisesRegex(ValueError, 'không đạt kiểm tra'):
                planner.generate_script('Mưa')
        self.assertEqual(call.call_count, 4)

    def test_rejected_input_never_generates(self):
        rejected = json.dumps({'valid': False, 'reason': 'Cần bổ sung sự kiện cụ thể.', 'topic': ''})
        with patch.object(planner, 'request_text', return_value=rejected) as call:
            with self.assertRaisesRegex(planner.InputRejectedError, 'bổ sung sự kiện'):
                planner.generate_script('Một vài số liệu rời rạc')
        call.assert_called_once()

    def test_ui_compatibility_errors_participate_in_repair(self):
        from backend.scripts import validate_for_ui
        broken = screenplay()
        broken['phases'][0]['duration'] = broken['total_duration'] = 121
        with patch.object(planner, 'request_text', side_effect=[ACCEPTED, json.dumps(broken), json.dumps(screenplay())]) as call:
            result = planner.generate_script('Mưa', extra_validate=validate_for_ui)
        self.assertEqual(result, screenplay())
        self.assertIn('120', call.call_args.args[0])


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'input.txt').write_text('Ý tưởng riêng do người dùng nhập', encoding='utf-8')
        self.settings = patch.multiple(planner, API_URL='http://unused', API_KEY='test-only', MODEL='test')
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def run_events(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_worker(self.root)
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def test_saves_full_script_and_projects_only_readable_fields(self):
        script = screenplay()
        with patch.object(planner, 'request_text', side_effect=[ACCEPTED, json.dumps(script)]) as call:
            events = self.run_events()
        saved = json.loads((self.root / 'kich_ban.json').read_text(encoding='utf-8'))
        self.assertEqual(saved, script)
        self.assertIn('Ý tưởng riêng do người dùng nhập', call.call_args.args[0])
        self.assertEqual(events[-1], {'status': 'succeeded'})
        self.assertEqual([e['stage'] for e in events[:-1]], ['validating', 'generating', 'saving'])
        row = project_script(saved)['scenes'][0]
        self.assertEqual(set(row), {'id', 'name', 'narration', 'description', 'duration'})
        for field in ('name', 'narration', 'description', 'duration'):
            self.assertEqual(row[field], saved['phases'][0][field])
        self.assertEqual(row['duration'], 7.25)
        self.assertNotIn('actions', row)
        self.assertFalse((self.root / 'kich_ban.tmp').exists())

    def test_rejection_has_no_script_file(self):
        with patch.object(planner, 'request_text', return_value=json.dumps({'valid': False, 'reason': 'Thiếu bối cảnh.', 'topic': ''})):
            events = self.run_events()
        self.assertEqual(events[-1]['status'], 'rejected')
        self.assertIn('Thiếu bối cảnh', events[-1]['error'])
        self.assertFalse((self.root / 'kich_ban.json').exists())

    def test_api_error_is_distinct_from_rejection(self):
        from urllib.error import HTTPError
        with patch.object(planner, 'request_text', side_effect=HTTPError('http://unused', 503, 'Unavailable', {}, None)):
            events = self.run_events()
        self.assertEqual(events[-1]['status'], 'failed')
        self.assertIn('HTTP 503', events[-1]['error'])

    def test_missing_configuration(self):
        with patch.object(planner, 'API_KEY', None), patch.object(planner, 'request_text') as call:
            events = self.run_events()
        self.assertEqual(events[-1]['status'], 'failed')
        self.assertIn('Thiếu cấu hình', events[-1]['error'])
        call.assert_not_called()

    def test_disk_error_is_not_success(self):
        original = Path.write_text

        def fail_script(path, *args, **kwargs):
            if path.name == 'kich_ban.tmp':
                raise OSError('disk full')
            return original(path, *args, **kwargs)

        with patch.object(planner, 'request_text', side_effect=[ACCEPTED, json.dumps(screenplay())]), patch.object(Path, 'write_text', fail_script):
            events = self.run_events()
        self.assertEqual(events[-1]['status'], 'failed')
        self.assertIn('lưu file', events[-1]['error'])
        self.assertFalse((self.root / 'kich_ban.json').exists())


class ScriptApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.real_run = ScriptJobManager.run
        self.no_run = patch.object(ScriptJobManager, 'run', return_value=None)
        self.no_run.start()
        self.addCleanup(self.no_run.stop)
        self.client = TestClient(create_app(self.root))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def create(self, content='Vì sao có mưa?'):
        return self.client.post('/api/scripts', json={'projectId': 'my-project', 'content': content})

    def test_async_creation_persistence_and_duplicate_guard(self):
        response = self.create()
        self.assertEqual(response.status_code, 202)
        job = response.json()
        self.assertEqual(job['status'], 'queued')
        self.assertEqual(self.create().json()['id'], job['id'])
        self.assertEqual(self.client.get('/api/scripts/' + job['id']).json(), job)
        self.assertEqual((self.root / 'scripts' / job['id'] / 'input.txt').read_text(), 'Vì sao có mưa?')
        self.assertNotIn('content', job)

    def test_invalid_requests_and_missing_jobs(self):
        self.assertEqual(self.create('   ').status_code, 422)
        for job_id in ('wrong', '0' * 32):
            self.assertEqual(self.client.get('/api/scripts/' + job_id).status_code, 404)

    def test_no_download_api(self):
        job = self.create().json()
        self.assertEqual(self.client.get('/api/scripts/' + job['id'] + '/download').status_code, 404)

    def test_restart_recovery_and_new_attempt_keeps_previous_file(self):
        first = self.create().json()
        old_directory = self.root / 'scripts' / first['id']
        (old_directory / 'kich_ban.json').write_text(json.dumps(screenplay()))
        manager = ScriptJobManager(self.root)
        try:
            self.assertEqual(manager.read(first['id'])['status'], 'failed')
            second = manager.create(ScriptRequest(projectId='my-project', content='Ý tưởng mới'))
            self.assertNotEqual(first['id'], second['id'])
            self.assertTrue((old_directory / 'kich_ban.json').exists())
        finally:
            manager.close()

    def test_worker_cannot_report_success_without_saved_file(self):
        job = self.create().json()
        process = unittest.mock.Mock()
        process.stdout = io.StringIO('{"status":"succeeded"}\n')
        process.wait.return_value = 0
        process.poll.return_value = 0
        with patch('backend.scripts.subprocess.Popen', return_value=process):
            self.real_run(self.client.app.state.scripts, job['id'])
        final = self.client.get('/api/scripts/' + job['id']).json()
        self.assertEqual(final['status'], 'failed')
        self.assertIsNone(final['result'])


class ProcessIntegrationTests(unittest.TestCase):
    def test_real_subprocess_roundtrip_against_local_ai_fixture(self):
        requests = []
        replies = [ACCEPTED, json.dumps(screenplay())]

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                payload = json.dumps({'success': True, 'result': replies.pop(0)}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {
                'CODEX_API_URL': f'http://127.0.0.1:{server.server_port}',
                'CODEX_API_TOKEN': 'local-test-only', 'CODEX_MODEL': 'test-model',
            }):
                root = Path(directory)
                with TestClient(create_app(root)) as client:
                    job = client.post('/api/scripts', json={'projectId': 'process-test', 'content': 'Vì sao có mưa?'}).json()
                    deadline = time.monotonic() + 15
                    while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
                        time.sleep(.05)
                        job = client.get('/api/scripts/' + job['id']).json()
                    self.assertEqual(job['status'], 'succeeded', job)
                    saved = json.loads((root / 'scripts' / job['id'] / 'kich_ban.json').read_text())
                    self.assertEqual(saved, screenplay())
                    self.assertEqual(job['result'], project_script(saved))
                    self.assertEqual(len(requests), 2)
                    self.assertEqual(requests[1]['model'], 'test-model')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
