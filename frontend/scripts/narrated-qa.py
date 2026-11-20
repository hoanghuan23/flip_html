"""Build two narrated 3D QA phases locally. Uses a test tone, never paid APIs."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.graphics import completed_snapshot
from backend.inputs import ReferenceImage, save_references
from render_style import load_render_style
from three_motion import build_preview


def main():
    storage = ROOT / 'storage' / 'qa' / 'narrated'
    output = storage / 'previews' / ('9' * 32)
    output.mkdir(parents=True, exist_ok=True)
    asset = output / 'assets/audio'
    asset.mkdir(parents=True, exist_ok=True)
    audio = asset / ('1' * 64 + '.mp3')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=3.9',
                    '-codec:a', 'libmp3lame', str(audio)], check=True)
    from backend.narration import probe_audio
    seconds = probe_audio(audio)
    import math
    duration = math.ceil(seconds * 30) / 30
    text = 'Vệ tinh Starlink ở độ cao khoảng 550 km.'
    alignment = {'characters': list(text),
                 'character_start_times_seconds': [i/len(text)*3.8 for i in range(len(text))],
                 'character_end_times_seconds': [(i+1)/len(text)*3.8 for i in range(len(text))]}
    audio.with_suffix('.json').write_text(json.dumps({'alignment': alignment}))
    phase = {'id': 1, 'name': 'Starlink · kiểm thử 1', 'duration': duration, 'branch_from': None,
             'caption': '', 'narration': '', 'voiceover': text,
             'description': 'Vệ tinh và Trái Đất. Hiện Hình 7 trong khung ảnh bên phải.',
             'camera': {'view': 'side', 'motion': 'zoom', 'detail': 'Tiến gần rồi lùi ra.'},
             'initial_state': 'Góc tổng quan.', 'final_state': 'Vệ tinh tiếp tục di chuyển.',
             'actions': [{'target': 'SATELLITE', 'type': 'move', 'from': {'x': -3}, 'to': {'x': -1.5},
                          'start': 0, 'end': duration}],
             'audio': {'src': audio.relative_to(output).as_posix(), 'duration': seconds,
                       'alignment': audio.with_suffix('.json').relative_to(output).as_posix(),
                       'sha256': hashlib.sha256(audio.read_bytes()).hexdigest()}}
    second = copy.deepcopy(phase)
    second.update(id=2, name='Starlink · kiểm thử 2')
    script = {'title': 'Kiểm thử 3D và audio', 'total_duration': duration * 2,
              'assets': [{'id': 'SATELLITE', 'category': 'object', 'name': 'Vệ tinh', 'description': 'Thân và pin mặt trời.'}],
              'phases': [phase, second]}
    image = ROOT / 'skills/3d-motion-infographic/assets/earth.jpg'
    refs = save_references(output, [ReferenceImage(id='qa-image-7', name='Ảnh kiểm thử số 7.jpg', number=7,
                                  dataUrl='data:image/jpeg;base64,' + base64.b64encode(image.read_bytes()).decode())])
    context = load_render_style('3d-motion-infographic')
    (output / 'kich_ban.json').write_text(json.dumps(script, ensure_ascii=False))
    (output / 'render_config.json').write_text(json.dumps(context, ensure_ascii=False))
    plan = runpy.run_path(str(ROOT / 'skills/3d-motion-infographic/scripts/build_demo.py'))['starlink_plan'](duration, 7)
    plan['overlays'][-1]['text'] = 'Ảnh kiểm thử · Hình 7'
    fingerprint = build_preview(script, output, lambda _: json.dumps(plan), style_context=context, references=refs)
    config = {'projectId': 'narrated-qa', 'scriptId': 'a'*32, 'categoryId': 'all_styles', 'styleId': context['id']}
    snapshot = completed_snapshot(storage, {'id': output.name, 'config': config}, fingerprint)
    project = {'id': config['projectId'], 'title': script['title'], 'sourceContent': 'Dữ liệu QA: audio là tín hiệu thử.',
               **{k: config[k] for k in ('scriptId', 'categoryId', 'styleId')}, 'snapshot': snapshot,
               'scenes': [{k: str(p[k]) if k == 'id' else p[k] for k in
                           ('id', 'name', 'narration', 'voiceover', 'description', 'duration')} for p in script['phases']],
               'messages': [], 'updatedAt': '2026-11-20T00:00:00Z'}
    directory = storage / 'qa'
    directory.mkdir(exist_ok=True)
    (directory / 'narrated-project.json').write_text(json.dumps(project, ensure_ascii=False))
    print('Built narrated QA fixture (two phases, image #7, synthetic test tone).')


if __name__ == '__main__':
    main()
