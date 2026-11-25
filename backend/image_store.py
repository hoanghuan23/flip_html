"""Persist uploaded illustration images independently of browser thumbnails."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import uuid

from PIL import Image
from pydantic import BaseModel, Field, field_validator


PROJECT = r'^[a-zA-Z0-9_-]{1,100}$'
IMAGE_ID = r'^[a-f0-9]{32}$'
KINDS = {'reference', 'illustration'}
MIME = {'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 100


class ImageUpload(BaseModel):
    projectId: str = Field(pattern=PROJECT)
    number: int = Field(gt=0, le=10000)
    kind: str
    filename: str = Field(min_length=1, max_length=255)
    dataUrl: str = Field(min_length=32, max_length=MAX_IMAGE_BYTES * 4 // 3 + 128)

    @field_validator('kind')
    @classmethod
    def check_kind(cls, value):
        if value not in KINDS:
            raise ValueError('Loại ảnh không hợp lệ.')
        return value


class ImageBinding(BaseModel):
    number: int = Field(gt=0, le=10000)
    kind: str
    imageId: str = Field(pattern=IMAGE_ID)

    @field_validator('kind')
    @classmethod
    def check_kind(cls, value):
        if value not in KINDS:
            raise ValueError('Loại ảnh không hợp lệ.')
        return value


def decode_image(data_url):
    match = re.fullmatch(r'data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/]+={0,2})', data_url)
    if not match:
        raise ValueError('Chỉ nhận ảnh JPG, PNG hoặc WEBP dạng base64.')
    try:
        raw = base64.b64decode(match[2], validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError('Dữ liệu ảnh không hợp lệ.') from error
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError('Ảnh phải có dữ liệu và không quá 5 MB.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            fmt = image.format.lower()
    except (OSError, ValueError) as error:
        raise ValueError('Không đọc được ảnh tải lên.') from error
    if MIME.get(fmt) != match[1]:
        raise ValueError('Định dạng ảnh không khớp dữ liệu.')
    return raw, fmt


def save_image(storage: Path, upload: ImageUpload):
    raw, fmt = decode_image(upload.dataUrl)
    image_id = uuid.uuid4().hex
    directory = storage / 'images' / upload.projectId / image_id
    directory.mkdir(parents=True)
    extension = 'jpg' if fmt == 'jpeg' else fmt
    (directory / f'original.{extension}').write_bytes(raw)
    metadata = {'id': image_id, 'projectId': upload.projectId, 'number': upload.number,
                'kind': upload.kind, 'filename': upload.filename,
                'sha256': hashlib.sha256(raw).hexdigest(), 'extension': extension}
    (directory / 'image.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
    return {key: metadata[key] for key in ('id', 'number', 'kind', 'sha256')}


def resolve_images(storage: Path, project_id: str, bindings: list[ImageBinding], content: str):
    mentions = {int(n) for n in re.findall(r'(?<!\w)@image_([1-9][0-9]*)(?!\w)', content)}
    numbers = [binding.number for binding in bindings]
    if len(bindings) > MAX_IMAGES or len(numbers) != len(set(numbers)):
        raise ValueError('Danh sách ảnh không hợp lệ hoặc trùng số thứ tự.')
    if not mentions.issubset(set(numbers)):
        missing = ', '.join(f'@image_{n}' for n in sorted(mentions - set(numbers)))
        raise ValueError(f'Chưa tải ảnh minh họa được nhắc trong nội dung: {missing}.')
    resolved = []
    for binding in bindings:
        directory = storage / 'images' / project_id / binding.imageId
        try:
            metadata = json.loads((directory / 'image.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise ValueError(f'Ảnh @image_{binding.number} không còn trên server. Hãy tải ảnh lại.') from error
        if (metadata['projectId'] != project_id or metadata['number'] != binding.number or
                metadata['kind'] != binding.kind):
            raise ValueError(f'Ảnh @image_{binding.number} không thuộc dự án hoặc đã thay đổi.')
        path = directory / f"original.{metadata['extension']}"
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']:
            raise ValueError(f'Ảnh @image_{binding.number} đã thay đổi trên server.')
        resolved.append({**metadata, 'path': path})
    return resolved
