import base64
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.graphics import GraphicsJobManager, completed_snapshot
from backend.models import GraphicsRequest
from backend.test_scripts import screenplay
from generate_kurzge import build_preview
import generate_kurzge as cli
import image_motion_ai as motion
from render_style import load_render_style


def graphics_script():
    script = screenplay()
    second = copy.deepcopy(script['phases'][0])
    second.update(id=2, name='Mây tiếp tục trôi', duration=2.25)
    second['actions'][0]['end'] = 2.25
    script['phases'][0]['duration'] = script['phases'][0]['actions'][0]['end'] = 1.5
    script['phases'].append(second)
    script['total_duration'] = 3.75
    return script


def phase_svg(phase):
    duration = phase['duration']
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
            '<style>@keyframes drift{from{transform:translateX(0px)}to{transform:translateX(500px)}}'
            f'.motion{{animation:drift {duration}s linear both}}</style>'
            '<g id="artwork"><g transform="translate(400 320)"><g class="motion">'
            '<use href="#CLOUD"/></g></g></g></svg>')


def png_response():
    image = Image.new('RGBA', (32, 32), (147, 215, 213, 255))
    image.putpixel((0, 0), (0, 0, 0, 0))
    data = io.BytesIO()
    image.save(data, format='PNG')
    return json.dumps({'success': True, 'data': [{'b64_json': base64.b64encode(data.getvalue()).decode()}]}).encode()


def seed_script(storage, script=None, script_id='a' * 32):
    directory = storage / 'scripts' / script_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'job.json').write_text(json.dumps({'id': script_id, 'status': 'succeeded'}))
    (directory / 'kich_ban.json').write_text(json.dumps(script or graphics_script(), ensure_ascii=False), encoding='utf-8')
    return script_id


def request(script_id='a' * 32, style='flat'):
    return GraphicsRequest(projectId='project-one', scriptId=script_id,
                           categoryId='all_styles', styleId=style)


class StyleAndPipelineTests(unittest.TestCase):
    def test_cli_style_and_resume_use_same_snapshot_without_api(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cli, 'request_text') as text, patch('image_asset_generator.urlopen') as images:
            source = Path(directory) / 'source.json'
            output = Path(directory) / 'output'
            source.write_text(json.dumps(graphics_script()))
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(['--script', str(source), '--output', str(output), '--style', 'flat-with-black', '--plan-only'])
                cli.main(['--resume', '--output', str(output), '--plan-only'])
            self.assertEqual(json.loads((output / 'render_config.json').read_text())['id'], 'flat-with-black')
            self.assertIn('SELECTED ILLUSTRATION STYLE: flat-with-black', (output / 'prompts' / 'phase_2.txt').read_text())
            text.assert_not_called()
            images.assert_not_called()

    def test_corrupt_cached_phase_is_regenerated_without_recreating_png(self):
        script = graphics_script()
        with tempfile.TemporaryDirectory() as directory, patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())) as images:
            output = Path(directory)
            calls = []

            def draw(prompt):
                phase = json.loads(prompt.split('\nPHASE:\n')[1].split('\nSTYLE:\n')[0])
                calls.append(phase['id'])
                return phase_svg(phase)

            with contextlib.redirect_stdout(io.StringIO()):
                fingerprint = build_preview(script, output, draw, style_context=load_render_style('flat'))
                (output / 'phase_1.svg').write_text(f'<svg data-fingerprint="{fingerprint}" data-renderer="{motion.VERSION}" BROKEN')
                build_preview(script, output, draw, style_context=load_render_style('flat'))
            self.assertEqual(calls, [1, 2, 1])
            self.assertEqual(images.call_count, 1)

    def test_worker_missing_configuration_never_calls_ai(self):
        from backend.graphics_worker import run
        import plant_kurzge as planner
        with tempfile.TemporaryDirectory() as directory, patch.multiple(planner, API_URL=None, API_KEY=None, MODEL=None), patch.object(planner, 'request_text') as text:
            events = io.StringIO()
            with contextlib.redirect_stdout(events):
                run(Path(directory))
            outcome = json.loads(events.getvalue().splitlines()[-1])
            self.assertEqual(outcome['status'], 'failed')
            self.assertIn('Thiếu cấu hình', outcome['error'])
            text.assert_not_called()

    def test_selected_style_reaches_image_and_phase_prompts(self):
        script = graphics_script()
        context = load_render_style('halftone-line')
        image_prompt = motion.asset_prompt(script, motion.image_specs(script)[0], 'default', context)
        phase_prompt = motion.phase_prompt(script, 1, 'library', style_context=context)
        for prompt in (image_prompt, phase_prompt):
            self.assertIn('SELECTED ILLUSTRATION STYLE: halftone-line', prompt)
            self.assertIn(context['skill'], prompt)
            self.assertNotIn('# Illustration: Flat\n', prompt)
        self.assertIn('overriding aesthetic colors/style', image_prompt)
        self.assertEqual(script, graphics_script())

    def test_style_changes_invalidate_image_and_phase_cache_even_with_identical_png(self):
        with tempfile.TemporaryDirectory() as directory, patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())) as images:
            output = Path(directory)
            script = graphics_script()
            first = motion.Renderer(script, output, None, __import__('generate_kurzge').clean_svg,
                                    style_context=load_render_style('flat')).prepare()
            old = first.clean_phase(phase_svg(script['phases'][0]), 1)
            changed = load_render_style('flat')
            changed['skill'] += '\nUpdated style rules.'
            second = motion.Renderer(script, output, None, __import__('generate_kurzge').clean_svg,
                                     style_context=changed).prepare()
            self.assertEqual(images.call_count, 2)
            self.assertNotEqual(first.fingerprint, second.fingerprint)
            with self.assertRaisesRegex(ValueError, 'Cache khác'):
                second.clean_phase(old, 1)

    def test_all_configured_styles_have_guides(self):
        from backend.models import load_style_config
        for category in load_style_config()['categories'].values():
            for style in category['allowed_styles']:
                self.assertTrue(load_render_style(style)['skill'])
        with self.assertRaises(ValueError):
            load_render_style('../flat')


