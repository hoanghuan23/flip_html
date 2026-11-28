import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.graphics import GraphicsJobManager
from backend.graphics_worker import run as run_worker
from backend.still_previews import build_stills, load_stills
from backend.test_graphics import graphics_script, png_response, seed_script
from render_style import load_render_style


class StillGenerationTests(unittest.TestCase):
    def test_progressive_static_images_cache_and_no_animation_or_narration(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            script = graphics_script()
            (output / 'kich_ban.json').write_text(json.dumps(script))
            context = load_render_style('character-cartoon')
            events = []

            def progress(stage, completed, total):
                rows = load_stills(output)
                events.append((stage, completed, total, len(rows)))
                if completed == 1:
                    self.assertFalse((output / 'phase_2.preview.png').exists())
                self.assertFalse(list(output.glob('*.html')))
                self.assertFalse((output / 'assets/audio').exists())

            with patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())) as generate:
                build_stills(script, output, context, progress)
                self.assertEqual(generate.call_count, 2)
                build_stills(script, output, context, lambda *args: None)
                self.assertEqual(generate.call_count, 2)
            self.assertEqual(events, [('stills', 0, 2, 0), ('stills', 1, 2, 1), ('stills', 2, 2, 2)])
            self.assertEqual(len(load_stills(output, complete=True)), 2)
            prompt = (output / 'prompts/phase_1_still.txt').read_text()
            self.assertIn('SELECTED ILLUSTRATION STYLE: character-cartoon', prompt)
            self.assertIn('PHASE TO ILLUSTRATE', prompt)
            self.assertIn('No animation', prompt)

    def test_worker_finishes_stills_without_calling_animation_or_tts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            script = graphics_script()
            script['phases'][0]['voiceover'] = 'Mây trôi trên bầu trời.'
            (output / 'kich_ban.json').write_text(json.dumps(script))
            (output / 'render_config.json').write_text(json.dumps(load_render_style('character-cartoon')))
            protocol = io.StringIO()
            with patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())), \
                    patch('backend.graphics_worker.build_preview') as animate, \
                    patch('backend.narration.prepare_narration') as narrate, \
                    contextlib.redirect_stdout(protocol):
                run_worker(output, 'stills')
            animate.assert_not_called()
            narrate.assert_not_called()
            self.assertEqual(json.loads(protocol.getvalue().splitlines()[-1]), {'status': 'succeeded'})
            self.assertFalse((output / 'snapshot.json').exists())


class StillApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        seed_script(self.root, project_id='still-project')
        self.no_run = patch.object(GraphicsJobManager, 'run')
        self.no_run.start()
        self.addCleanup(self.no_run.stop)
        self.client = TestClient(create_app(self.root))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.manager = self.client.app.state.graphics
        self.config = {'projectId': 'still-project', 'scriptId': 'a' * 32,
                       'categoryId': 'education_entertainment', 'styleId': 'character-cartoon', 'previewOnly': True}
        self.job = self.client.post('/api/graphics', json=self.config).json()
        self.output = self.root / 'previews' / self.job['id']

    def generate(self, fail_second=False):
        def progress(stage, completed, total):
            self.manager.update(self.job['id'], status='running', stage=stage,
                                completed=completed, total=total, previews=load_stills(self.output))
            if completed == 1:
                first = self.client.get(f"/api/graphics/{self.job['id']}/previews/phase_1.png")
                self.assertEqual(first.status_code, 200)
                self.assertEqual(first.headers['content-type'], 'image/png')
                self.assertEqual(self.client.get(f"/api/graphics/{self.job['id']}/previews/phase_2.png").status_code, 404)
                self.assertEqual(self.client.post(f"/api/graphics/{self.job['id']}/confirm").status_code, 409)
                if fail_second:
                    raise ValueError('Interrupted after phase one')
        with patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())):
            build_stills(graphics_script(), self.output, load_render_style('character-cartoon'), progress)
        self.manager.update(self.job['id'], status='awaiting_confirmation', stage='awaiting_confirmation')

    def test_partial_serving_confirmation_and_duplicate_guard(self):
        self.generate()
        self.assertEqual(self.client.get(f"/api/previews/{self.job['id']}/phase_1.html").status_code, 404)
        self.assertEqual(self.client.post('/api/graphics', json=self.config).json()['id'], self.job['id'])
        with patch.object(self.manager.executor, 'submit') as submit:
            first = self.client.post(f"/api/graphics/{self.job['id']}/confirm")
            second = self.client.post(f"/api/graphics/{self.job['id']}/confirm")
            submit.assert_called_once()
        self.assertEqual(first.status_code, 202)
        self.assertTrue(first.json()['confirmed'])
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertEqual(first.json()['sourceSignature'], json.dumps(
            {k: v for k, v in self.config.items() if k != 'previewOnly'}, separators=(',', ':')))
        self.assertFalse((self.output / 'snapshot.json').exists())

    def test_partial_failure_retries_same_job_without_losing_finished_images(self):
        with self.assertRaisesRegex(ValueError, 'Interrupted'):
            self.generate(fail_second=True)
        before = (self.output / 'phase_1.preview.png').read_bytes()
        self.manager.update(self.job['id'], status='failed')
        retry = self.client.post('/api/graphics', json=self.config).json()
        self.assertEqual(retry['id'], self.job['id'])
        self.assertEqual(len(retry['previews']), 1)
        self.assertEqual((self.output / 'phase_1.preview.png').read_bytes(), before)
        self.assertEqual(self.client.post(f"/api/graphics/{self.job['id']}/confirm").status_code, 409)

    def test_waiting_for_confirmation_survives_restart_and_damaged_image_is_rejected(self):
        self.generate()
        restarted = GraphicsJobManager(self.root)
        try:
            self.assertEqual(restarted.read(self.job['id'])['status'], 'awaiting_confirmation')
        finally:
            restarted.close()
        (self.output / 'phase_2.preview.png').write_bytes(b'broken')
        self.assertEqual(self.client.post(f"/api/graphics/{self.job['id']}/confirm").status_code, 409)


if __name__ == '__main__':
    unittest.main()
