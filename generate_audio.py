"""Tạo thuyết minh VieNeu từ kịch bản JSON, lưu WAV và timeline đã đồng bộ."""
import argparse
import json
import os
from pathlib import Path
import sys

from backend.narration import prepare_narration
from backend.scripts import validate_for_ui
from plant_kurzge import ROOT, validate_generated


def generate_audio(source, output, cache, *, overwrite=False, on_progress=None):
    target = output / 'kich_ban.json'
    if source.resolve() == target.resolve():
        raise ValueError('Chọn thư mục output khác để giữ nguyên kịch bản nguồn.')
    if target.exists() and not overwrite:
        raise ValueError('Kịch bản output đã tồn tại. Dùng --overwrite để tạo lại.')
    script = json.loads(source.read_text(encoding='utf-8'))
    errors = validate_generated(script)
    if not errors:
        errors = validate_for_ui(script)
    if errors:
        raise ValueError('Kịch bản không hợp lệ: ' + '; '.join(errors))
    if not any((phase.get('voiceover') or '').strip() for phase in script['phases']):
        raise ValueError('Kịch bản chưa có voiceover. Hãy bổ sung lời đọc cho các cảnh.')
    output.mkdir(parents=True, exist_ok=True)
    prepare_narration(script, output, cache, on_progress)
    temporary = target.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(script, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                             encoding='utf-8')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='File kich_ban.json có voiceover.')
    parser.add_argument('--output', type=Path, required=True, help='Thư mục lưu audio và kịch bản đã đồng bộ.')
    parser.add_argument('--cache', type=Path,
                        default=Path(os.environ.get('VIDEO_STORAGE_DIR', ROOT / 'storage')) / 'audio_cache',
                        help='Cache WAV dùng lại giữa các lần chạy (mặc định storage/audio_cache).')
    parser.add_argument('--overwrite', action='store_true', help='Thay kịch bản đã tạo trong output.')
    args = parser.parse_args(argv)

    def progress(_stage, completed, total):
        print(f'VieNeu {completed}/{total}', file=sys.stderr, flush=True)

    target = generate_audio(args.input, args.output, args.cache,
                            overwrite=args.overwrite, on_progress=progress)
    print(f'Đã lưu thuyết minh và kịch bản: {target}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f'Lỗi: {error}')