class GraphicsStorageTests(unittest.TestCase):
    def test_creation_recovers_deleted_job_storage_with_selected_style(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(GraphicsJobManager, 'run'):
            storage = Path(directory)
            seed_script(storage)
            manager = GraphicsJobManager(storage)
            try:
                shutil.rmtree(storage / 'graphics')
                job = manager.create(request(style='flat-with-black'))
                self.assertEqual(job['status'], 'queued')
                self.assertEqual(manager.read(job['id'])['config']['styleId'], 'flat-with-black')
                output = storage / 'previews' / job['id']
                self.assertEqual(json.loads((output / 'render_config.json').read_text())['id'], 'flat-with-black')
                self.assertEqual((output / 'kich_ban.json').read_bytes(),
                                 (storage / 'scripts' / ('a' * 32) / 'kich_ban.json').read_bytes())
            finally:
                manager.close()


class GraphicsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        seed_script(self.root)
        self.no_run = patch.object(GraphicsJobManager, 'run', return_value=None)
        self.no_run.start()
        self.addCleanup(self.no_run.stop)
        self.client = TestClient(create_app(self.root))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def create(self, **changes):
        config = request().model_dump()
        config.update(changes)
        return self.client.post('/api/graphics', json=config)

    def test_creation_duplicate_guard_and_immutable_full_source(self):
        before = (self.root / 'scripts' / ('a' * 32) / 'kich_ban.json').read_bytes()
        response = self.create()
        self.assertEqual(response.status_code, 202)
        job = response.json()
        self.assertEqual(job['status'], 'queued')
        self.assertEqual(self.create().json()['id'], job['id'])
        output = self.root / 'previews' / job['id']
        self.assertEqual((output / 'kich_ban.json').read_bytes(), before)
        self.assertEqual(self.client.get('/api/previews/' + job['id']).status_code, 404)
        self.assertEqual(self.client.get('/api/previews/' + job['id'] + '/phase_1.html').status_code, 404)

    def test_rejects_missing_pending_script_and_invalid_category_style(self):
        self.assertEqual(self.create(scriptId='b' * 32).status_code, 409)
        self.assertEqual(self.create(styleId='../flat').status_code, 422)
        self.assertEqual(self.create(categoryId='technology', styleId='flat').status_code, 422)
        path = self.root / 'scripts' / ('a' * 32) / 'job.json'
        path.write_text(json.dumps({'id': 'a' * 32, 'status': 'running'}))
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.client.get('/api/graphics/' + '0' * 32).status_code, 404)

    def test_missing_style_guide_is_an_error_without_flat_fallback(self):
        with patch('backend.graphics.load_render_style', side_effect=ValueError('Không đọc được phong cách')):
            response = self.create()
        self.assertEqual(response.status_code, 503)

    def test_retry_same_inputs_reuses_job_but_new_style_and_success_start_new_job(self):
        manager = self.client.app.state.graphics
        first = self.create().json()
        manager.update(first['id'], status='failed')
        retry = self.create().json()
        self.assertEqual(retry['id'], first['id'])
        self.assertEqual(retry['attempt'], 2)
        manager.update(retry['id'], status='succeeded')
        next_job = self.create().json()
        self.assertNotEqual(next_job['id'], first['id'])
        manager.update(next_job['id'], status='failed')
        changed = self.create(styleId='flat-with-black').json()
        self.assertNotEqual(changed['id'], next_job['id'])

    def test_restart_marks_incomplete_failed_preserving_outputs(self):
        job = self.create().json()
        output = self.root / 'previews' / job['id']
        marker = output / 'phase_1.svg'
        marker.write_text('keep partial work')
        manager = GraphicsJobManager(self.root)
        try:
            self.assertEqual(manager.read(job['id'])['status'], 'failed')
            self.assertEqual(marker.read_text(), 'keep partial work')
        finally:
            manager.close()

    def test_partial_render_is_never_published(self):
        job = self.create().json()
        output = self.root / 'previews' / job['id']
        with patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())):
            with self.assertRaisesRegex(ValueError, 'phase two failed'), contextlib.redirect_stdout(io.StringIO()):
                def draw(prompt):
                    if '"id": 2,' in prompt.split('\nPHASE:\n')[1].split('\nSTYLE:\n')[0]:
                        raise ValueError('phase two failed')
                    return phase_svg(graphics_script()['phases'][0])
                build_preview(graphics_script(), output, draw, style_context=load_render_style('flat'))
        with self.assertRaises((ValueError, OSError)):
            completed_snapshot(self.root, job, 'incomplete')
        self.assertFalse((output / 'snapshot.json').exists())
        self.assertEqual(self.client.get('/api/previews/' + job['id']).status_code, 404)


