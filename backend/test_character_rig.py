import base64
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from assemble_character import CharacterConfigError, CharacterRig, main


class CharacterRigTests(unittest.TestCase):
    def setUp(self):
        self.rig = CharacterRig()

    def test_all_shipped_presets_resolve_and_attach_to_profile_sockets(self):
        self.rig.validate()
        for preset_id, preset in self.rig.presets.items():
            with self.subTest(preset=preset_id):
                canvas, layers = self.rig.layout(preset_id)
                profile = self.rig.profiles[preset['rig_profile']]
                self.assertEqual(canvas, (360, 440))
                self.assertEqual(len(layers), 7)
                for layer in layers:
                    asset = self.rig.assets[preset['parts'][layer.slot]]
                    parent_slot = asset.get('parent_slot', layer.slot)
                    transforms = preset.get('transforms', {})
                    own_offset = transforms.get(layer.slot, {}).get('offset', [0, 0])
                    parent_offset = (transforms.get(parent_slot, {}).get('offset', [0, 0])
                                     if parent_slot != layer.slot else [0, 0])
                    for i, position in enumerate((layer.x, layer.y)):
                        self.assertAlmostEqual(position + asset['attach_point'][i] * layer.scale,
                                               profile['sockets'][parent_slot][i] + own_offset[i] + parent_offset[i])

    def test_svg_uses_corrected_suit_and_prepared_default_as_design_reference(self):
        _, layers = self.rig.layout('front_happy')
        torso = next(layer for layer in layers if layer.slot == 'suit')
        self.assertEqual(torso.source, 'SUIT/DEFAULT/torso_front.png')
        self.assertEqual(torso.render_source, 'SUIT/DEFAULT/torso_front.png')
        self.assertEqual(self.rig.assets[torso.source]['reference_source'], torso.source)
        svg = ET.fromstring(self.rig.svg('front_happy'))
        images = svg.findall('.//{http://www.w3.org/2000/svg}image')
        self.assertEqual(len(images), 7)
        self.assertTrue(all(image.attrib['href'].startswith('data:image/png;base64,iVBOR')
                            for image in images))
        torso_image = svg.find('.//{http://www.w3.org/2000/svg}g[@data-slot="suit"]'
                               '/{http://www.w3.org/2000/svg}g/{http://www.w3.org/2000/svg}image')
        embedded = base64.b64decode(torso_image.attrib['href'].split(',', 1)[1])
        self.assertEqual(embedded, torso.path.read_bytes())
        self.assertNotIn('clip-path', torso_image.attrib)
        self.assertEqual(len(svg.findall('.//{http://www.w3.org/2000/svg}clipPath')), 2)
        for layer in layers:
            if layer.slot != 'suit':
                self.assertEqual(layer.source, layer.render_source)

    def test_missing_suit_design_reference_is_reported(self):
        suit = self.rig.assets['SUIT/DEFAULT/torso_front.png']
        suit['reference_source'] = 'SUIT/DEFAULT/missing.png'
        with self.assertRaisesRegex(CharacterConfigError, 'Không tìm thấy ảnh'):
            self.rig.layout('front_happy')

    def test_shoulder_joints_follow_parent_transform_and_draw_behind_arms(self):
        self.rig.presets['front_happy']['transforms']['arm_L'] = {
            'offset': [10, -5], 'rotation': 37, 'scale': 1.3}
        for preset_id in self.rig.presets:
            with self.subTest(preset=preset_id):
                _, layers = self.rig.layout(preset_id)
                slots = [layer.slot for layer in layers]
                by_slot = {layer.slot: layer for layer in layers}
                for side in ('L', 'R'):
                    joint = by_slot['shoulder_' + side]
                    arm = by_slot['arm_' + side]
                    self.assertEqual(joint.pivot, arm.pivot)
                    joint_transform = self.rig.presets[preset_id].get('transforms', {}).get(joint.slot, {})
                    self.assertEqual(joint.rotation, arm.rotation + joint_transform.get('rotation', 0))
                    self.assertLess(slots.index(joint.slot), slots.index(arm.slot))
                    self.assertLess(slots.index(joint.slot), slots.index('suit'))
                    if preset_id == 'front_happy' and side == 'L':
                        self.assertAlmostEqual(joint.scale, .85 * 1.3)

    def test_shoulder_joint_cannot_follow_the_wrong_arm(self):
        self.rig.assets['JOINT/DEFAULT/shoulder_L.png']['parent_slot'] = 'arm_R'
        with self.assertRaisesRegex(CharacterConfigError, 'parent_slot phải là arm_L'):
            self.rig.layout('front_happy')

    def test_presets_can_omit_optional_joint_layers(self):
        preset = self.rig.presets['front_happy']
        del preset['parts']['shoulder_L']
        del preset['parts']['shoulder_R']
        preset['layer_order'] = ['legs_pair', 'arm_L', 'arm_R', 'suit', 'head']
        _, layers = self.rig.layout('front_happy')
        self.assertEqual(len(layers), 5)

    def test_bent_arms_draw_in_front_and_raised_arms_rotate_at_shoulders(self):
        _, bent = self.rig.layout('front_bend')
        slots = [layer.slot for layer in bent]
        self.assertLess(slots.index('suit'), slots.index('arm_L'))
        _, raised = self.rig.layout('front_raise')
        arms = {layer.slot: layer for layer in raised if layer.slot.startswith('arm_')}
        self.assertLess(arms['arm_L'].rotation, 0)
        self.assertGreater(arms['arm_R'].rotation, 0)
        for arm in arms.values():
            self.assertIsNotNone(arm.clip_rect)
            self.assertLess(arm.clip_rect[1] + arm.clip_rect[3], arm.size[1])

    def test_wrong_side_unregistered_asset_missing_file_and_incompatible_suit_fail(self):
        original = copy.deepcopy(self.rig.presets['front_happy'])
        for bad, message in [('HAND/07_ARM/down_R.png', 'sai slot'),
                             ('HEAD/not_registered.png', 'chưa đăng ký')]:
            with self.subTest(asset=bad):
                self.rig.presets['front_happy'] = copy.deepcopy(original)
                self.rig.presets['front_happy']['parts']['arm_L'] = bad
                with self.assertRaisesRegex(CharacterConfigError, message):
                    self.rig.layout('front_happy')
        self.rig.presets['front_happy'] = original
        arm = self.rig.assets['HAND/07_ARM/down_L.png']
        arm['compatible_suits'] = ['SPORT']
        with self.assertRaisesRegex(CharacterConfigError, 'không tương thích'):
            self.rig.layout('front_happy')
        arm['compatible_suits'] = ['DEFAULT']
        arm['render_source'] = 'HAND/missing.png'
        with self.assertRaisesRegex(CharacterConfigError, 'Không tìm thấy ảnh'):
            self.rig.layout('front_happy')

    def test_library_paths_cannot_escape_or_reference_non_png_files(self):
        for path in ['../../README.md', str(Path(__file__).resolve()), 'HEAD/a.svg', '', None]:
            with self.subTest(path=path), self.assertRaises(CharacterConfigError):
                self.rig.asset_path(path)

    def test_mixed_leg_modes_duplicate_layers_and_wrong_views_fail(self):
        preset = self.rig.presets['front_happy']
        preset['parts']['leg_L'] = preset['parts']['legs_pair']
        with self.assertRaisesRegex(CharacterConfigError, 'legs_pair HOẶC'):
            self.rig.layout('front_happy')
        del preset['parts']['leg_L']
        preset['layer_order'] = ['legs_pair', 'suit', 'arm_L', 'arm_L', 'head']
        with self.assertRaisesRegex(CharacterConfigError, 'layer_order'):
            self.rig.layout('front_happy')
        del preset['layer_order']
        preset['view'] = 'back'
        with self.assertRaisesRegex(CharacterConfigError, 'góc nhìn'):
            self.rig.layout('front_happy')

    def test_invalid_calibration_and_transform_typos_fail(self):
        arm = self.rig.assets['HAND/07_ARM/down_L.png']
        for bad in [0, -1, True, '0.8', float('inf'), 10 ** 1000]:
            with self.subTest(scale=str(bad)[:30]):
                arm['scale'] = bad
                with self.assertRaisesRegex(CharacterConfigError, 'scale'):
                    self.rig.layout('front_happy')
        arm['scale'] = 0.8
        arm['attach_point'] = [9999, 0]
        with self.assertRaisesRegex(CharacterConfigError, 'nằm ngoài ảnh'):
            self.rig.layout('front_happy')
        arm['attach_point'] = [27, 4]
        self.rig.presets['front_happy']['transforms'] = {'arm_L': {'rotaton': 20}}
        with self.assertRaisesRegex(CharacterConfigError, 'chỉ hỗ trợ'):
            self.rig.layout('front_happy')

    def test_html_escapes_description_and_does_not_require_a_server(self):
        self.rig.presets['front_happy']['description'] = '<script>alert(1)</script>'
        html = self.rig.html(['front_happy'])
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('data:image/png;base64,', html)
        self.assertNotIn('<link', html)

    def test_gallery_embeds_each_bitmap_once_and_is_visible_without_script(self):
        html = self.rig.html(list(self.rig.presets))
        paths = {layer.path for key in self.rig.presets for layer in self.rig.layout(key)[1]}
        for path in paths:
            self.assertEqual(html.count(self.rig.data_uri(path)), 1)
        self.assertEqual(html.count('<div class="character" data-state="static">'), len(self.rig.presets))
        self.assertNotIn('data-state="loading"', html)
        self.assertNotIn('Đang tải nhân vật', html)
        self.assertNotIn('<noscript>', html)
        self.assertIn('window.characterPreviewReady', html)

    def test_clip_rect_rejects_invalid_or_out_of_bounds_regions(self):
        arm = self.rig.assets['HAND/07_ARM/down_L.png']
        for rect in ([0, 0, 0, 20], [0, 0, 999, 20], [-1, 0, 10, 10], [0, 0, 10],
                     [0, False, 10, 10]):
            with self.subTest(rect=rect):
                arm['clip_rect'] = rect
                with self.assertRaisesRegex(CharacterConfigError, 'clip_rect'):
                    self.rig.layout('front_happy')

    def test_cli_checks_without_writes_and_exports_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            output = Path(tmp) / 'gallery.html'
            self.assertEqual(main(['--check', '--output', str(output)]), 0)
            self.assertFalse(output.exists())
            self.assertEqual(main(['--gallery', '--output', str(output)]), 0)
            self.assertEqual(output.read_text().count('<article>'), len(self.rig.presets))
            self.assertEqual(main(['--output', str(output)]), 1)
            self.assertEqual(main(['--preset', 'unknown', '--output', str(Path(tmp) / 'bad.svg')]), 1)
            svg = Path(tmp) / 'happy.svg'
            self.assertEqual(main(['--gallery', '--output', str(svg)]), 1)
            self.assertEqual(main(['--output', str(svg)]), 0)
            self.assertEqual(main(['--preset', 'front_happy_closed', '--output', str(svg), '--overwrite']), 0)
            self.assertIn('khép miệng', ET.fromstring(svg.read_text()).attrib['aria-label'])
            protected = self.rig.asset_root / 'not_created.svg'
            self.assertEqual(main(['--output', str(protected)]), 1)
            self.assertFalse(protected.exists())

    def test_unsupported_config_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'assets.json'
            path.write_text(json.dumps({'version': 2}))
            with self.assertRaisesRegex(CharacterConfigError, 'version 1'):
                CharacterRig(assets_path=path)


if __name__ == '__main__':
    unittest.main()
