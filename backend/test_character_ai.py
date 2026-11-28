import base64
import io
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend import character_ai as ai


class CharacterAiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.asset_root = self.root / 'parts'
        self.asset_root.mkdir()
        buffer = io.BytesIO()
        Image.new('RGBA', (2, 2), (255, 0, 0, 255)).save(buffer, format='PNG')
        self.png = buffer.getvalue()
        self.parts = {}
        for slot in ai.SLOTS:
            name = slot + '.png'
            (self.asset_root / name).write_bytes(self.png)
            self.parts[slot] = name
        patcher = patch.object(ai, 'ASSET_ROOT', self.asset_root)
        patcher.start()
        self.addCleanup(patcher.stop)
        env = patch.dict(os.environ, {'CODEX_API_TOKEN': 'private-test-key',
                                    'CODEX_MODEL': 'test-model',
                                    'CODEX_IMAGE_API_URL': 'http://codex.test/generate-image'})
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(create_app(self.root / 'storage'))
        self.addCleanup(self.client.close)
        self.prompt = re.search(r'<script id="character-prompt" type="text/plain">(.*?)</script>',
                                (ai.ROOT / 'character_ai.html').read_text(), re.S).group(1).strip()
        self.payload = {'config': {'description': 'Giữ nét tinh nghịch', 'parts': self.parts},
                        'prompt': self.prompt}

    def prepare(self, payload=None):
        return self.client.post('/api/character-ai/prepare', json={'prompt': self.prompt, **(payload or self.payload)})

    def test_page_and_defaults_hide_key(self):
        for path in ('/character-ai', '/character_ai.html'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/html', response.headers['content-type'])
            self.assertIn('Tạo nhân vật', response.text)
        response = self.client.get('/api/character-ai/config')
        self.assertEqual(set(response.json()), {'config'})
        self.assertNotIn('private-test-key', response.text)
        self.assertIn('front_happy', response.json()['config']['presets'])

    def test_html_alias_redirects_to_single_page(self):
        response = self.client.get('/character_ai.html', follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers['location'], '/character-ai')

    def test_prepares_without_asset_catalog_or_rig_coordinates(self):
        self.parts.update(shoulder_L='not-needed.png', shoulder_R='not-needed.png')
        response = self.prepare()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual([p['slot'] for p in data['parts']], list(ai.SLOTS))
        self.assertEqual(data['ignored_parts'], ['shoulder_L', 'shoulder_R'])
        for image in data['reference_images']:
            self.assertEqual(base64.b64decode(image.split(',', 1)[1]), self.png)
        self.assertIn('Image 1: head', data['prompt'])
        self.assertIn('exact facial expression', data['prompt'])
        self.assertIn('transparent_background=true', data['prompt'])
        self.assertEqual(data['prompt'], self.prompt)

    def test_accepts_parts_map_and_full_presets_file(self):
        for config in (self.parts, {'default_preset': 'custom', 'presets': {
                'custom': {'parts': self.parts}}}):
            with self.subTest(config=config):
                self.assertEqual(self.prepare({'config': config}).status_code, 200)

    def test_missing_invalid_and_outside_assets_fail_before_network(self):
        for parts in ({}, {**self.parts, 'head': '../outside.png'},
                      {**self.parts, 'head': '/etc/passwd'},
                      {**self.parts, 'head': 'missing.png'},
                      {**self.parts, 'head': 10}, {**self.parts, 'unknown': 'head.png'}):
            with self.subTest(parts=parts):
                self.assertEqual(self.prepare({'config': {'parts': parts}}).status_code, 422)
        (self.root / 'outside.png').write_bytes(self.png)
        (self.asset_root / 'escape.png').symlink_to(self.root / 'outside.png')
        self.assertEqual(self.prepare({'config': {'parts': {**self.parts, 'head': 'escape.png'}}}).status_code, 422)
        self.assertEqual(self.prepare({'config': {'presets': {}, 'default_preset': []}}).status_code, 422)
        self.assertEqual(self.prepare({**self.payload, 'prompt': '   '}).status_code, 422)
        with patch.object(ai, 'MAX_BYTES', len(self.png) * 2):
            self.assertEqual(self.prepare().status_code, 422)

    def test_asset_route_serves_only_allowed_pngs(self):
        response = self.client.get('/api/character-ai/assets/head.png')
        self.assertEqual(response.content, self.png)
        self.assertEqual(response.headers['content-type'], 'image/png')
        (self.asset_root / 'bad.txt').write_text('private')
        self.assertEqual(self.client.get('/api/character-ai/assets/bad.txt').status_code, 404)

    def mock_upstream(self, handler):
        client_class = httpx.AsyncClient
        patcher = patch.object(ai.httpx, 'AsyncClient', side_effect=lambda **kwargs:
                               client_class(transport=httpx.MockTransport(handler), **kwargs))
        patcher.start()
        self.addCleanup(patcher.stop)

    def success(self):
        return {'success': True, 'output_format': 'png', 'usage': {'input_tokens': 50},
                'data': [{'b64_json': base64.b64encode(self.png).decode()}]}

    def test_sends_only_generic_prompt_model_and_images_to_codex(self):
        calls = []
        def upstream(request):
            calls.append(request)
            return httpx.Response(200, json=self.success())
        self.mock_upstream(upstream)
        response = self.client.post('/api/character-ai/generate', json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual({key: response.json()[key] for key in self.success()}, self.success())
        self.assertIsNotNone(response.json()['saved'])
        self.assertIsNone(response.json()['save_error'])
        self.assertEqual(str(calls[0].url), 'http://codex.test/generate-image')
        self.assertEqual(calls[0].headers['X-API-Key'], 'private-test-key')
        data = json.loads(calls[0].content)
        self.assertEqual(set(data), {'model', 'prompt', 'reference_images'})
        self.assertEqual(len(data['reference_images']), 5)
        self.assertEqual(data['model'], 'test-model')
        self.assertNotIn('private-test-key', response.text)

    def test_saved_png_and_json_survive_restart_without_ai_or_source_assets(self):
        calls = []
        def upstream(request):
            calls.append(request)
            return httpx.Response(200, json=self.success())
        self.mock_upstream(upstream)
        self.assertEqual(self.client.get('/api/character-ai/saved').json(), {'characters': []})
        response = self.client.post('/api/character-ai/generate', json=self.payload)
        saved = response.json()['saved']
        self.assertEqual(saved['input'], {**self.payload, 'preset_id': None})
        self.assertEqual(saved['kind'], 'character-ai-result')
        self.assertEqual(saved['model'], 'test-model')
        directory = self.root / 'storage/character_ai' / saved['id']
        self.assertEqual((directory / 'character.png').read_bytes(), self.png)
        self.assertEqual(json.loads((directory / 'character.json').read_text()), saved)
        for image in self.asset_root.glob('*.png'):
            image.unlink()
        with TestClient(create_app(self.root / 'storage')) as reopened:
            with patch.dict(os.environ, {'CODEX_API_TOKEN': '', 'CODEX_MODEL': ''}):
                listing = reopened.get('/api/character-ai/saved').json()['characters']
                self.assertEqual([item['id'] for item in listing], [saved['id']])
                self.assertEqual(reopened.get('/api/character-ai/saved/' + saved['id']).json(), saved)
                self.assertEqual(reopened.get(saved['image_url']).content, self.png)
                config = reopened.get(saved['config_url'])
                self.assertEqual(config.json(), saved)
                self.assertIn('attachment', config.headers['content-disposition'])
                self.assertNotIn('private-test-key', config.text)
                self.assertNotIn('codex.test', config.text)
        self.assertEqual(len(calls), 1)

    def test_separate_generations_keep_both_results(self):
        self.mock_upstream(lambda request: httpx.Response(200, json=self.success()))
        saved = [self.client.post('/api/character-ai/generate', json=self.payload).json()['saved']
                 for _ in range(2)]
        self.assertNotEqual(saved[0]['id'], saved[1]['id'])
        listing = self.client.get('/api/character-ai/saved').json()['characters']
        self.assertEqual([item['id'] for item in listing], [saved[1]['id'], saved[0]['id']])
        self.assertEqual(self.client.get(saved[0]['image_url']).content, self.png)

    def test_save_failure_preserves_generated_png_and_reports_error(self):
        self.mock_upstream(lambda request: httpx.Response(200, json=self.success()))
        with patch.object(ai, 'save_character', side_effect=OSError('Disk full')):
            response = self.client.post('/api/character-ai/generate', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], self.success()['data'])
        self.assertIsNone(response.json()['saved'])
        self.assertIn('không lưu được', response.json()['save_error'])

    def test_saved_routes_reject_unknown_ids_and_unrelated_files(self):
        self.mock_upstream(lambda request: httpx.Response(200, json=self.success()))
        saved = self.client.post('/api/character-ai/generate', json=self.payload).json()['saved']
        for suffix in ('not-an-id', '0' * 32, saved['id'] + '/secret.txt'):
            self.assertEqual(self.client.get('/api/character-ai/saved/' + suffix).status_code, 404)
        directory = self.root / 'storage/character_ai' / saved['id']
        (directory / 'character.png').unlink()
        (directory / 'character.png').symlink_to(self.root / 'outside.png')
        (self.root / 'outside.png').write_bytes(self.png)
        self.assertEqual(self.client.get(saved['image_url']).status_code, 404)

    def test_connection_settings_come_only_from_env(self):
        for key, value in [('endpoint', 'http://other.test'), ('model', 'other-model'), ('api_key', 'other-key')]:
            with self.subTest(key=key):
                response = self.client.post('/api/character-ai/generate', json={**self.payload, key: value})
                self.assertEqual(response.status_code, 422)

    def test_upstream_errors_and_invalid_output(self):
        results = [(401, {'detail': 'Unauthorized'}, 401),
                   (504, {'detail': 'Timed out'}, 504),
                   (200, {'success': True, 'output_format': 'png', 'data': []}, 502),
                   (200, {'success': True, 'output_format': 'png', 'data': [{'b64_json': 'bad'}]}, 502),
                   (200, ['not a response'], 502)]
        current = None
        self.mock_upstream(lambda request: httpx.Response(current[0], json=current[1]))
        for current in results:
            with self.subTest(current=current):
                response = self.client.post('/api/character-ai/generate', json=self.payload)
                self.assertEqual(response.status_code, current[2], response.text)

    def test_connection_timeout_is_reported(self):
        def upstream(request):
            raise httpx.ReadTimeout('Timeout', request=request)
        self.mock_upstream(upstream)
        response = self.client.post('/api/character-ai/generate', json=self.payload)
        self.assertEqual(response.status_code, 504)

    def test_invalid_endpoint_or_missing_credentials(self):
        for endpoint in ('file:///etc/passwd', 'http://[', 'http://user:pass@codex.test'):
            with patch.dict(os.environ, {'CODEX_IMAGE_API_URL': endpoint}):
                self.assertEqual(self.client.post('/api/character-ai/generate', json=self.payload).status_code, 422)
        with patch.dict(os.environ, {'CODEX_API_TOKEN': '', 'CODEX_MODEL': ''}):
            self.assertEqual(self.client.post('/api/character-ai/generate', json=self.payload).status_code, 422)

    def test_normalizes_text_endpoint_from_existing_env(self):
        with patch.dict(os.environ, {'CODEX_IMAGE_API_URL': '', 'CODEX_API_URL': 'https://codex.test/prefix/analyze'}):
            self.assertEqual(ai.default_endpoint(), 'https://codex.test/prefix/generate-image')


if __name__ == '__main__':
    unittest.main()
