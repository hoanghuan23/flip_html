"""Lossless narration sections and requested text labels."""
import re


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
