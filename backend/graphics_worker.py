"""Worker stdout is reserved for progress; renderer logs stay on disk."""
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import plant_kurzge as planner
from generate_kurzge import build_preview
from image_asset_generator import image_config


def run(output):
    protocol = sys.stdout

    def emit(**event):
        print(json.dumps(event, ensure_ascii=False), file=protocol, flush=True)

    try:
        emit(stage='preparing')
        if not all((planner.API_URL, planner.API_KEY, planner.MODEL)):
            raise ValueError('Thiếu cấu hình CODEX_API_URL, CODEX_API_TOKEN hoặc CODEX_MODEL.')
        config = image_config()
        if not config.get('key'):
            raise ValueError('Thiếu cấu hình khóa API ảnh trên máy chủ.')
        script = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
        context = json.loads((output / 'render_config.json').read_text(encoding='utf-8'))
        with (output / 'render.log').open('a', encoding='utf-8') as log, redirect_stdout(log):
            fingerprint = build_preview(
                script, output, planner.request_text, style_context=context,
                on_progress=lambda stage, completed, total: emit(
                    stage=stage, completed=completed, total=total), resume=True)
        emit(stage='checking')
        emit(status='succeeded', fingerprint=fingerprint)
    except HTTPError as error:
        emit(status='failed', error=f'Dịch vụ AI trả HTTP {error.code}. Hãy thử tạo đồ họa lại.')
    except (URLError, TimeoutError):
        emit(status='failed', error='Không kết nối được dịch vụ AI. Hãy kiểm tra máy chủ và thử lại.')
    except OSError:
        emit(status='failed', error='Không thể đọc hoặc lưu dữ liệu đồ họa trên máy chủ.')
    except ValueError as error:
        emit(status='failed', error=str(error))
    except Exception:
        emit(status='failed', error='Không thể dựng đồ họa. Hãy kiểm tra cấu hình và thử lại.')


if __name__ == '__main__':
    run(Path(sys.argv[1]))
