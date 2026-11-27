import base64
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

from backend.graphics import GraphicsJobManager
from backend.models import GraphicsRequest
from backend.still_previews import build_stills
from backend.test_graphics import graphics_script, png_response, seed_script
from character_assets import CharacterAssets, ROOT, is_xeko, reference_prompt
from image_asset_generator import ImageAssetGenerator
import image_motion_ai as motion
from render_style import load_render_context, style_prompt


CONFIG = {'url': 'http://localhost/generate-image', 'key': 'test', 'model': 'test', 'quality': 'medium'}


def xeko_script():
    script = graphics_script()
    script['assets'][0].update(id='XEKO', category='character', name='Xeko',
                               description='Xeko full-body 512x512. Pose happy-seated: seated happily.')
    for phase in script['phases']:
        phase['actions'][0]['target'] = 'XEKO'
    return script


class CharacterReferencesTests(unittest.TestCase):
    def test_education_job_snapshots_template_catalog_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            seed_script(storage)
            manager = GraphicsJobManager(storage)
            try:
                with patch.object(manager.executor, 'submit'):
                    job = manager.create(GraphicsRequest(projectId='xeko-test', scriptId='a' * 32,
                                                         categoryId='education', styleId='character-cartoon'))
                output = storage / 'previews' / job['id']
                context = json.loads((output / 'render_config.json').read_text())
                self.assertEqual(context['template']['id'], 'character')
                self.assertIn('canonical_views', context['template']['library']['catalog'])
                self.assertEqual((output / 'assets/characters/design/01-front-view.png').read_bytes(),
                                 (ROOT / 'design/01-front-view.png').read_bytes())
                self.assertIn('WHITE PLAY-BUTTON', style_prompt(context))
            finally:
                manager.close()

    def test_exact_catalog_pose_is_reused_without_image_request(self):
        context = load_render_context('character-cartoon', 'education')
        with tempfile.TemporaryDirectory() as directory, patch('image_asset_generator.urlopen') as api:
            output = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                renderer = motion.Renderer(xeko_script(), output, None, None, style_context=context).prepare()
            api.assert_not_called()
            metadata = json.loads((output / 'assets.meta.json').read_text())['assets'][0]
            self.assertEqual(metadata['operation'], 'catalog_reuse')
            self.assertEqual((output / metadata['file']).read_bytes(),
                             (ROOT / 'poses/xeko-happy-seated.png').read_bytes())
            self.assertIn('data:image/png;base64,', renderer.library)
            self.assertTrue((output / 'assets/characters/catalog.json').is_file())

    def test_new_pose_attaches_canonical_but_supporting_character_does_not(self):
        script = xeko_script()
        script['assets'][0]['description'] = 'Xeko pointing at a diagram 512x512.'
        script['assets'].append({'id': 'FRIEND', 'name': 'Lan', 'category': 'character',
                                 'description': 'A girl wearing a yellow shirt 512x512.'})
        context = load_render_context('character-cartoon', 'education')
        with tempfile.TemporaryDirectory() as directory, patch('image_asset_generator.image_config', return_value=CONFIG), \
                patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())) as api:
            output = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                motion.Renderer(script, output, None, None, style_context=context).prepare()
            first, second = [json.loads(call.args[0].data) for call in api.call_args_list]
            original = base64.b64decode(first['reference_images'][0].split(',', 1)[1])
            self.assertEqual(original, (ROOT / 'design/01-front-view.png').read_bytes())
            self.assertNotIn('reference_images', second)
            self.assertIn('SELECTED CHARACTER REFERENCES', first['prompt'])

    def test_static_phases_attach_reference_only_when_xeko_is_present(self):
        script = xeko_script()
        script['phases'][1]['actions'] = []
        with tempfile.TemporaryDirectory() as directory, patch('image_asset_generator.image_config', return_value=CONFIG), \
                patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())) as api:
            build_stills(script, Path(directory), load_render_context('character-cartoon', 'education'), lambda *a: None)
            requests = [json.loads(call.args[0].data) for call in api.call_args_list]
            self.assertTrue(requests[0]['reference_images'])
            self.assertNotIn('reference_images', requests[1])

    def test_reference_bytes_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('image_asset_generator.urlopen', side_effect=lambda *a, **k: io.BytesIO(png_response())) as api:
            root = Path(directory)
            reference = root / 'reference.png'
            generator = ImageAssetGenerator(root / 'cache', CONFIG)
            for color in ('red', 'red', 'blue'):
                Image.new('RGB', (2, 2), color).save(reference)
                generator.generate('Same prompt', transparent=True, requested_size=[32, 32],
                                   reference_images=[reference])
            self.assertEqual(api.call_count, 2)

    def test_old_server_is_rejected_without_text_only_retry(self):
        error = HTTPError(CONFIG['url'], 422, 'Unsupported', {}, io.BytesIO())
        self.addCleanup(error.close)
        with tempfile.TemporaryDirectory() as directory, patch('image_asset_generator.urlopen',
                side_effect=error) as api:
            with self.assertRaisesRegex(ValueError, 'không sinh Xeko chỉ bằng mô tả chữ'):
                ImageAssetGenerator(directory, CONFIG).generate('Xeko', transparent=True,
                    requested_size=[512, 512], reference_images=[ROOT / 'design/01-front-view.png'])
            self.assertEqual(api.call_count, 1)

    def test_missing_profile_falls_back_to_existing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            library = CharacterAssets(load_render_context('character-cartoon', 'education'), Path(directory))
            reference = library.references('left profile facing right')[0]
            self.assertTrue(reference.is_file())
            self.assertIn(reference.relative_to(library.root).as_posix(),
                          [v['file'] for v in library.catalog['canonical_views'].values()])

    def test_supporting_character_mentioning_xeko_keeps_own_identity(self):
        self.assertFalse(is_xeko({'id': 'LAN', 'category': 'character', 'name': 'Lan',
                                   'description': 'Lan standing next to Xeko.'}))
        self.assertTrue(is_xeko({'id': 'XEKO_01', 'category': 'character'}))

    def test_costume_reference_precedes_pose_and_prevents_default_outfit_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            library = CharacterAssets(load_render_context('character-cartoon', 'education'), Path(directory))
            refs = library.references('Xeko scientist happy seated')
            self.assertEqual(refs[0].name, '01-front-view.png')
            self.assertEqual(refs[1].name, 'scientist.png')
            asset = xeko_script()['assets'][0]
            asset['description'] = 'Xeko dressed as a scientist, full-body.'
            self.assertIsNone(library.reuse(asset, 'happy-seated'))

    def test_relative_cli_output_supports_references_and_provenance(self):
        with tempfile.TemporaryDirectory(dir='.') as directory:
            output = Path(directory).relative_to(Path.cwd()) if Path(directory).is_absolute() else Path(directory)
            library = CharacterAssets(load_render_context('character-cartoon', 'education'), output)
            refs = library.references('front')
            self.assertIn('assets/characters/design/01-front-view.png', reference_prompt(refs, output))
            library.record('XEKO', 'front', refs[0], {}, refs)
            self.assertTrue((output / 'assets/characters/catalog.json').is_file())


if __name__ == '__main__':
    unittest.main()
