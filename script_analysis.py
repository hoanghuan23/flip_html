"""Text-only screenplay parsing, review metadata and provisional timing."""
import math
import os
import re
from urllib.parse import urlsplit


class InputRejectedError(ValueError):
    """The user needs to supply or clarify content, rather than retry an API."""


PHASE_HEADER = re.compile(
    r'(?im)^[ \t]*(?:#{1,6}[ \t]+)?(?:[-+*][ \t]+)?(?:\*\*)?'
    r'(?:phase|cảnh|phần)[ \t]+(?:\d+|[ivxlcdm]+)\b[^\r\n]*')
SECTION = re.compile(
    r'(?im)^[ \t]*(?:#{1,6}[ \t]+)?(?:[-+*][ \t]+)?(?:\*\*)?'
    r'(hoạt ảnh|mô tả|audio|thuyết minh|lời đọc)(?:\*\*)?[ \t]*[:：](?:\*\*)?[ \t]*')
IMAGE_MENTION = re.compile(r'(?i)\b(?:ảnh|hình)[ \t]+(?:\d+|này|đính kèm|tham chiếu)\b')
IMAGE_WARNING = 'Chỉ dẫn ảnh chưa được thực hiện: hệ thống chỉ phân tích văn bản, không nhận hoặc xem ảnh input.'
UNVERIFIED_WARNING = 'Nội dung chưa được kiểm chứng bằng nguồn web; hãy kiểm tra trước khi dựng video.'


def parse_detailed(text):
    """Recognized headings lock phase boundaries before any model call."""
    headers = list(PHASE_HEADER.finditer(text))
    if not headers:
        return []
    phases = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[header.end():end]
        markers = list(SECTION.finditer(body))
        sections = {}
        for j, marker in enumerate(markers):
            key = 'animation' if marker[1].casefold() in ('hoạt ảnh', 'mô tả') else 'voiceover'
            if key in sections:
                raise InputRejectedError(f'Phase {index + 1}: có nhiều phần {key}, hãy làm rõ ranh giới.')
            sections[key] = body[marker.end():markers[j + 1].start() if j + 1 < len(markers) else len(body)].strip()
        for key, label in [('animation', 'Hoạt ảnh/Mô tả'), ('voiceover', 'Audio/Thuyết minh/Lời đọc')]:
            if not sections.get(key):
                raise InputRejectedError(f'Phase {index + 1}: cần bổ sung phần {label}.')
        # Text before the first section must not be silently dropped.
        if markers and body[:markers[0].start()].strip():
            sections['animation'] = body[:markers[0].start()].strip() + '\n' + sections['animation']
        heading = re.sub(r'^[ \t]*(?:#{1,6}[ \t]+)?(?:[-+*][ \t]+)?', '', header[0])
        heading = heading.replace('**', '').strip()
        title = re.sub(r'(?i)^(?:phase|cảnh|phần)\s+(?:\d+|[ivxlcdm]+)\b[ \t]*[:：.\-–—]?[ \t]*', '', heading).strip()
        phases.append({**sections, 'name': title, 'heading': heading, 'block': text[header.start():end]})
    if len(phases) > 100:
        raise InputRejectedError('Kịch bản có hơn 100 phase. Hãy rút gọn trước khi tạo.')
    return phases


def speech_seconds(text):
    try:
        rate = float(os.getenv('SCRIPT_SPEECH_UNITS_PER_MINUTE', '210'))
    except ValueError as error:
        raise ValueError('SCRIPT_SPEECH_UNITS_PER_MINUTE phải là số dương hữu hạn.') from error
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError('SCRIPT_SPEECH_UNITS_PER_MINUTE phải là số dương hữu hạn.')
    return (len(text.split()) * 60 / rate + len(re.findall(r'[,;:]', text)) * .15
            + len(re.findall(r'[.!?…]+|\n+', text)) * .3)


def check_source_limits(sources):
    for index, source in enumerate(sources, 1):
        if len(source['name']) > 160:
            raise InputRejectedError(f'Phase {index}: tên dài hơn 160 ký tự. Hãy rút gọn tên phase.')
        if len(source['voiceover']) > 10000 or speech_seconds(source['voiceover']) > 120:
            raise InputRejectedError(f'Phase {index}: audio vượt giới hạn 10.000 ký tự hoặc 120 giây ước tính. Hãy sửa phase; hệ thống không tự chia hoặc cắt lời đọc.')
    if sum(speech_seconds(s['voiceover']) for s in sources) > 1800:
        raise InputRejectedError('Tổng audio ước tính vượt 30 phút. Hãy rút gọn kịch bản.')


