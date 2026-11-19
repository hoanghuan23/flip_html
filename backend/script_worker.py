"""Private worker protocol: stage/terminal JSON lines, never credentials."""
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import plant_kurzge as planner
from .scripts import project_script, validate_for_ui


def emit(**event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def run(directory):
    try:
        if not all((planner.API_URL, planner.API_KEY, planner.MODEL)):
            raise ValueError('Thiếu cấu hình CODEX_API_URL, CODEX_API_TOKEN hoặc CODEX_MODEL trên máy chủ.')
        content = (directory / 'input.txt').read_text(encoding='utf-8')
        script = planner.generate_script(
            content, on_stage=lambda stage: emit(stage=stage), extra_validate=validate_for_ui,
        )
        project_script(script)
        emit(stage='saving')
        temporary = directory / 'kich_ban.tmp'
        temporary.write_text(json.dumps(script, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                             encoding='utf-8')
        temporary.replace(directory / 'kich_ban.json')
        emit(status='succeeded')
    except planner.InputRejectedError as error:
        emit(status='rejected', error=str(error))
    except HTTPError as error:
        emit(status='failed', error=f'Dịch vụ AI trả HTTP {error.code}. Hãy thử lại.')
    except (URLError, TimeoutError):
        emit(status='failed', error='Không kết nối được dịch vụ AI. Hãy kiểm tra kết nối máy chủ và thử lại.')
    except OSError:
        emit(status='failed', error='Không thể đọc hoặc lưu file kịch bản trên máy chủ.')
    except ValueError as error:
        emit(status='failed', error=str(error))
    except Exception:
        emit(status='failed', error='Không thể tạo kịch bản. Hãy kiểm tra cấu hình dịch vụ AI.')


if __name__ == '__main__':
    run(Path(sys.argv[1]))
