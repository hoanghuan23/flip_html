"""Stoppable preview/animation worker; JSON protocol stays separate from logs."""
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import traceback
from urllib.error import HTTPError, URLError

import plant_kurzge as planner
from generate_kurzge import build_preview
from token_usage import collect_usage


def run(output, mode='complete'):
    protocol = sys.stdout

    def emit(**event):
        print(json.dumps(event, ensure_ascii=False), file=protocol, flush=True)

    try:
        if mode not in ('stills', 'complete'):
            raise ValueError('Chế độ dựng không hợp lệ.')
        emit(stage='preparing')
        script = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
        context = json.loads((output / 'render_config.json').read_text(encoding='utf-8'))
        progress = lambda stage, completed, total: emit(stage=stage, completed=completed, total=total)
        with collect_usage(output, 'graphics' if mode == 'stills' else 'animation', emit,
                           phase_ids=[phase['id'] for phase in script['phases']]), \
                (output / 'render.log').open('a', encoding='utf-8') as log, redirect_stdout(log):
            if mode == 'stills':
                from .still_previews import build_stills
                build_stills(script, output, context, progress)
                emit(status='succeeded')
                return
            if not all((planner.API_URL, planner.API_KEY, planner.MODEL)):
                raise ValueError('Thiếu CODEX_API_URL, CODEX_API_TOKEN hoặc CODEX_MODEL.')
            fingerprint = build_preview(script, output, planner.request_text,
                                        style_context=context, on_progress=progress, resume=True)
        emit(stage='checking')
        emit(status='succeeded', fingerprint=fingerprint)
    except HTTPError as error:
        traceback.print_exc(file=sys.stderr)
        emit(status='failed', error=f'Dịch vụ AI trả HTTP {error.code}. Hãy thử lại.')
    except (URLError, TimeoutError):
        traceback.print_exc(file=sys.stderr)
        emit(status='failed', error='Không kết nối được dịch vụ AI. Hãy kiểm tra máy chủ.')
    except (OSError, ValueError) as error:
        traceback.print_exc(file=sys.stderr)
        emit(status='failed', error=str(error) if isinstance(error, ValueError) else 'Không đọc hoặc lưu được đồ họa.')
    except Exception:
        traceback.print_exc(file=sys.stderr)
        emit(status='failed', error='Không thể dựng đồ họa. Hãy kiểm tra worker.log và thử lại.')


if __name__ == '__main__':
    run(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'complete')