def safe_source_url(value):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return url.scheme in ('http', 'https') and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


def review_errors(script):
    """Optional metadata stays readable in legacy JSON; new metadata is checked."""
    errors = []
    kind = script.get('input_type')
    if kind is not None and kind not in ('topic', 'detailed_script', 'legacy'):
        errors.append('input_type không hợp lệ.')
    warnings = script.get('warnings', [])
    if not isinstance(warnings, list) or any(not isinstance(w, str) or not w.strip() for w in warnings):
        errors.append('warnings phải là danh sách chuỗi có nội dung.')
    research = script.get('research')
    if research is not None:
        if not isinstance(research, dict) or research.get('status') not in ('sources_reported', 'unverified', 'not_required'):
            errors.append('research.status không hợp lệ.')
        else:
            sources = research.get('sources')
            if not isinstance(sources, list):
                errors.append('research.sources phải là danh sách.')
            else:
                for source in sources:
                    if (not isinstance(source, dict) or not isinstance(source.get('title'), str)
                            or not source['title'].strip() or not safe_source_url(source.get('url'))
                            or not isinstance(source.get('claims'), list) or not source['claims']
                            or any(not isinstance(c, str) or not c.strip() for c in source['claims'])):
                        errors.append('Nguồn cần title, URL HTTP/HTTPS và claims có nội dung.')
                if research['status'] == 'sources_reported' and not sources:
                    errors.append('sources_reported cần ít nhất một nguồn.')
                if research['status'] != 'sources_reported' and sources:
                    errors.append('Nguồn web chỉ được lưu với trạng thái sources_reported.')
    assets = script.get('assets', [])
    asset_ids = {a['id'] for a in assets if isinstance(a, dict) and isinstance(a.get('id'), str)} if isinstance(assets, list) else set()
    for index, phase in enumerate(script.get('phases', []) if isinstance(script.get('phases'), list) else [], 1):
        if not isinstance(phase, dict):
            continue
        if kind in ('topic', 'detailed_script'):
            if not isinstance(phase.get('voiceover'), str) or not phase['voiceover'].strip() or len(phase['voiceover']) > 10000:
                errors.append(f'Phase {index}: cần voiceover có nội dung, tối đa 10.000 ký tự.')
            if 'annotations' not in phase:
                errors.append(f'Phase {index}: cần annotations (có thể rỗng).')
            if phase.get('duration_status') != 'estimated':
                errors.append(f'Phase {index}: duration_status phải là estimated.')
        elif 'duration_status' in phase and phase['duration_status'] != 'estimated':
            errors.append(f'Phase {index}: duration_status không hợp lệ.')
        notes = phase.get('annotations', [])
        if not isinstance(notes, list):
            errors.append(f'Phase {index}: annotations phải là danh sách.')
            continue
        actions = phase.get('actions', [])
        for note in notes:
            if not isinstance(note, dict):
                errors.append(f'Phase {index}: chú giải phải là object.')
                continue
            if not isinstance(note.get('text'), str) or not note['text'].strip() or len(note['text']) > 200:
                errors.append(f'Phase {index}: chú giải cần text ngắn, tối đa 200 ký tự.')
            if not isinstance(note.get('target'), str) or note['target'] not in asset_ids:
                errors.append(f'Phase {index}: target chú giải không tồn tại.')
            action = note.get('action_index')
            if action is not None and (type(action) is not int or not isinstance(actions, list) or not 0 <= action < len(actions)):
                errors.append(f'Phase {index}: action_index chú giải không tồn tại (đếm từ 0).')
            cue = note.get('cue')
            speech = phase.get('voiceover')
            if cue is not None and (not isinstance(cue, str) or not cue.strip() or not isinstance(speech, str) or cue not in speech):
                errors.append(f'Phase {index}: cue phải có nguyên văn trong voiceover của phase.')
    if kind is not None:
        phases = script.get('phases')
        for container in [script, *(p for p in phases if isinstance(p, dict))] if isinstance(phases, list) else [script]:
            if any(k in container for k in ('image_refs', 'referenceImages', 'reference_images', 'references')):
                errors.append('Kịch bản mới chỉ nhận văn bản, không khai báo tham chiếu ảnh input.')
    return errors


