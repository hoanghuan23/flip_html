"""Prepare character references in flip_html; Codex Server only generates images."""
import base64
import binascii
import json
import os
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / 'skills/templates/character_rig'
SLOTS = ('head', 'suit', 'arm_L', 'arm_R', 'legs_pair')
MAX_BYTES = 20 * 1024 * 1024
load_dotenv(ROOT / '.env')
router = APIRouter()


class CharacterInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: dict
    preset_id: str | None = None
    prompt: str = Field(min_length=1, max_length=30000)


def default_endpoint():
    explicit = os.getenv('CODEX_IMAGE_API_URL', '').strip()
    if explicit:
        return explicit
    value = os.getenv('CODEX_API_URL', 'http://127.0.0.1:8000').strip().rstrip('/')
    parsed = urlsplit(value)
    path = parsed.path.rstrip('/')
    if path.rsplit('/', 1)[-1] in {'analyze', 'generate', 'generate-image'}:
        path = path.rsplit('/', 1)[0]
    return urlunsplit((parsed.scheme, parsed.netloc, path + '/generate-image', '', ''))


def asset_path(value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('Đường dẫn ảnh phải tương đối với thư mục character_rig.')
    path = (ASSET_ROOT / value).resolve()
    if not path.is_relative_to(ASSET_ROOT.resolve()) or path.suffix.lower() != '.png':
        raise ValueError('Ảnh phải là PNG nằm trong thư mục character_rig.')
    if not path.is_file():
        raise ValueError(f'Không tìm thấy ảnh: {value}')
    return path


def selected_config(config, preset_id=None):
    if 'presets' in config:
        presets = config['presets']
        key = preset_id or config.get('default_preset')
        if (not isinstance(presets, dict) or not isinstance(key, str)
                or not isinstance(presets.get(key), dict)):
            raise ValueError('Không tìm thấy preset được chọn trong config.')
        config = presets[key]
    parts = config.get('parts', config)
    if not isinstance(parts, dict) or not all(slot in parts for slot in SLOTS):
        raise ValueError('Config cần đủ head, suit, arm_L, arm_R, legs_pair trong parts.')
    unknown = set(parts) - set(SLOTS) - {'shoulder_L', 'shoulder_R'}
    if unknown:
        raise ValueError('Bộ phận chưa hỗ trợ: ' + ', '.join(sorted(unknown)))
    return config, parts


def prepare_character(request):
    _, parts = selected_config(request.config, request.preset_id)
    references, sources = [], []
    total = 0
    for slot in SLOTS:
        path = asset_path(parts[slot])
        if path.stat().st_size > MAX_BYTES - total:
            raise ValueError('Tổng ảnh bộ phận vượt 20 MiB.')
        raw = path.read_bytes()
        total += len(raw)
        if total > MAX_BYTES or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError(f'{slot}: cần PNG hợp lệ, tổng ảnh không quá 20 MiB.')
        references.append('data:image/png;base64,' + base64.b64encode(raw).decode('ascii'))
        sources.append({'slot': slot, 'path': parts[slot]})
    if not request.prompt.strip():
        raise ValueError('Prompt không được để trống.')
    return {'prompt': request.prompt.strip(), 'reference_images': references, 'parts': sources,
            'ignored_parts': [slot for slot in ('shoulder_L', 'shoulder_R') if slot in parts]}


@router.get('/character-ai')
def character_page():
    return FileResponse(ROOT / 'character_ai.html', media_type='text/html',
                        headers={'Cache-Control': 'no-store'})


@router.get('/character_ai.html', include_in_schema=False)
def character_page_redirect():
    return RedirectResponse('/character-ai', status_code=307)


@router.get('/api/character-ai/config')
def character_config():
    return {'config': json.loads((ROOT / 'config/character_presets.json').read_text(encoding='utf-8'))}


@router.get('/api/character-ai/assets/{value:path}')
def character_asset(value: str):
    try:
        return FileResponse(asset_path(value), media_type='image/png')
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


@router.post('/api/character-ai/prepare')
def prepare(request: CharacterInput):
    try:
        return prepare_character(request)
    except (ValueError, OSError) as error:
        raise HTTPException(422, str(error)) from error


def saved_directory(http_request, character_id):
    if not re.fullmatch(r'[a-f0-9]{32}', character_id):
        raise HTTPException(404, 'Không tìm thấy nhân vật đã lưu.')
    root = http_request.app.state.storage_root / 'character_ai'
    directory = root / character_id
    if directory.is_symlink() or not (directory / 'character.json').is_file():
        raise HTTPException(404, 'Không tìm thấy nhân vật đã lưu.')
    return directory


def read_saved(directory):
    return json.loads((directory / 'character.json').read_text(encoding='utf-8'))


def save_character(http_request, request, model, raw, usage):
    character_id = uuid4().hex
    base = f'/api/character-ai/saved/{character_id}'
    selected, _ = selected_config(request.config, request.preset_id)
    manifest = {
        'version': 1, 'kind': 'character-ai-result', 'id': character_id,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'description': selected.get('description', '') if 'parts' in selected else '',
        'model': model, 'image': 'character.png', 'image_url': base + '/character.png',
        'config_url': base + '/character.json',
        'input': request.model_dump(), 'usage': usage,
    }
    root = http_request.app.state.storage_root / 'character_ai'
    temporary = root / ('.' + character_id)
    try:
        root.mkdir(parents=True, exist_ok=True)
        temporary.mkdir()
        (temporary / 'character.png').write_bytes(raw)
        (temporary / 'character.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.rename(root / character_id)
    except OSError:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


@router.get('/api/character-ai/saved')
def saved_characters(http_request: Request):
    root = http_request.app.state.storage_root / 'character_ai'
    characters = []
    for directory in root.glob('*'):
        if not re.fullmatch(r'[a-f0-9]{32}', directory.name) or directory.is_symlink():
            continue
        try:
            manifest = read_saved(directory)
            if manifest.get('id') != directory.name or not (directory / 'character.png').is_file():
                continue
            characters.append({key: manifest.get(key) for key in
                               ('id', 'created_at', 'description', 'image_url', 'config_url')})
        except (OSError, ValueError, AttributeError):
            continue
    characters.sort(key=lambda item: item.get('created_at') or '', reverse=True)
    return {'characters': characters}


@router.get('/api/character-ai/saved/{character_id}')
def saved_character(character_id: str, http_request: Request):
    directory = saved_directory(http_request, character_id)
    try:
        return read_saved(directory)
    except (OSError, ValueError) as error:
        raise HTTPException(404, 'Không đọc được cấu hình nhân vật đã lưu.') from error


@router.get('/api/character-ai/saved/{character_id}/{filename}')
def saved_character_file(character_id: str, filename: str, http_request: Request):
    directory = saved_directory(http_request, character_id)
    if filename not in {'character.png', 'character.json'}:
        raise HTTPException(404, 'Không tìm thấy file nhân vật.')
    path = directory / filename
    if path.is_symlink() or not path.is_file():
        raise HTTPException(404, 'Không tìm thấy file nhân vật.')
    return FileResponse(path, media_type='image/png' if filename.endswith('.png') else 'application/json',
                        filename=character_id + ('.png' if filename.endswith('.png') else '.json'))


@router.post('/api/character-ai/generate')
async def generate(request: CharacterInput, http_request: Request):
    prepared = prepare(request)
    endpoint = default_endpoint().strip()
    try:
        parsed = urlsplit(endpoint)
    except ValueError as error:
        raise HTTPException(422, 'URL API không hợp lệ.') from error
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, 'URL API phải là HTTP/HTTPS hợp lệ.')
    model = os.getenv('CODEX_MODEL', '').strip()
    token = os.getenv('CODEX_API_TOKEN', '').strip()
    if not model or not token:
        raise HTTPException(422, 'Thiếu CODEX_MODEL hoặc CODEX_API_TOKEN trong .env của flip_html.')
    payload = {'model': model, 'prompt': prepared['prompt'],
               'reference_images': prepared['reference_images']}
    try:
        async with httpx.AsyncClient(timeout=660) as client:
            response = await client.post(endpoint, json=payload, headers={'X-API-Key': token})
    except httpx.TimeoutException as error:
        raise HTTPException(504, 'Hết thời gian chờ Codex Server tạo ảnh.') from error
    except httpx.HTTPError as error:
        raise HTTPException(502, 'Không kết nối được Codex Server. Kiểm tra URL và tiến trình server.') from error
    try:
        result = response.json()
    except ValueError as error:
        raise HTTPException(502, 'Codex Server không trả JSON hợp lệ. Kiểm tra URL /generate-image.') from error
    if not response.is_success:
        detail = result.get('detail', 'Không tạo được ảnh.') if isinstance(result, dict) else 'Không tạo được ảnh.'
        raise HTTPException(response.status_code if response.status_code >= 400 else 502, detail)
    try:
        if result.get('success') is not True or result.get('output_format') != 'png':
            raise ValueError('Invalid image response')
        encoded = result['data'][0]['b64_json']
        if not isinstance(encoded, str) or len(encoded) > MAX_BYTES * 4 // 3 + 64:
            raise ValueError('Invalid image size')
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_BYTES or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Invalid PNG')
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, binascii.Error) as error:
        raise HTTPException(502, 'Codex Server chưa trả ảnh PNG hợp lệ.') from error
    try:
        saved = save_character(http_request, request, model, raw, result.get('usage'))
    except OSError:
        saved = None
    return {'success': True, 'output_format': 'png', 'data': [{'b64_json': encoded}],
            'usage': result.get('usage'), 'saved': saved,
            'save_error': None if saved else 'Đã tạo PNG nhưng không lưu được trên máy chủ. Hãy tải PNG trước khi đóng trang.'}
