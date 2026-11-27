import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

import image_motion_ai as motion
import generate_kurzge as cli
from render_style import load_render_context
from scene_logic import check_scene, validate_contract


def image_group(aid, size, box):
    image = Image.new('RGBA', size)
    ImageDraw.Draw(image).rectangle(box, fill='#315ca8')
    stream = io.BytesIO()
    image.save(stream, 'PNG')
    data = base64.b64encode(stream.getvalue()).decode()
    return (f'<g id="{aid}"><image href="data:image/png;base64,{data}" '
            f'x="{-size[0]/2}" y="{-size[1]/2}" width="{size[0]}" height="{size[1]}" '
            'preserveAspectRatio="xMidYMid meet"/></g>')


LIBRARY = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080"><defs>'
           + image_group('BODY', (200, 200), (80, 40, 119, 159))
           + image_group('SUPPORT', (300, 60), (20, 20, 279, 39))
           + image_group('PROP', (100, 100), (40, 40, 59, 59))
           + image_group('COVER', (200, 200), (30, 30, 169, 169))
           + '</defs></svg>')


def instance(iid, asset, mode='environment'):
    return {'id': iid, 'asset': asset, 'space': 'room', 'mode': mode,
            'reason': 'An explicitly staged physical relationship in the test scene.'}


def use(iid, asset, x, y, cls=''):
    return f'<g transform="translate({x} {y})"><g class="{cls}"><use id="{iid}" href="#{asset}"/></g></g>'


def scene(uses, instances, relations, *, css='', actions=None, causes=None):
    contract = {'version': 1, 'instances': instances, 'relations': relations, 'causality': causes or []}
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
           '<style>@keyframes hold{from{opacity:1}to{opacity:1}}'
           '.moving{animation:travel 2s linear both;transform-origin:0 0;transform-box:view-box}'
           '@keyframes travel{from{transform:translateX(0px)}to{transform:translateX(400px)}}'
           + css + '</style><desc id="scene-logic">' + json.dumps(contract)
           + '</desc><g id="artwork">' + uses + '</g></svg>')
    phase = {'id': 1, 'duration': 2, 'actions': actions or [
        {'target': 'BODY', 'type': 'move', 'start': 0, 'end': 2,
         'from': {'x': 500, 'y': 500}, 'to': {'x': 900, 'y': 500}}]}
    return svg, contract, phase


SUPPORT = {'type': 'supported_by', 'a': 'body', 'b': 'seat', 'start': 0, 'end': 2,
           'point': [.5, 1], 'surface': [[0, 0], [1, 0]], 'tolerance': 1}


class SceneLogicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)
        self.geometry = {r['id']: r for r in motion.measured_geometry(LIBRARY)}

    def check(self, fixture):
        svg, contract, phase = fixture
        validate_contract(ET.fromstring(svg), phase, self.geometry.keys())
        root = ET.fromstring(svg)
        root.insert(0, ET.fromstring(LIBRARY).find(f'{{{motion.NS}}}defs'))
        check_scene(ET.tostring(root, encoding='unicode'), contract, self.geometry, phase, self.output, 1)

    def test_support_uses_actual_alpha_surface_and_rejects_sitting_beside_it(self):
        self.assertEqual(self.geometry['BODY']['bounds'], [-20, -60, 20, 60])
        good = scene(use('seat', 'SUPPORT', 500, 570) + use('body', 'BODY', 500, 500),
                     [instance('seat', 'SUPPORT'), instance('body', 'BODY', 'supported')], [SUPPORT])
        self.check(good)
        bad = (good[0].replace('translate(500 500)', 'translate(300 500)'), good[1], good[2])
        with self.assertRaisesRegex(ValueError, 'no contact with support'):
            self.check(bad)

    def test_source_aspect_ratio_and_transparent_margins_are_preserved(self):
        group = image_group('WIDE', (80, 40), (10, 10, 69, 29))
        group = group.replace('x="-40.0" y="-20.0" width="80" height="40"',
                              'x="-100" y="-100" width="200" height="200"')
        library = f'<svg xmlns="{motion.NS}"><defs>{group}</defs></svg>'
        self.assertEqual(motion.measured_geometry(library)[0]['bounds'], [-75, -25, 75, 25])

    def test_attachment_must_follow_carrier_between_endpoints(self):
        relation = {'type': 'contact', 'a': 'prop', 'b': 'body', 'start': 0, 'end': 2,
                    'a_point': [0, .5], 'b_point': [1, .5], 'tolerance': 1}
        good = scene(use('body', 'BODY', 500, 500, 'moving') + use('prop', 'PROP', 530, 500, 'moving'),
                     [instance('body', 'BODY', 'free'), instance('prop', 'PROP', 'attached')], [relation])
        self.check(good)
        bad = (good[0].replace('translate(530 500)"><g class="moving"', 'translate(530 500)"><g class=""'),
               good[1], good[2])
        with self.assertRaisesRegex(ValueError, 'contact points detached'):
            self.check(bad)

    def test_cover_requires_overlap_and_correct_actual_paint_order(self):
        body, cover = use('body', 'BODY', 500, 500), use('cover', 'COVER', 500, 500)
        instances = [instance('body', 'BODY'), instance('cover', 'COVER')]
        relations = [{'type': 'covers', 'a': 'cover', 'b': 'body', 'start': 0, 'end': 2}]
        self.check(scene(body + cover, instances, relations))
        with self.assertRaisesRegex(ValueError, 'reversed paint order'):
            self.check(scene(cover + body, instances, relations))
        with self.assertRaisesRegex(ValueError, 'does not overlap'):
            self.check(scene(body + use('cover', 'COVER', 900, 500), instances, relations))

    def test_path_collision_is_caught_even_when_both_endpoints_are_clear(self):
        fixture = scene(use('body', 'BODY', 300, 500, 'moving') + use('prop', 'PROP', 500, 500),
                        [instance('body', 'BODY', 'free'), instance('prop', 'PROP')],
                        [{'type': 'separate', 'a': 'body', 'b': 'prop', 'start': 0, 'end': 2}])
        with self.assertRaisesRegex(ValueError, 'solid silhouettes intersect'):
            self.check(fixture)
        report = json.loads((self.output / 'phase_1.logic.json').read_text())
        self.assertTrue(any('0.900s' in e or '1.000s' in e for e in report['errors']))

    def test_container_checks_local_region_through_rotation(self):
        relation = {'type': 'contained_in', 'a': 'prop', 'b': 'cover', 'start': 0, 'end': 2,
                    'region': [.2, .2, .8, .8], 'tolerance': 1}
        good = scene(use('cover', 'COVER', 500, 500) + use('prop', 'PROP', 500, 500),
                     [instance('cover', 'COVER'), instance('prop', 'PROP', 'contained')], [relation])
        # Rotate the whole scene so containment must be evaluated in container coordinates.
        good = (good[0].replace('<g id="artwork">', '<g id="artwork" transform="rotate(30 500 500)">'), good[1], good[2])
        self.check(good)
        with self.assertRaisesRegex(ValueError, 'outside receiving region'):
            self.check((good[0].replace('href="#PROP"', 'transform="translate(100 0)" href="#PROP"'), good[1], good[2]))

    def test_support_disappearing_and_uncovered_relation_interval_are_rejected(self):
        uses = use('seat', 'SUPPORT', 500, 570, 'vanish') + use('body', 'BODY', 500, 500)
        instances = [instance('seat', 'SUPPORT'), instance('body', 'BODY', 'supported')]
        css = '.vanish{animation:gone 2s linear both}@keyframes gone{0%,49%{opacity:1}50%,100%{opacity:0}}'
        with self.assertRaisesRegex(ValueError, 'support invisible'):
            self.check(scene(uses, instances, [SUPPORT], css=css))
        with self.assertRaisesRegex(ValueError, 'visible without supported_by'):
            self.check(scene(uses, instances, [{**SUPPORT, 'end': 1}]))

    def test_duplicate_entity_is_not_allowed_outside_its_crossfade(self):
        with self.assertRaisesRegex(ValueError, 'duplicate visible copies'):
            self.check(scene(use('one', 'BODY', 500, 500) + use('two', 'BODY', 700, 500),
                             [instance('one', 'BODY'), instance('two', 'BODY')], []))

    def test_result_cannot_precede_the_cause_or_depend_on_itself(self):
        actions = [{'start': 1, 'end': 2}, {'start': 0, 'end': 1}]
        fixture = scene(use('body', 'BODY', 500, 500), [instance('body', 'BODY')], [],
                        actions=actions, causes=[{'cause': 0, 'effect': 1, 'trigger': 'end'}])
        with self.assertRaisesRegex(ValueError, 'kết quả xảy ra trước nguyên nhân'):
            validate_contract(ET.fromstring(fixture[0]), fixture[2], self.geometry.keys())

    def test_rendered_effect_cannot_appear_before_its_causal_action(self):
        actions = [{'target': 'BODY', 'type': 'move', 'start': 0, 'end': 1},
                   {'target': 'PROP', 'type': 'fade', 'start': 1, 'end': 2,
                    'from': {'opacity': 0}, 'to': {'opacity': 1}}]
        fixture = scene(use('body', 'BODY', 500, 500) + use('prop', 'PROP', 530, 500),
                        [instance('body', 'BODY'), instance('prop', 'PROP', 'overlay')], [],
                        actions=actions, causes=[{'cause': 0, 'effect': 1, 'trigger': 'end'}])
        with self.assertRaisesRegex(ValueError, 'visible effect before its causal action'):
            self.check(fixture)

    def test_physical_size_ratio_is_measured_after_scene_transforms(self):
        relation = {'type': 'size_ratio', 'a': 'body', 'b': 'seat', 'start': 0, 'end': 2,
                    'a_axis': 'width', 'b_axis': 'width', 'min': .1, 'max': .3}
        fixture = scene(use('seat', 'SUPPORT', 500, 570) + use('body', 'BODY', 500, 500),
                        [instance('seat', 'SUPPORT'), instance('body', 'BODY')], [relation])
        self.check(fixture)
        with self.assertRaisesRegex(ValueError, 'physical size ratio'):
            self.check((fixture[0].replace('href="#BODY"', 'transform="scale(.1)" href="#BODY"'), fixture[1], fixture[2]))

    def test_renderer_repairs_a_failed_relationship_before_publishing(self):
        good, contract, phase = scene(use('seat', 'SUPPORT', 500, 570) + use('body', 'BODY', 500, 500),
                                     [instance('seat', 'SUPPORT'), instance('body', 'BODY', 'supported')], [SUPPORT])
        bad = good.replace('translate(500 500)', 'translate(300 500)')
        script = {'title': 'Support interaction', 'phases': [phase], 'assets': [
            {'id': 'BODY', 'category': 'character', 'description': 'A full-size subject.'},
            {'id': 'SUPPORT', 'category': 'object', 'description': 'A supporting surface.'}]}
        request = Mock(side_effect=[bad, good])
        renderer = motion.Renderer(script, self.output, request, cli.clean_svg)
        renderer.library, renderer.fingerprint = LIBRARY, 'a' * 64
        renderer.geometry = motion.measured_geometry(LIBRARY)
        (self.output / 'prompts').mkdir()
        renderer.render(1)
        self.assertEqual(request.call_count, 2)
        self.assertIn('no contact with support', request.call_args.args[0])
        self.assertTrue(json.loads((self.output / 'phase_1.logic.json').read_text())['passed'])

    def test_contract_cannot_omit_instances_or_claim_support_without_a_relation(self):
        fixture = scene(use('body', 'BODY', 500, 500), [instance('body', 'BODY', 'supported')], [])
        with self.assertRaisesRegex(ValueError, 'thiếu quan hệ'):
            validate_contract(ET.fromstring(fixture[0]), fixture[2], self.geometry.keys())
        root = ET.fromstring(fixture[0]); root.remove(root.find(f'{{{motion.NS}}}desc'))
        with self.assertRaisesRegex(ValueError, 'scene-logic'):
            validate_contract(root, fixture[2], self.geometry.keys())

    def test_selected_character_template_is_loaded_from_category_config(self):
        context = load_render_context('character-cartoon', 'education')
        self.assertEqual(context['template']['id'], 'character')
        self.assertIn('Xeko', context['template']['skill'])
        self.assertNotIn('template', load_render_context('flat', 'all_styles'))


if __name__ == '__main__':
    unittest.main()
