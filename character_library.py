"""Lưu PNG nhân vật AI và tọa độ khớp để tái sử dụng từ thư viện cục bộ."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tempfile

from PIL import Image, UnidentifiedImageError


ROOT = Path(__file__).resolve().parent
COORDINATE_SPACE = 'image_pixels_top_left'
IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$')
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class CharacterLibraryError(ValueError):
    pass


class CharacterNotFoundError(CharacterLibraryError):
    pass


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise CharacterLibraryError('ID cần 1–100 ký tự chữ, số, dấu gạch ngang hoặc gạch dưới.')
    return value


def image_size(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_IMAGE_BYTES:
        raise CharacterLibraryError('Ảnh cần dữ liệu PNG không quá 20 MiB.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG':
                raise CharacterLibraryError('Ảnh nhân vật phải là PNG.')
            size = list(image.size)
            image.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise CharacterLibraryError('Không đọc được ảnh PNG nhân vật.') from error
    return size


def validated_metadata(metadata, size):
    if not isinstance(metadata, dict):
        raise CharacterLibraryError('Metadata nhân vật phải là object JSON.')
    allowed = {'joints', 'description', 'preset_id', 'view', 'generation', 'image_size', 'coordinate_space'}
    if set(metadata) - allowed:
        raise CharacterLibraryError('Metadata có trường chưa hỗ trợ: ' + ', '.join(sorted(set(metadata) - allowed)))
    if metadata.get('image_size', size) != size:
        raise CharacterLibraryError('image_size không khớp kích thước PNG; cần tọa độ trên ảnh gốc.')
    if metadata.get('coordinate_space', COORDINATE_SPACE) != COORDINATE_SPACE:
        raise CharacterLibraryError('Tọa độ khớp phải là pixel ảnh gốc, gốc trên trái, trục y hướng xuống.')
    joints = metadata.get('joints')
    if not isinstance(joints, dict) or not joints:
        raise CharacterLibraryError('Cần joints chứa vị trí [x, y] thực tế của các khớp trên PNG.')
    for name, position in joints.items():
        identifier(name)
        if (not isinstance(position, list) or len(position) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in position)):
            raise CharacterLibraryError(f'{name}: tọa độ khớp cần mảng [x, y].')
        if not all(math.isfinite(v) and 0 <= v < limit for v, limit in zip(position, size)):
            raise CharacterLibraryError(f'{name}: tọa độ khớp phải hữu hạn và nằm trong ảnh {size}.')
    for field in ('description', 'preset_id', 'view'):
        if field in metadata and not isinstance(metadata[field], str):
            raise CharacterLibraryError(f'{field}: cần chuỗi.')
    if 'generation' in metadata and not isinstance(metadata['generation'], dict):
        raise CharacterLibraryError('generation: cần object chứa thông tin lần tạo ảnh.')
    try:
        # Copy metadata, rejecting non-JSON values before changing the library.
        result = json.loads(json.dumps(metadata, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise CharacterLibraryError('Metadata phải là JSON hợp lệ, không chứa NaN/Infinity.') from error
    return {**result, 'image_size': size, 'coordinate_space': COORDINATE_SPACE}


def atomic_write(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '.', delete=False) as temporary:
        pending = Path(temporary.name)
        try:
            temporary.write(raw)
            temporary.flush()
        except BaseException:
            pending.unlink(missing_ok=True)
            raise
    try:
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


class GeneratedCharacterLibrary:
    def __init__(self, catalog_path=ROOT / 'config/character_assets.json', *, project_root=ROOT):
        self.catalog_path = Path(catalog_path)
        self.project_root = Path(project_root).resolve()

    def catalog(self):
        catalog = json.loads(self.catalog_path.read_text(encoding='utf-8'))
        if (not isinstance(catalog, dict) or catalog.get('version') != 1
                or not isinstance(catalog.get('generated_characters'), dict)):
            raise CharacterLibraryError('Catalog cần version 1 và object generated_characters.')
        return catalog

    def asset_root(self, catalog):
        value = catalog.get('asset_root')
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise CharacterLibraryError('asset_root phải là đường dẫn tương đối trong dự án.')
        root = (self.project_root / value).resolve()
        if not root.is_relative_to(self.project_root):
            raise CharacterLibraryError('asset_root nằm ngoài dự án.')
        return root

    def image_path(self, entry, catalog):
        root = self.asset_root(catalog)
        source = entry.get('source')
        if (not isinstance(source, str) or Path(source).is_absolute()
                or Path(source).parent != Path('GENERATED') or Path(source).suffix != '.png'):
            raise CharacterLibraryError('Ảnh đã lưu phải thuộc character_rig/GENERATED và có đuôi .png.')
        path = (root / source).resolve()
        if not path.is_relative_to(root):
            raise CharacterLibraryError('Ảnh đã lưu nằm ngoài thư viện.')
        return path

    def get(self, character_id):
        identifier(character_id)
        catalog = self.catalog()
        entry = catalog['generated_characters'].get(character_id)
        if entry is None:
            raise CharacterNotFoundError(f'Chưa có nhân vật {character_id!r} trong thư viện.')
        if not isinstance(entry, dict):
            raise CharacterLibraryError('Thông tin nhân vật đã lưu không hợp lệ.')
        try:
            raw = self.image_path(entry, catalog).read_bytes()
        except OSError as error:
            raise CharacterLibraryError(f'Không đọc được PNG đã lưu của {character_id!r}.') from error
        if hashlib.sha256(raw).hexdigest() != entry.get('sha256') or image_size(raw) != entry.get('image_size'):
            raise CharacterLibraryError('PNG đã thay đổi; cần đăng ký lại tọa độ khớp cho đúng ảnh.')
        validated_metadata({k: v for k, v in entry.items() if k not in ('source', 'sha256')}, entry['image_size'])
        return {'id': character_id, **entry}

    def save(self, character_id, raw, metadata, *, overwrite=False):
        identifier(character_id)
        entry = validated_metadata(metadata, image_size(raw))
        digest = hashlib.sha256(raw).hexdigest()
        entry.update(source=f'GENERATED/{character_id}-{digest}.png', sha256=digest)
        # A separate lock survives atomic catalog replacement and prevents lost updates.
        with self.catalog_path.with_suffix('.json.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            catalog = self.catalog()
            previous = catalog['generated_characters'].get(character_id)
            if previous is not None and previous != entry and not overwrite:
                raise CharacterLibraryError('ID đã tồn tại với ảnh hoặc tọa độ khác. Dùng ID mới hoặc --overwrite.')
            path = self.image_path(entry, catalog)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file() or path.read_bytes() != raw:
                atomic_write(path, raw)
            if previous != entry:
                catalog['generated_characters'][character_id] = entry
                atomic_write(self.catalog_path, (json.dumps(catalog, ensure_ascii=False, indent=2,
                                                          allow_nan=False) + '\n').encode('utf-8'))
        return {'id': character_id, **entry}

    def get_or_create(self, character_id, generate):
        """generate() returns (PNG bytes, metadata); called only for a missing ID."""
        try:
            return self.get(character_id)
        except CharacterNotFoundError:
            raw, metadata = generate()
            return self.save(character_id, raw, metadata)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'config/character_assets.json')
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('list', help='Liệt kê ID nhân vật đã lưu.')
    get = actions.add_parser('get', help='Đọc ảnh và thông số đã lưu, không gọi AI.')
    get.add_argument('id')
    add = actions.add_parser('add', help='Nhập PNG và metadata thực tế do AI trả về.')
    add.add_argument('id')
    add.add_argument('--image', type=Path, required=True)
    add.add_argument('--metadata', type=Path, required=True)
    add.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    library = GeneratedCharacterLibrary(args.catalog)
    if args.action == 'list':
        result = list(library.catalog()['generated_characters'])
    elif args.action == 'get':
        result = library.get(args.id)
    else:
        result = library.save(args.id, args.image.read_bytes(),
                              json.loads(args.metadata.read_text(encoding='utf-8')), overwrite=args.overwrite)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (CharacterLibraryError, OSError, ValueError) as error:
        raise SystemExit(f'Lỗi: {error}')
