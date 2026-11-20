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
        from .inputs import split_input, attach_voiceover, requested_labels
        visual, voiceover = split_input(content)
        references_path = directory / 'references.json'
        references = json.loads(references_path.read_text()) if references_path.exists() else []
        def validate_script(value):
            if voiceover:
                try:
                    attach_voiceover(value, voiceover)
                except ValueError as error:
                    return [str(error)]
            errors = validate_for_ui(value)
            for label in requested_labels(visual):
                if not any(label in phase.get('description', '') for phase in value['phases']):
                    errors.append('Giữ nguyên nhãn trong description của cảnh tương ứng, kể cả dấu ngoặc kép: "' + label + '".')
            return errors
        extra = ''
        if voiceover:
            extra += ('\nNARRATED INPUT: The user supplies the exact spoken script below. '
                      'Preserve explicitly requested on-screen labels VERBATIM, in quotation marks, '
                      'in the description of the relevant phase. '
                      'Add voiceover to each phase: partition ALL of this text into nonempty consecutive '
                      'segments, preserving every word and punctuation in order. Never rewrite, summarize '
                      'or omit speech. Use fewer phases if necessary. narration is only a SHORT script note, '
                      'never the spoken paragraph or an on-screen subtitle. Do not reserve a bottom caption strip. '
                      'Keep each spoken segment below 1000 characters. '
                      'Actions may include cue: an exact short phrase from that phase voiceover, '
                      'to anchor action start to speech. Durations are provisional until TTS.\nVOICEOVER:\n' + voiceover)
        if references:
            extra += '\nREFERENCE IMAGES (keep exact number and id):\n' + json.dumps(references, ensure_ascii=False)
        script = planner.generate_script(
            (visual or voiceover) if voiceover else content, on_stage=lambda stage: emit(stage=stage),
            extra_validate=validate_script,
            **({'prompt_suffix': extra} if extra else {}),
            **({'validation_text': visual + '\n' + voiceover} if voiceover else {}),
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
