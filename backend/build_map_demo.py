"""Build a reviewable map HTML preview from a detailed script without the AI/TTS services.

Usage: python -m backend.build_map_demo --script plan.md --images travel_images
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid

from script_analysis import parse_detailed, speech_seconds
from plant_kurzge import validate_generated
from render_style import load_render_style, load_render_template
from .illustrations import attach_events, validate_events
from .narration import prepare_narration
from map_renderer import build_map_preview, build_map_stills, verify_map_phases


def build(script_path, images_path, output):
    sources = parse_detailed(script_path.read_text(encoding='utf-8'))
    if not sources:
        raise ValueError('Cần kịch bản chi tiết có Hoạt ảnh và Lời đọc cho từng cảnh.')
    output.mkdir(parents=True, exist_ok=True)
    destination = output / 'assets' / 'illustrations'
    destination.mkdir(parents=True, exist_ok=True)
    references = []
    for number in sorted({int(match) for source in sources for match in
                          re.findall(r'@image_([1-9][0-9]*)\b', source['animation'])}):
        options = list(images_path.glob(f'image_{number}.*'))
        if len(options) != 1 or options[0].suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            raise ValueError(f'Cần đúng một tệp image_{number}.jpg/png/webp trong {images_path}.')
        source = options[0]
        filename = f'image_{number}{source.suffix.lower()}'
        target = destination / filename
        shutil.copy2(source, target)
        references.append({'number': number, 'kind': 'illustration', 'name': f'image_{number}',
                           'filename': source.name, 'src': f'assets/illustrations/{filename}',
                           'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    phases = []
    for index, source in enumerate(sources, 1):
        duration = min(120, max(5, round(speech_seconds(source['voiceover']) + 1, 2)))
        phases.append({'id': index, 'name': source['name'], 'description': source['animation'],
                       'voiceover': source['voiceover'], 'duration': duration,
                       'narration': '', 'caption': '', 'annotations': [], 'duration_status': 'estimated',
                       'initial_state': 'Tiếp tục từ cảnh trước trên cùng bản đồ.',
                       'final_state': 'Chuyển tiếp tự nhiên sang cảnh sau.', 'added': False,
                       'camera': {'view': 'top-down', 'motion': 'pan', 'detail': source['animation']},
                       'actions': [{'target': 'CAR', 'type': 'move', 'from': {}, 'to': {},
                                    'start': 0, 'end': duration, 'easing': 'linear', 'note': source['animation']}],
                       'sound': '', 'branch_from': None})
    script = {'title': script_path.stem, 'input_type': 'detailed_script',
              'research': {'status': 'not_required', 'sources': []}, 'warnings': [],
              'style': {'palette': {}, 'font': '', 'notes': ''},
              'assets': [{'id': 'CAR', 'category': 'object', 'name': 'Phương tiện',
                          'description': 'Nhận diện lấy từ kịch bản.'}],
              'phases': phases, 'total_duration': round(sum(p['duration'] for p in phases), 2)}
    attach_events(script, sources, references)
    validate_events(script, references)
    errors = validate_generated(script)
    if errors:
        raise ValueError('; '.join(errors))
    context = load_render_style('map-2d')
    context['template'] = load_render_template('map')
    (output / 'kich_ban.json').write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'references.json').write_text(json.dumps(references, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'render_config.json').write_text(json.dumps(context, ensure_ascii=False), encoding='utf-8')
    build_map_stills(script, output, context, None, lambda *_: None)
    revision = build_map_preview(script, output, context, None, lambda *_: None)
    snapshot = {'id': output.name, 'revision': revision, 'renderer': 'map-motion-v1',
                'demoNoAudio': True, 'duration': script['total_duration'], 'width': 1920,
                'height': 1080, 'phases': verify_map_phases(output, script, revision)}
    (output / 'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    return snapshot


def refresh_existing(output):
    """Rebuild HTML after a renderer change while keeping the screenplay and WAV files."""
    script = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
    context = json.loads((output / 'render_config.json').read_text(encoding='utf-8'))
    snapshot = json.loads((output / 'snapshot.json').read_text(encoding='utf-8'))
    if snapshot.get('renderer') != 'map-motion-v1':
        raise ValueError('Thư mục này không phải preview bản đồ.')
    revision = build_map_preview(script, output, context, None, lambda *_: None)
    phases = verify_map_phases(output, script, revision)
    for row, phase in zip(phases, script['phases']):
        if phase.get('audio'):
            audio = phase['audio']
            row['audio'] = {'url': f"/api/previews/{output.name}/{audio['src']}",
                            'duration': audio['duration']}
    snapshot.update(revision=revision, duration=script['total_duration'], phases=phases,
                    demoNoAudio=not all(phase.get('audio') for phase in script['phases']))
    temporary = output / 'snapshot.tmp'
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(output / 'snapshot.json')
    return snapshot


def narrate_existing(output):
    """Add VieNeu narration to an existing map demo and republish its seekable index."""
    script = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
    prepare_narration(script, output, output.parent.parent / 'audio_cache',
                      lambda _stage, completed, total: print(f'VieNeu {completed}/{total}', flush=True))
    temporary = output / 'kich_ban.tmp'
    temporary.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(output / 'kich_ban.json')
    return refresh_existing(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=Path('plan.md'))
    parser.add_argument('--images', type=Path, default=Path('travel_images'))
    parser.add_argument('--output', type=Path, default=Path('storage/previews') / uuid.uuid4().hex)
    parser.add_argument('--narrate-existing', type=Path,
                        help='Thêm VieNeu audio vào preview bản đồ đã dựng, không tạo preview mới.')
    parser.add_argument('--refresh-existing', type=Path,
                        help='Dựng lại HTML của preview hiện có, giữ nguyên WAV và kịch bản.')
    args = parser.parse_args()
    if args.narrate_existing and args.refresh_existing:
        parser.error('Chỉ chọn một trong --narrate-existing và --refresh-existing.')
    if args.refresh_existing:
        args.output = args.refresh_existing
        result = refresh_existing(args.output)
    elif args.narrate_existing:
        args.output = args.narrate_existing
        result = narrate_existing(args.output)
    else:
        result = build(args.script, args.images, args.output)
    audio_state = 'không có audio' if result.get('demoNoAudio') else 'VieNeu audio'
    print(f"{args.output.resolve() / 'index.html'} ({len(result['phases'])} phase, {audio_state})")


if __name__ == '__main__':
    main()
