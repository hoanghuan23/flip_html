import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.still_previews import build_stills
from backend.test_graphics import graphics_script, png_response
from character_assets import CharacterAssets, PARTS
from character_library import GeneratedCharacterLibrary
from image_motion_ai import image_specs
from render_style import load_render_style


class CharacterPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.catalog = self.root / 'character_assets.json'
        self.catalog.write_text(json.dumps({'version': 1, 'asset_root': 'rig', 'generated_characters': {}}))
        self.library = GeneratedCharacterLibrary(self.catalog, project_root=self.root)
        self.png = base64.b64decode(json.loads(png_response())['data'][0]['b64_json'])
        source = self.root / 'rig'
        source.mkdir()
        parts = {slot: slot + '.png' for slot in PARTS}
        for filename in parts.values():
            (source / filename).write_bytes(self.png)
        self.context = load_render_style('character-cartoon')
        self.context['character_library'] = {
            'presets': {'default_preset': 'front_happy', 'presets': {
                'front_happy': {'parts': parts, 'view': 'front'}}},
            'files': {p: hashlib.sha256(self.png).hexdigest() for p in parts.values()}}
        self.script = graphics_script()
        self.script['assets'][0].update(category='character', name='Xeko', preset_id='front_happy')
        patcher = patch('character_assets.GeneratedCharacterLibrary', return_value=self.library)
        patcher.start()
        self.addCleanup(patcher.stop)

    def build(self, output):
        output.mkdir()
        (output / 'kich_ban.json').write_text(json.dumps(self.script))
        build_stills(self.script, output, self.context, lambda *args: None)

    def test_saves_complete_sprite_and_reuses_it_in_another_preview_without_character_generation(self):
        calls = []
        def respond(request, **kwargs):
            calls.append(json.loads(request.data))
            return io.BytesIO(png_response())
        with patch('image_asset_generator.urlopen', side_effect=respond):
            self.build(self.root / 'first')
            entries = self.library.catalog()['generated_characters']
            self.assertEqual(len(entries), 1)
            entry = next(iter(entries.values()))
            self.assertEqual(entry['rig_status'], 'pending')
            self.assertEqual(entry['joints'], {})
            saved = self.root / 'rig' / entry['source']
            self.assertEqual(saved.read_bytes(), self.png)
            self.build(self.root / 'second')
        character_calls = [p for p in calls if 'Generate exactly ONE reusable PNG' in p['prompt']]
        self.assertEqual(len(character_calls), 1)
        self.assertEqual(len(character_calls[0]['reference_images']), 5)
        still_calls = [p for p in calls if 'Generate ONE complete static' in p['prompt']]
        self.assertEqual(len(still_calls), 4)
        self.assertTrue(all(len(p['reference_images']) == 1 for p in still_calls))
        character = CharacterAssets(self.context, self.root / 'animation')
        self.assertIsNotNone(character.reuse(image_specs(self.script)[0], 'default'))
        self.assertEqual(self.library.catalog()['generated_characters'], entries)

    def test_real_joint_metadata_returned_with_png_is_saved_without_rewriting_coordinates(self):
        payload = json.loads(png_response())
        payload['character_metadata'] = {'joints': {'neck': [16, 12], 'shoulder_L': [10, 16]},
                                         'image_size': [32, 32], 'preset_id': 'front_happy'}
        with patch('image_asset_generator.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            # One completed character needs one request; no storyboard calls here.
            from image_asset_generator import ImageAssetGenerator
            output = self.root / 'metadata'
            output.mkdir()
            character = CharacterAssets(self.context, output)
            character.prepare(self.script, ImageAssetGenerator(output / 'cache'), lambda *args: None)
        entry = next(iter(self.library.catalog()['generated_characters'].values()))
        self.assertEqual(entry['rig_status'], 'ready')
        self.assertEqual(entry['joints'], payload['character_metadata']['joints'])

    def test_modified_source_parts_require_new_job_instead_of_silently_switching_identity(self):
        (self.root / 'rig/head.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'đã thay đổi'):
            CharacterAssets(self.context, self.root / 'new-output')

    def test_new_camera_view_does_not_reuse_a_sprite_for_another_view(self):
        with patch('image_asset_generator.urlopen', side_effect=lambda *args, **kwargs: io.BytesIO(png_response())):
            self.build(self.root / 'original-view')
        character = CharacterAssets(self.context, self.root / 'new-view')
        self.assertIsNotNone(character.reuse(image_specs(self.script)[0], 'default'))
        changed = copy.deepcopy(self.script)
        changed['phases'][0]['camera']['view'] = 'top-down'
        self.assertIsNone(character.reuse(image_specs(changed)[0], 'default'))

    def test_manually_registered_character_keeps_its_metadata_during_animation_reuse(self):
        saved = self.library.save('saved_happy', self.png, {'joints': {'neck': [16, 12]}})
        asset = {**image_specs(self.script)[0], 'character_id': 'saved_happy'}
        character = CharacterAssets(self.context, self.root / 'manual-reuse')
        path, info = character.reuse(asset, 'default')
        character.record(asset['id'], 'default', path, info, [], asset=asset)
        self.assertEqual(self.library.get('saved_happy'), saved)
