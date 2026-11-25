"""Rebuild the bundled, deterministic 3D style sample without calling AI or TTS."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from render_style import load_render_style
from three_motion import build_preview


def starlink_plan(duration=28, reference_number=None):
    nodes = [
        {'id': 'space', 'geometry': 'stars'},
        {'id': 'earth', 'geometry': 'sphere', 'position': [-7, -15, -10], 'scale': [16, 16, 16],
         'rotation': [0, .7, -.2], 'material': {'color': '#ffffff', 'texture': 'earth', 'roughness': .85}},
        {'id': 'atmosphere', 'geometry': 'sphere', 'position': [-7, -15, -10], 'scale': [16.06]*3,
         'material': {'color': '#5aa6e8', 'opacity': .12, 'emissive': '#194d87'}},
        {'id': 'satellite', 'geometry': 'group', 'position': [-3, .2, 1], 'rotation': [.35, -.35, -.12]},
        {'id': 'body', 'parent': 'satellite', 'geometry': 'box', 'scale': [.6, 1.05, .28],
         'material': {'color': '#d2d7d9', 'metalness': .8, 'roughness': .28}},
        {'id': 'dish', 'parent': 'satellite', 'geometry': 'cylinder', 'position': [0, .55, .08],
         'scale': [.3, .08, .3], 'material': {'color': '#e3e7ea', 'metalness': .6}},
        {'id': 'mast', 'parent': 'satellite', 'geometry': 'cylinder', 'position': [0, .8, 0],
         'scale': [.035, .6, .035], 'material': {'color': '#a8b9c7', 'metalness': .8}},
    ]
    for side in (-1, 1):
        for i in range(7):
            nodes.append({'id': f'panel_{"L" if side < 0 else "R"}_{i}', 'parent': 'satellite',
                          'geometry': 'box', 'position': [side*(.6+i*.47), 0, 0], 'scale': [.44, .82, .045],
                          'material': {'color': '#153c68', 'metalness': .65, 'roughness': .3}})
            nodes.append({'id': f'frame_{"L" if side < 0 else "R"}_{i}', 'parent': 'satellite',
                          'geometry': 'box', 'position': [side*(.6+i*.47), -.44, 0], 'scale': [.46, .035, .065],
                          'material': {'color': '#8eacc2', 'metalness': .8}})
    overlays = [
        {'type': 'label', 'text': 'VỆ TINH STARLINK\nInternet từ quỹ đạo thấp', 'start': 0, 'end': duration,
         'x': .08, 'y': .12},
        {'type': 'connector', 'text': 'Quỹ đạo thấp – khoảng 550 km', 'start': duration*.55, 'end': duration,
         'target': 'satellite', 'anchor': [0, -.6, 0], 'endTarget': 'earth', 'endAnchor': [.02, .99, .1],
         'x': .12, 'y': .65},
    ]
    if reference_number:
        overlays.append({'type': 'image', 'number': reference_number, 'text': 'Vệ tinh Starlink · Hình '+str(reference_number),
                         'start': duration*.32, 'end': duration, 'x': .59, 'y': .18, 'width': .33})
    return {'background': '#060c14', 'nodes': nodes,
            'camera': [{'t': 0, 'position': [0, 2, 23], 'lookAt': [-1, 0, 0]},
                       {'t': duration*.28, 'position': [-1, 1.5, 17], 'lookAt': [-1.2, .2, 0]},
                       {'t': duration*.55, 'position': [-1, 1.5, 17], 'lookAt': [-1.2, .2, 0]},
                       {'t': duration*.85, 'position': [0, 2, 23], 'lookAt': [-1, 0, 0]}],
            'tracks': [{'target': 'satellite', 'property': 'position', 'easing': 'linear',
                        'keys': [{'t': 0, 'value': [-3, .2, 1]}, {'t': duration, 'value': [-1.5, .6, .5]}]},
                       {'target': 'earth', 'property': 'rotation', 'easing': 'linear',
                        'keys': [{'t': 0, 'value': [0, .7, -.2]}, {'t': duration, 'value': [0, .75, -.2]}]}],
            'overlays': overlays}


def main():
    output = ROOT / 'skills/styles/3d-motion-infographic/demo'
    output.mkdir(exist_ok=True)
    phase = {'id': 1, 'name': 'Vệ tinh Starlink trong không gian', 'duration': 28, 'caption': '',
             'narration': '', 'description': 'Minh họa 3D cho phong cách.', 'actions': []}
    script = {'title': phase['name'], 'assets': [], 'phases': [phase], 'total_duration': 28}
    (output / 'kich_ban.json').write_text(json.dumps(script, ensure_ascii=False), encoding='utf-8')
    build_preview(script, output, lambda _: json.dumps(starlink_plan()),
                  style_context=load_render_style('3d-motion-infographic'))
    sample = (output / 'phase_1.html').read_text()
    sample = sample.replace('<script src="assets/runtime/', '<script>window.pendingTime=18;</script><script src="assets/runtime/')
    (output / 'index.html').write_text(sample, encoding='utf-8')
    # The picker needs only the static sample, runtime and local fonts.
    import shutil
    for file in ('phase_1.html', 'phase_1.scene.json', 'kich_ban.json', 'assets/earth.jpg', 'assets/earth.png', 'assets/sources.json'):
        (output / file).unlink(missing_ok=True)
    shutil.rmtree(output / 'prompts', ignore_errors=True)
    print('Built 3D style demo.')


if __name__ == '__main__':
    main()