class ProcessGraphicsTests(unittest.TestCase):
    def test_real_worker_full_roundtrip_failure_and_cached_retry(self):
        calls = {'images': [], 'phases': []}
        fail_phase_two = [True]
        script = graphics_script()

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path == '/generate-image':
                    calls['images'].append(body['prompt'])
                    payload = png_response()
                else:
                    phase = json.loads(body['prompt'].split('\nPHASE:\n')[1].split('\nSTYLE:\n')[0])
                    calls['phases'].append(phase['id'])
                    if phase['id'] == 2 and fail_phase_two[0]:
                        self.send_response(503)
                        self.end_headers()
                        return
                    payload = json.dumps({'success': True, 'result': phase_svg(phase)}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def await_terminal(client, job):
            deadline = time.monotonic() + 20
            while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
                time.sleep(.05)
                job = client.get('/api/graphics/' + job['id']).json()
            return job

        try:
            with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {
                'CODEX_API_URL': f'http://127.0.0.1:{server.server_port}/text',
                'CODEX_API_TOKEN': 'fixture-only', 'CODEX_MODEL': 'fixture',
                'IMAGE_API_BASE_URL': f'http://127.0.0.1:{server.server_port}/generate-image',
                'IMAGE_API_KEY': 'fixture-only', 'IMAGE_MODEL': 'fixture',
            }):
                storage = Path(directory)
                seed_script(storage, script)
                with TestClient(create_app(storage)) as client:
                    job = await_terminal(client, client.post('/api/graphics', json=request().model_dump()).json())
                    self.assertEqual(job['status'], 'failed', job)
                    self.assertIn('HTTP 503', job['error'])
                    self.assertEqual(client.get('/api/previews/' + job['id']).status_code, 404)
                    self.assertTrue((storage / 'previews' / job['id'] / 'phase_1.svg').is_file())
                    fail_phase_two[0] = False
                    retried = await_terminal(client, client.post('/api/graphics', json=request().model_dump()).json())
                    self.assertEqual(retried['id'], job['id'])
                    self.assertEqual(retried['status'], 'succeeded', retried)
                    snapshot = retried['result']
                    self.assertEqual(len(calls['images']), 1)
                    self.assertEqual(calls['phases'], [1, 2, 2])
                    self.assertEqual(snapshot['duration'], 3.75)
                    self.assertEqual([p['id'] for p in snapshot['phases']], ['1', '2'])
                    self.assertEqual(client.get('/api/previews/' + job['id']).json(), snapshot)
                    for phase in snapshot['phases']:
                        page = client.get(phase['url']).text
                        self.assertIn('data:image/png;base64,', page)
                        self.assertIn('window.renderAt', page)
                        self.assertIn('e.source===parent', page)
                    full = json.loads((storage / 'scripts' / ('a' * 32) / 'kich_ban.json').read_text())
                    self.assertEqual(full, script)
                    self.assertIn('SELECTED ILLUSTRATION STYLE: flat', calls['images'][0])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
