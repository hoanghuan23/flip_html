"""Lossless narration sections and validated, numbered reference images."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re

from PIL import Image
from pydantic import BaseModel, Field, field_validator


class ReferenceImage(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    number: int = Field(gt=0, strict=True)
    dataUrl: str = Field(max_length=7 * 1024 * 1024)

    @field_validator('dataUrl')
    @classmethod
    def valid_image(cls, value):
        match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})', value)
        if not match:
            raise ValueError('Ảnh tham chiếu phải là PNG, JPG hoặc WEBP base64.')
        try:
            raw = base64.b64decode(match[2], validate=True)
            if len(raw) > 5 * 1024 * 1024:
                raise ValueError('Ảnh tham chiếu vượt quá 5 MB.')
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != {'png': 'PNG', 'jpeg': 'JPEG', 'webp': 'WEBP'}[match[1]]:
                    raise ValueError('Định dạng ảnh không khớp dữ liệu.')
                if image.width * image.height > 20_000_000:
                    raise ValueError('Ảnh tham chiếu có kích thước quá lớn.')
                image.verify()
        except Exception as error:
            raise ValueError('Ảnh tham chiếu không hợp lệ hoặc quá lớn.') from error
        return value


def validate_references(images):
    for key in ('id', 'number'):
        if len({getattr(image, key) for image in images}) != len(images):
            raise ValueError('ID và số hình tham chiếu phải khác nhau.')
    return images


def reference_signature(images):
    # FNV-1a over the ASCII data URL, shared with the synchronous UI signature.
    rows = []
    for image in images:
        row = image.model_dump() if isinstance(image, ReferenceImage) else image
        checksum = 2166136261
        for char in row['dataUrl']:
            checksum = ((checksum ^ ord(char)) * 16777619) & 0xffffffff
        rows.append({'id': row['id'], 'name': row['name'], 'number': row['number'],
                     'checksum': format(checksum, '08x')})
    return rows


def save_references(directory: Path, images):
    assets = directory / 'assets' / 'references'
    assets.mkdir(parents=True, exist_ok=True)
    rows = []
    for image in images:
        row = image.model_dump() if isinstance(image, ReferenceImage) else image
        header, encoded = row['dataUrl'].split(',', 1)
        raw = base64.b64decode(encoded, validate=True)
        extension = header.split('/')[1].split(';')[0]
        digest = hashlib.sha256(raw).hexdigest()
        path = assets / f'{digest}.{extension}'
        path.write_bytes(raw)
        rows.append({'id': row['id'], 'name': row['name'], 'number': row['number'],
                     'src': path.relative_to(directory).as_posix(), 'sha256': digest})
    (directory / 'references.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    return rows


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


def check_image_mentions(text, images):
    available = {image.number if isinstance(image, ReferenceImage) else image['number'] for image in images}
    mentioned = {int(n) for n in re.findall(r'(?i)\bhình\s+(\d+)\b', text)}
    missing = mentioned - available
    if missing:
        raise ValueError('Thiếu ảnh tham chiếu: ' + ', '.join(f'Hình {n}' for n in sorted(missing)) + '.')


def requested_labels(text):
    return re.findall(r'(?i)(?:dòng chữ|nhãn|chú thích)\s*[:：]?\s*(?:\*\*)?["“]([^"”]+)["”]', text)
