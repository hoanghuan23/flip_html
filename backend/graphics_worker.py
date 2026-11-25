"""Worker stdout is reserved for progress; renderer logs stay on disk."""
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import traceback
from urllib.error import HTTPError, URLError

import plant_kurzge as planner
from generate_kurzge import build_preview
from image_asset_generator import image_config


def run(output, mode='complete'):
    protocol = sys.stdout

    def emit(**event):
        print(json.dumps(event, ensure_ascii=False), file=protocol, flush=True)

    def fail(message):
        traceback.print_exc(file=sys.stderr)
        emit(status='failed', error=message)

    try:
        emit(stage='preparing')
        if mode != 'stills' and not all((planner.API_URL, planner.API_KEY, planner.MODEL)):
            config_path = output / 'render_config.json'
            if not config_path.is_file() or json.loads(config_path.read_text(encoding='utf-8')).get('id') != 'map-2d':
                raise ValueError('Thiếu cấu hình CODEX_API_URL, CODEX_API_TOKEN hoặc CODEX_MODEL.')
        script = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
        context = json.loads((output / 'render_config.json').read_text(encoding='utf-8'))
        is_three = context['id'] == '3d-motion-infographic'
        is_map = context['id'] == 'map-2d' and context.get('template', {}).get('id') == 'map'
        if not is_three and not is_map and not image_config().get('key'):
            raise ValueError('Thiếu cấu hình khóa API ảnh trên máy chủ.')
        progress = lambda stage, completed, total: emit(stage=stage, completed=completed, total=total)
        with (output / 'render.log').open('a', encoding='utf-8') as log, redirect_stdout(log):
            if mode == 'stills':
                if is_map:
                    from map_renderer import build_map_stills
                    build_map_stills(script, output, context, planner.request_text, progress)
                else:
                    from .still_previews import build_stills
                    build_stills(script, output, context, progress)
                emit(status='succeeded')
                return
            from .narration import prepare_narration
            if any(phase.get('voiceover') for phase in script['phases']):
                prepare_narration(script, output, output.parent.parent / 'audio_cache', progress)
                emit(stage='synchronizing')
                temporary = output / 'kich_ban.tmp'
                temporary.write_text(json.dumps(script, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
                temporary.replace(output / 'kich_ban.json')
            if is_map:
                from map_renderer import build_map_preview
                fingerprint = build_map_preview(script, output, context, planner.request_text, progress)
            elif is_three:
                from three_motion import build_preview as build_three
                fingerprint = build_three(script, output, planner.request_text, style_context=context,
                                          on_progress=progress)
            else:
                fingerprint = build_preview(script, output, planner.request_text, style_context=context,
                                            on_progress=progress, resume=True)
        emit(stage='checking')
        emit(status='succeeded', fingerprint=fingerprint)
    except HTTPError as error:
        fail(f'Dịch vụ AI trả HTTP {error.code}. Hãy thử tạo đồ họa lại.')
    except (URLError, TimeoutError):
        fail('Không kết nối được dịch vụ AI. Hãy kiểm tra máy chủ và thử lại.')
    except OSError:
        fail('Không thể đọc hoặc lưu dữ liệu đồ họa trên máy chủ.')
    except ValueError as error:
        fail(str(error))
    except Exception:
        fail('Không thể dựng đồ họa. Hãy kiểm tra cấu hình và thử lại.')


if __name__ == '__main__':
    run(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'complete')
