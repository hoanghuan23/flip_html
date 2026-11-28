import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

import character_library as library


class GeneratedCharacterLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.catalog_path = self.root / 'character_assets.json'
        self.original = {
            'version': 1, 'asset_root': 'skills/templates/character_rig',
            'assets': {'legacy_head': {'source': 'HEAD/old.png'}},
            'rig_profiles': {'legacy_front': {'canvas': [360, 440]}},
            'generated_characters': {},
        }
        self.catalog_path.write_text(json.dumps(self.original))
        self.store = library.GeneratedCharacterLibrary(self.catalog_path, project_root=self.root)
        buffer = io.BytesIO()
        Image.new('RGBA', (64, 96), (220, 30, 30, 128)).save(buffer, format='PNG')
        self.png = buffer.getvalue()
        self.metadata = {'preset_id': 'front_happy', 'view': 'front', 'description': 'Nhân vật hoàn chỉnh',
                         'joints': {'neck': [32, 24], 'shoulder_L': [20, 32], 'shoulder_R': [44, 32]},
                         'generation': {'provider': 'test', 'model': 'fixture'}}

    def test_saves_exact_returned_png_and_joint_coordinates_in_catalog(self):
        saved = self.store.save('front_happy_v1', self.png, self.metadata)
        self.assertTrue(saved['source'].startswith('GENERATED/'))
        path = self.root / self.original['asset_root'] / saved['source']
        self.assertEqual(path.read_bytes(), self.png)
        self.assertEqual(saved['image_size'], [64, 96])
        self.assertEqual(saved['sha256'], hashlib.sha256(self.png).hexdigest())
        self.assertEqual(saved['joints'], self.metadata['joints'])
        self.assertEqual(saved['coordinate_space'], 'image_pixels_top_left')
        catalog = json.loads(self.catalog_path.read_text())
        self.assertEqual(catalog['assets'], self.original['assets'])
        self.assertEqual(catalog['rig_profiles'], self.original['rig_profiles'])
        self.assertEqual(catalog['generated_characters']['front_happy_v1']['joints'], self.metadata['joints'])
        self.assertEqual(self.store.get('front_happy_v1'), saved)

    def test_reuses_saved_character_after_restart_without_ai_or_source_png(self):
        source = self.root / 'ai-returned.png'
        source.write_bytes(self.png)
        generate = Mock(side_effect=lambda: (source.read_bytes(), self.metadata))
        first = self.store.get_or_create('front_happy_v1', generate)
        source.unlink()
        reopened = library.GeneratedCharacterLibrary(self.catalog_path, project_root=self.root)
        self.assertEqual(reopened.get_or_create('front_happy_v1', generate), first)
        generate.assert_called_once_with()

    def test_same_result_is_idempotent_but_changed_joints_require_explicit_overwrite(self):
        first = self.store.save('happy', self.png, self.metadata)
        before = self.catalog_path.read_bytes()
        self.assertEqual(self.store.save('happy', self.png, self.metadata), first)
        self.assertEqual(self.catalog_path.read_bytes(), before)
        changed = copy.deepcopy(self.metadata)
        changed['joints']['neck'] = [32, 25]
        with self.assertRaisesRegex(library.CharacterLibraryError, 'ID đã tồn tại'):
            self.store.save('happy', self.png, changed)
        self.assertEqual(self.catalog_path.read_bytes(), before)
        self.store.save('happy', self.png, changed, overwrite=True)
        self.assertEqual(self.store.get('happy')['joints']['neck'], [32, 25])

    def test_invalid_joints_or_coordinate_system_do_not_change_catalog(self):
        before = self.catalog_path.read_bytes()
        invalid = [
            {}, {'joints': {}}, {'joints': {'neck': [64, 24]}}, {'joints': {'neck': [-1, 24]}},
            {'joints': {'neck': [True, 24]}}, {'joints': {'neck': [32, float('nan')]}},
            {'joints': {'neck': [32, 24, 0]}}, {'joints': {'../neck': [32, 24]}},
            {**self.metadata, 'image_size': [32, 48]},
            {**self.metadata, 'coordinate_space': 'normalized'},
            {**self.metadata, 'source': '../outside.png'},
        ]
        for metadata in invalid:
            with self.subTest(metadata=metadata), self.assertRaises(library.CharacterLibraryError):
                self.store.save('happy', self.png, metadata)
        self.assertEqual(self.catalog_path.read_bytes(), before)
        self.assertFalse((self.root / self.original['asset_root']).exists())

    def test_invalid_png_or_id_never_creates_a_library_entry(self):
        for character_id, raw in [('happy', b'not png'), ('../outside', self.png), ('', self.png)]:
            with self.subTest(character_id=character_id), self.assertRaises(library.CharacterLibraryError):
                self.store.save(character_id, raw, self.metadata)
        self.assertEqual(self.store.catalog()['generated_characters'], {})

    def test_modified_or_missing_cached_png_is_reported_without_an_ai_call(self):
        saved = self.store.save('happy', self.png, self.metadata)
        path = self.root / self.original['asset_root'] / saved['source']
        generate = Mock()
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(library.CharacterLibraryError, 'PNG đã thay đổi'):
            self.store.get_or_create('happy', generate)
        path.unlink()
        with self.assertRaisesRegex(library.CharacterLibraryError, 'Không đọc được PNG'):
            self.store.get_or_create('happy', generate)
        generate.assert_not_called()

    def test_different_characters_are_retained_during_concurrent_saves(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.store.save, name, self.png, self.metadata)
                       for name in ('happy', 'excited')]
            for future in futures:
                future.result()
        self.assertEqual(set(self.store.catalog()['generated_characters']), {'happy', 'excited'})
        for name in ('happy', 'excited'):
            self.assertEqual(self.store.get(name)['joints'], self.metadata['joints'])

    def test_failed_catalog_publication_preserves_previous_records(self):
        self.store.save('happy', self.png, self.metadata)
        before = self.catalog_path.read_bytes()
        real_write = library.atomic_write

        def fail_catalog(path, raw):
            if path == self.catalog_path:
                raise OSError('disk full')
            real_write(path, raw)

        with patch.object(library, 'atomic_write', side_effect=fail_catalog):
            with self.assertRaises(OSError):
                self.store.save('excited', self.png, self.metadata)
        self.assertEqual(self.catalog_path.read_bytes(), before)
        self.assertEqual(self.store.get('happy')['joints'], self.metadata['joints'])

    def test_generated_directory_cannot_escape_asset_root_through_symlink(self):
        root = self.root / self.original['asset_root']
        root.mkdir(parents=True)
        outside = self.root / 'outside'
        outside.mkdir()
        (root / 'GENERATED').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(library.CharacterLibraryError, 'nằm ngoài thư viện'):
            self.store.save('happy', self.png, self.metadata)
        self.assertEqual(list(outside.iterdir()), [])

    def test_cli_add_list_and_get_use_only_local_files(self):
        source = self.root / 'ai-returned.png'
        source.write_bytes(self.png)
        metadata = self.root / 'joints.json'
        metadata.write_text(json.dumps(self.metadata))
        with patch.object(library, 'GeneratedCharacterLibrary', return_value=self.store), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            library.main(['add', 'happy', '--image', str(source), '--metadata', str(metadata)])
            self.assertEqual(json.loads(output.getvalue())['joints'], self.metadata['joints'])
            output.seek(0)
            output.truncate()
            library.main(['list'])
            self.assertEqual(json.loads(output.getvalue()), ['happy'])
            output.seek(0)
            output.truncate()
            library.main(['get', 'happy'])
            self.assertEqual(json.loads(output.getvalue())['source'], self.store.get('happy')['source'])


if __name__ == '__main__':
    unittest.main()
