"""Frozen character-rig references and a shared library of completed AI sprites."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from character_library import GeneratedCharacterLibrary, CharacterNotFoundError
from image_asset_generator import validate_png

ROOT = Path(__file__).resolve().parent
PARTS = ('head', 'suit', 'arm_L', 'arm_R', 'legs_pair')


def local_file(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError('Đường dẫn nhân vật phải tương đối với thư viện.')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Đường dẫn nhân vật nằm ngoài thư viện.')
    return path


def catalog_snapshot():
    library = GeneratedCharacterLibrary()
    catalog = library.catalog()
    root = library.asset_root(catalog)
    presets = json.loads((ROOT / 'config/character_presets.json').read_text(encoding='utf-8'))
    files = {}
    for preset in presets['presets'].values():
        for slot in PARTS:
            relative = preset['parts'][slot]
            path = local_file(root, relative)
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'presets': presets, 'files': files}


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value).lower()).replace('đ', 'd')
    return ' '.join(re.findall(r'[a-z0-9]+', ''.join(c for c in value if not unicodedata.combining(c))))


def is_xeko(asset):
    return asset.get('category') == 'character' and bool(
        asset.get('preset_id') or re.search(r'\bxeko\b', normalize(' '.join(str(asset.get(k, ''))
                                                                 for k in ('id', 'name', 'description')))))


def phase_has_xeko(script, phase):
    return any(is_xeko(a) for a in phase_assets(script, phase))


def phase_assets(script, phase):
    text = json.dumps(phase, ensure_ascii=False)
    return [a for a in script['assets'] if a.get('category') == 'character'
            and any(re.search(r'(?<!\w)' + re.escape(str(a[k])) + r'(?!\w)', text, re.I)
                    for k in ('id', 'name') if a.get(k))]


def reference_prompt(paths, output):
    if not paths:
        return ''
    return ('\nATTACHED CHARACTER/STORYBOARD REFERENCES (in attachment order):\n'
            + json.dumps([{'file': p.resolve().relative_to(Path(output).resolve()).as_posix(),
                           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]))


class CharacterAssets:
    def __init__(self, context, output):
        self.context = context or {}
        self.enabled = bool(self.context.get('preset', {}).get('character_policy', {}).get('use_template_references'))
        self.output = Path(output).resolve()
        self.root = self.output / 'assets/characters'
        self.library = GeneratedCharacterLibrary()
        self.snapshot = self.context.get('character_library') or (catalog_snapshot() if self.enabled else {})
        if self.enabled:
            source_root = self.library.asset_root(self.library.catalog())
            for relative, expected in self.snapshot['files'].items():
                target = local_file(self.root, relative)
                if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
                    continue
                raw = local_file(source_root, relative).read_bytes()
                if hashlib.sha256(raw).hexdigest() != expected:
                    raise ValueError('Ảnh bộ phận đã thay đổi sau khi tạo tác vụ. Hãy tạo lại đồ họa.')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)

    def preset_id(self, asset, pose):
        presets = self.snapshot.get('presets', {}).get('presets', {})
        explicit = asset.get('preset_id') or (pose if pose in presets else None)
        if explicit:
            if explicit not in presets:
                raise ValueError(f'Preset nhân vật không tồn tại: {explicit}')
            return explicit
        text = normalize(pose + ' ' + asset.get('description', ''))
        for words, key in [('khoc buon cry sad', 'front_cry'), ('suy nghi think confused', 'front_think'),
                           ('hao hung excited', 'front_excited'), ('cuoi laugh', 'front_laught')]:
            if any(re.search(r'\b' + word + r'\b', text) for word in words.split()):
                return key
        return self.snapshot.get('presets', {}).get('default_preset')

    def identity(self, asset, pose):
        preset = self.preset_id(asset, pose) if is_xeko(asset) else None
        identity = {'design': {k: v for k, v in asset.items() if k not in ('id', 'poses', 'base_pose', 'character_id')},
                    'pose': pose, 'preset_id': preset,
                    'parts': self.snapshot.get('files') if preset else None,
                    'style': {k: self.context.get(k) for k in ('id', 'skill', 'preset')}}
        return 'character_' + hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]

    def reuse(self, asset, pose):
        if not self.enabled or asset.get('category') != 'character':
            return None
        explicit = asset.get('character_id')
        character_id = explicit or self.identity(asset, pose)
        try:
            entry = self.library.get(character_id)
        except CharacterNotFoundError:
            if explicit:
                raise ValueError(f'Nhân vật đã chọn chưa có trong thư viện: {explicit}')
            return None
        source = self.library.image_path(entry, self.library.catalog())
        info = validate_png(source.read_bytes(), transparent=True)
        target = self.root / 'completed' / Path(entry['source']).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return target, {**info, 'cached': True, 'character_id': character_id,
                        'character_metadata': {k: v for k, v in entry.items() if k not in ('id', 'source', 'sha256')}}

    def references(self, subject, asset=None):
        if not self.enabled:
            return []
        asset = asset or {'description': subject}
        preset = self.snapshot['presets']['presets'][self.preset_id(asset, subject)]
        return [local_file(self.root, preset['parts'][slot]) for slot in PARTS]

    def record(self, asset_id, pose, path, info, references, *, asset):
        character_id = info.get('character_id') or self.identity(asset, pose)
        metadata = info.get('character_metadata')
        if metadata is not None and not info.get('character_id'):
            metadata = {**metadata, 'rig_status': metadata.get('rig_status', 'ready')}
        if metadata is None:
            metadata = {'joints': {}, 'rig_status': 'pending',
                        'description': asset['description'],
                        'generation': {'pose': pose, 'asset_id': asset_id, 'reference_sha256':
                                       [hashlib.sha256(p.read_bytes()).hexdigest() for p in references]}}
            if is_xeko(asset):
                metadata['preset_id'] = self.preset_id(asset, pose)
                metadata['view'] = self.snapshot['presets']['presets'][metadata['preset_id']]['view']
        entry = self.library.save(character_id, path.read_bytes(), metadata)
        target = self.root / 'catalog.json'
        rows = json.loads(target.read_text()) if target.exists() else {}
        rows[asset_id] = {'pose': pose, **entry}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        return self.reuse({**asset, 'character_id': character_id}, pose)

    def prepare(self, script, generator, on_progress):
        if not self.enabled:
            return
        from image_motion_ai import image_specs, asset_prompt
        specs = [a for a in image_specs(script) if a['category'] == 'character']
        total = sum(len(set([a['base_pose'], *(p['description'] for p in a['poses'])])) for a in specs)
        completed = 0
        if total:
            on_progress('images', 0, total)
        for asset in specs:
            identity_reference = []
            for pose in dict.fromkeys([asset['base_pose'], *(p['description'] for p in asset['poses'])]):
                reused = self.reuse(asset, pose)
                if reused:
                    identity_reference = identity_reference or [reused[0]]
                    completed += 1
                    on_progress('images', completed, total)
                    continue
                refs = self.references(pose, asset) if is_xeko(asset) else identity_reference
                prompt = asset_prompt(script, asset, pose, self.context) + reference_prompt(refs, self.output)
                if is_xeko(asset):
                    prompt += '\nAssemble one complete character from these parts: head, suit, left arm, right arm, legs. Preserve their design and expression.'
                path, info = generator.generate(prompt, transparent=True,
                                                requested_size=[asset['width'], asset['height']], reference_images=refs)
                saved = self.record(asset['id'], pose, path, info, refs, asset=asset)
                identity_reference = identity_reference or [saved[0]]
                completed += 1
                on_progress('images', completed, total)

    def phase_references(self, script, phase):
        from image_motion_ai import image_specs
        ids = {a['id'] for a in phase_assets(script, phase)}
        refs = []
        for asset in image_specs(script):
            if asset['id'] not in ids:
                continue
            result = self.reuse(asset, asset['base_pose'])
            if result:
                refs.append(result[0])
        return refs[:4]