def normalize_cues(script):
    """Unmatched optional speech cues fall back to the existing visual timeline."""
    for phase in script['phases']:
        speech = phase.get('voiceover')
        for key in ('annotations', 'actions'):
            items = phase.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or 'cue' not in item:
                    continue
                cue = item['cue']
                if not isinstance(cue, str) or not cue.strip() or not isinstance(speech, str):
                    item.pop('cue')
                    continue
                if cue in speech:
                    continue
                # Restore source spelling when only case or whitespace differs.
                pattern = r'\s+'.join(re.escape(word) for word in cue.split())
                match = re.search(pattern, speech, re.IGNORECASE)
                if match:
                    item['cue'] = match[0]
                else:
                    item.pop('cue')


def normalize_timing(script):
    for phase in script['phases']:
        speech = speech_seconds(phase['voiceover'])
        # Existing action times describe the visual timeline. Never shrink it.
        visual = max(phase['duration'], max(a['end'] for a in phase['actions']))
        labels = ' '.join(n['text'] for n in phase['annotations'])
        reading = len(labels.split()) * 60 / 210 + (.5 if labels else 0)
        phase['duration'] = math.ceil(max(speech, visual, reading) * 100) / 100
        phase['duration_status'] = 'estimated'
    script['total_duration'] = round(math.fsum(p['duration'] for p in script['phases']), 2)


def limit_errors(script):
    errors = []
    if len(script['phases']) > 100:
        errors.append('Kịch bản hỗ trợ tối đa 100 phase.')
    for index, phase in enumerate(script['phases'], 1):
        if phase['duration'] > 120:
            errors.append(f'Phase {index}: thời lượng ước tính vượt 120 giây. Hãy rút gọn nội dung; không tự chia phase chi tiết.')
    if script['total_duration'] > 1800:
        errors.append('Tổng thời lượng vượt 30 phút.')
    return errors


def split_input(text):
    marker = re.compile(r'(?im)^\s*(?:\*\*)?(Mô tả|Thuyết minh)\s*:(?:\*\*)?[ \t]*')
    matches = list(marker.finditer(text))
    if not any(m[1].casefold() == 'thuyết minh' for m in matches):
        return text, ''
    visual = [text[:matches[0].start()].strip()]
    voices = []
    for index, match in enumerate(matches):
        section = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)].strip()
        if match[1].casefold() == 'thuyết minh':
            if len(section) >= 2 and (section[0], section[-1]) in [('"', '"'), ('“', '”')]:
                section = section[1:-1]
            if not section.strip():
                raise ValueError('Phần Thuyết minh đang trống.')
            voices.append(section)
        else:
            visual.append(section)
    return '\n\n'.join(s for s in visual if s), '\n\n'.join(voices)


def attach_voiceover(script, original):
    """AI selects boundaries; the source characters are copied, never regenerated."""
    cursor = 0
    for phase in script['phases']:
        piece = phase.get('voiceover')
        if not isinstance(piece, str) or not piece.strip():
            raise ValueError('Mỗi cảnh cần voiceover là một đoạn liên tiếp từ lời đọc gốc.')
        if len(piece) > 1000:
            raise ValueError('Hãy chia lời đọc thành các cảnh, mỗi voiceover tối đa 1000 ký tự.')
        words = re.findall(r'\S+', piece)
        pattern = r'\s*' + r'\s+'.join(re.escape(w) for w in words)
        match = re.match(pattern, original[cursor:])
        if not match or (cursor + match.end() < len(original) and not original[cursor + match.end()].isspace()):
            raise ValueError('voiceover phải giữ nguyên toàn bộ lời đọc theo đúng thứ tự, không viết lại.')
        phase['voiceover'] = original[cursor:cursor + match.end()]
        cursor += match.end()
    if original[cursor:].strip():
        raise ValueError('Kịch bản bỏ sót phần cuối lời thuyết minh.')
    script['phases'][-1]['voiceover'] += original[cursor:]
    script['voiceoverText'] = original


def requested_labels(text):
    return re.findall(r'(?i)(?:dòng chữ|nhãn|chú thích)\s*[:：]?\s*(?:\*\*)?["“]([^"”]+)["”]', text)
