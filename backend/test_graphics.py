import base64
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
from PIL import Image

from backend.app import create_app
from backend.graphics import GraphicsJobManager
from backend.models import GraphicsRequest
from backend.test_scripts import screenplay
from generate_kurzge import build_preview
import generate_kurzge as cli
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
    contract = json.dumps({'version': 1, 'instances': [
        {'id': 'cloud-instance', 'asset': 'CLOUD', 'space': 'sky', 'mode': 'free',
         'reason': 'A cloud drifting freely through the sky.'}], 'relations': [], 'causality': []})
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
            '<desc id="scene-logic">' + contract + '</desc>'
            '<style>@keyframes drift{from{transform:translateX(0px)}to{transform:translateX(500px)}}'
            f'.motion{{animation:drift {duration}s linear both}}</style>'
            '<g id="artwork"><g transform="translate(400 320)"><g class="motion">'
            '<use id="cloud-instance" href="#CLOUD"/></g></g></g></svg>')

def png_response():
    image = Image.new('RGBA', (32, 32), (147, 215, 213, 255))
    image.putpixel((0, 0), (0, 0, 0, 0))
    data = io.BytesIO()
    image.save(data, format='PNG')
    return json.dumps({'success': True, 'data': [{'b64_json': base64.b64encode(data.getvalue()).decode()}]}).encode()


def seed_script(storage, script=None, script_id='a' * 32, project_id='project-one'):
    directory = storage / 'scripts' / script_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'job.json').write_text(json.dumps({'id': script_id, 'projectId': project_id, 'status': 'succeeded'}))
    (directory / 'kich_ban.json').write_text(json.dumps(script or graphics_script(), ensure_ascii=False), encoding='utf-8')
    return script_id


def request(script_id='a' * 32):
    return GraphicsRequest(projectId='project-one', scriptId=script_id,
                           categoryId='education_entertainment', styleId='character-cartoon')


class StyleAndPipelineTests(unittest.TestCase):
    def test_current_style_guides_both_images_and_animation_and_resumes_from_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            script = graphics_script()
            context = load_render_style('character-cartoon')
            with patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())) as images, \
                    patch.object(cli, 'request_text', side_effect=[phase_svg(p) for p in script['phases']]) as text, \
                    contextlib.redirect_stdout(io.StringIO()):
                first = build_preview(script, output, cli.request_text, style_context=context)
                second = build_preview(script, output, cli.request_text, style_context=context)
            self.assertEqual(first, second)
            self.assertEqual(images.call_count, 1)
            self.assertEqual(text.call_count, 2)
            self.assertIn('Character Cartoon Style', (output / 'prompts/phase_1.txt').read_text())
            for i in (1, 2):
                page = (output / f'phase_{i}.html').read_text()
                self.assertIn('window.renderAt', page)
                self.assertNotIn('program-captions', page)
                self.assertNotIn(script['phases'][i-1]['narration'], page)
                self.assertTrue(json.loads((output / f'phase_{i}.logic.json').read_text())['passed'])

    def test_missing_or_unregistered_style_has_no_fallback(self):
        with self.assertRaises(ValueError):
            load_render_style('flat')
        from render_style import load_render_context
        with self.assertRaises(ValueError):
            load_render_context('character-cartoon', 'all_styles')
        context = load_render_context('character-cartoon', 'education_entertainment')
        self.assertEqual(context['id'], 'character-cartoon')
        self.assertEqual(len(context['character_library']['presets']['presets']), 5)

    def test_untrusted_svg_cannot_add_scripts_external_images_or_event_handlers(self):
        bad = ['<script>alert(1)</script>', '<image href="https://example.com/image.png"/>',
               '<g onclick="alert(1)"/>', '<foreignObject/>']
        for content in bad:
            with self.subTest(content=content), self.assertRaises(ValueError):
                cli.clean_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
                              + content + '</svg>')

    def test_worker_missing_text_configuration_does_not_call_ai(self):
        from backend.graphics_worker import run
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'kich_ban.json').write_text(json.dumps(graphics_script()))
            (output / 'render_config.json').write_text(json.dumps(load_render_style('character-cartoon')))
            protocol = io.StringIO()
            with patch('plant_kurzge.API_KEY', None), patch('backend.graphics_worker.build_preview') as build, \
                    contextlib.redirect_stdout(protocol), contextlib.redirect_stderr(io.StringIO()):
                run(output)
            build.assert_not_called()
            self.assertEqual(json.loads(protocol.getvalue().splitlines()[-1])['status'], 'failed')


class GraphicsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        seed_script(self.root)
        no_run = patch.object(GraphicsJobManager, 'run')
        no_run.start()
        self.addCleanup(no_run.stop)
        self.client = TestClient(create_app(self.root))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.config = request().model_dump()

    def test_creates_job_from_canonical_script_without_changing_the_source(self):
        original = (self.root / 'scripts' / ('a'*32) / 'kich_ban.json').read_bytes()
        response = self.client.post('/api/graphics', json=self.config)
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()
        self.assertEqual(job['workflow'], 'stills-v1')
        self.assertEqual(job['sourceSignature'], json.dumps(job['config'], ensure_ascii=False, separators=(',', ':')))
        self.assertEqual(self.client.get('/api/graphics/' + job['id']).json(), job)
        self.assertEqual(self.client.post('/api/graphics', json=self.config).json()['id'], job['id'])
        self.assertEqual((self.root / 'previews' / job['id'] / 'kich_ban.json').read_bytes(), original)
        self.assertEqual((self.root / 'scripts' / ('a'*32) / 'kich_ban.json').read_bytes(), original)
        self.assertEqual(self.client.post('/api/graphics/' + job['id'] + '/confirm').status_code, 409)
        self.assertEqual(self.client.get('/api/previews/' + job['id']).status_code, 404)

    def test_rejects_missing_foreign_or_unfinished_script_and_wrong_style(self):
        for changes, code in [({'scriptId': 'b'*32}, 409), ({'projectId': 'another-project'}, 409),
                              ({'styleId': 'flat'}, 422), ({'categoryId': 'all_styles'}, 422)]:
            response = self.client.post('/api/graphics', json={**self.config, **changes})
            self.assertEqual(response.status_code, code, response.text)
        source = self.root / 'scripts' / ('a'*32) / 'job.json'
        source.write_text(json.dumps({'id': 'a'*32, 'status': 'running'}))
        self.assertEqual(self.client.post('/api/graphics', json=self.config).status_code, 409)


class ProcessGraphicsTests(unittest.TestCase):
    def test_real_worker_preview_confirmation_narration_animation_and_export_project(self):
        import wave
        from render_hyperframes import collect_scenes, prepare_project
        script = graphics_script()
        script['phases'][0]['voiceover'] = 'Mây trôi.'
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, payload))
                if self.path == '/generate-image':
                    raw = png_response()
                else:
                    phase = script['phases'][0] if 'PHASE 1/' in payload['prompt'] else script['phases'][1]
                    # The narrated scene's real measured duration is one second.
                    raw = json.dumps({'success': True, 'result': phase_svg({**phase, 'duration':
                        1 if phase.get('voiceover') else phase['duration']})}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'provider'
            fake.mkdir()
            (fake / 'vieneu.py').write_text(
                'import wave\nclass Vieneu:\n'
                ' def infer(self, **kwargs): return None\n'
                ' def save(self, audio, path):\n'
                '  with wave.open(path,"wb") as f:\n'
                '   f.setparams((1,2,8000,0,"NONE","not compressed")); f.writeframes(bytes(16000))\n')
            seed_script(root, script)
            original = (root / 'scripts' / ('a'*32) / 'kich_ban.json').read_bytes()
            import os
            with patch.dict(os.environ, {'CODEX_API_URL': f'http://127.0.0.1:{server.server_port}/generate',
                      'IMAGE_API_BASE_URL': f'http://127.0.0.1:{server.server_port}/generate-image',
                      'CODEX_API_TOKEN': 'test-only', 'IMAGE_API_KEY': 'test-only', 'CODEX_MODEL': 'fixture',
                      'PYTHONPATH': str(fake), 'CHROME_PATH': '/usr/bin/google-chrome'}), \
                    TestClient(create_app(root)) as client:
                response = client.post('/api/graphics', json=request().model_dump())
                self.assertEqual(response.status_code, 202, response.text)
                job = response.json()

                def wait_for(terminal):
                    deadline = time.monotonic() + 55
                    current = job
                    while current['status'] in ('queued', 'running') and time.monotonic() < deadline:
                        time.sleep(.05)
                        current = client.get('/api/graphics/' + job['id']).json()
                    if current['status'] != terminal:
                        log = root / 'graphics' / job['id'] / 'worker.log'
                        self.fail(str(current) + '\n' + (log.read_text() if log.exists() else ''))
                    return current

                ready = wait_for('awaiting_confirmation')
                self.assertEqual(len(ready['previews']), 2)
                self.assertEqual(client.get(ready['previews'][0]['url']).status_code, 200)
                output = root / 'previews' / job['id']
                self.assertFalse((output / 'snapshot.json').exists())
                self.assertFalse((output / 'assets/audio').exists())
                self.assertEqual(client.post('/api/graphics/' + job['id'] + '/confirm').status_code, 202)
                final = wait_for('succeeded')
                snapshot = final['result']
                self.assertEqual(len(snapshot['phases']), 2)
                self.assertAlmostEqual(snapshot['phases'][0]['duration'], 1)
                self.assertEqual(client.get(snapshot['phases'][0]['audio']['url']).status_code, 200)
                for phase in snapshot['phases']:
                    self.assertEqual(client.get(phase['url']).status_code, 200)
                scenes = collect_scenes([output])
                project = root / 'hyperframes'
                manifest = prepare_project(scenes, project, 30)
                self.assertEqual(manifest['audio'], 'voiceover')
                self.assertIn('<audio ', (project / 'index.html').read_text())
                self.assertEqual((root / 'scripts' / ('a'*32) / 'kich_ban.json').read_bytes(), original)
                self.assertEqual(len([row for row in requests if row[0] == '/generate-image']), 3)
                self.assertTrue(any('reference_images' in payload for path, payload in requests if path == '/generate-image'))


if __name__ == '__main__':
    unittest.main()
