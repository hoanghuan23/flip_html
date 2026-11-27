"""Catalog-backed Xeko references, copied into each consuming preview."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from image_asset_generator import validate_png

ROOT = Path(__file__).resolve().parent / 'skills/templates/character'


def local_file(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Đường dẫn catalog nhân vật không hợp lệ.')
    return path


def catalog_snapshot():
    catalog = json.loads((ROOT / 'asset_catalog.json').read_text(encoding='utf-8'))
    files = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for folder in ('design', 'poses') for p in sorted((ROOT / folder).glob('*.png'))}
    canonical = [v['file'] for v in catalog['canonical_views'].values() if v['file'] in files]
    if not canonical:
        raise ValueError('Thiếu ảnh thiết kế Xeko gốc trong catalog.')
    return {'catalog': catalog, 'files': files}


def is_xeko(asset):
    if asset.get('category') != 'character':
        return False
    named = ' '.join(str(asset.get(k, '')) for k in ('id', 'name'))
    return bool(re.search(r'(?<![a-z0-9])xeko(?![a-z0-9])', named, re.I)
                or re.match(r'\s*Xeko\b', asset.get('description', ''), re.I))


def normalize(value):
    value = unicodedata.normalize('NFKD', value.lower()).replace('đ', 'd')
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', value))


def phase_has_xeko(script, phase):
    text = json.dumps(phase, ensure_ascii=False).lower()
    return any(is_xeko(a) and any(re.search(r'(?<!\w)' + re.escape(str(a[k]).lower()) + r'(?!\w)', text)
                                 for k in ('id', 'name') if a.get(k)) for a in script['assets'])


def reference_prompt(paths, output):
    if not paths:
        return ''
    return ('\nSELECTED CHARACTER REFERENCES (attached as real images in this order):\n'
            + json.dumps([{'file': p.relative_to(Path(output).resolve()).as_posix(),
                           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                          for p in paths], ensure_ascii=False))


class CharacterAssets:
    def __init__(self, context, output):
        template = (context or {}).get('template', {})
        self.enabled = template.get('id') == 'character'
        self.output = Path(output).resolve()
        self.root = self.output / 'assets/characters'
        self.catalog = {}
        if not self.enabled:
            return
        snapshot = template.get('library') or catalog_snapshot()
        self.catalog = snapshot['catalog']
        self.files = snapshot['files']
        for relative, expected in self.files.items():
            target = local_file(self.root, relative)
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
                continue
            source = local_file(ROOT, relative)
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Mẫu Xeko đã thay đổi sau khi tạo tác vụ. Hãy tạo lại đồ họa.')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'source_catalog.json').write_text(
            json.dumps(self.catalog, ensure_ascii=False, indent=2), encoding='utf-8')

    def entries(self):
        entries = [a for a in self.catalog.get('assets', []) if a['file'] in self.files]
        known = {a['file'] for a in entries}
        entries += [{'id': Path(p).stem, 'file': p, 'tags': [normalize(Path(p).stem)],
                     'category': 'design_variant' if p.startswith('design/') else 'pose'}
                    for p in self.files if p not in known]
        return entries

    def references(self, subject):
        if not self.enabled:
            return []
        text = normalize(subject)
        views = self.catalog['canonical_views']
        view = ('back' if re.search(r'\b(back view|rear view|quay lung)\b', text) else
                'right_profile' if re.search(r'\b(facing left|right profile|huong trai)\b', text) else
                'left_profile' if re.search(r'\b(facing right|left profile|huong phai)\b', text) else 'front')
        # A missing catalog view must not prevent using the available original designs.
        canonical = views.get(view, {}).get('file')
        if canonical not in self.files:
            canonical = views['front']['file']
        if canonical not in self.files:
            canonical = next(v['file'] for v in views.values() if v['file'] in self.files)
        paths = [local_file(self.root, canonical)]
        def matches(tag):
            return bool(re.search(r'(?<!\w)' + re.escape(normalize(tag)) + r'(?!\w)', text))
        canonical_files = {v['file'] for v in views.values()}
        # Costume references precede pose references, but neither replaces the original.
        for category in ('design_variant', 'pose', 'design_view'):
            ranked = sorted([a for a in self.entries() if a.get('category') == category
                             and a['file'] not in canonical_files],
                            key=lambda a: sum(matches(tag) for tag in a.get('tags', [])), reverse=True)
            if ranked and any(matches(tag) for tag in ranked[0].get('tags', [])):
                path = local_file(self.root, ranked[0]['file'])
                if path not in paths:
                    paths.append(path)
        return paths

    def reuse(self, asset, pose):
        if not self.enabled or not is_xeko(asset):
            return None
        # Only exact catalog selectors are reusable; prose may request extra props,
        # a different outfit or a composite action and must go through generation.
        selector = normalize(pose)
        description = normalize(asset.get('description', ''))
        canonical_files = {v['file'] for v in self.catalog['canonical_views'].values()}
        variants = [a for a in self.entries() if a.get('category') == 'design_variant'
                    and a['file'] not in canonical_files
                    and any(re.search(r'(?<!\w)' + re.escape(normalize(tag)) + r'(?!\w)', description)
                            for tag in a.get('tags', []))]
        for entry in self.entries():
            selectors = {normalize(entry['id']), normalize(Path(entry['file']).stem),
                         normalize(' '.join(entry.get('tags', [])))}
            if selector not in selectors or entry.get('background') != 'transparent':
                continue
            if variants and entry['file'] not in {v['file'] for v in variants}:
                continue
            if 'full body' in description and 'portrait' in entry.get('tags', []):
                continue
            path = local_file(self.root, entry['file'])
            info = validate_png(path.read_bytes(), transparent=True)
            return path, {**info, 'cached': True, 'catalog_id': entry['id'],
                          'source_file': entry['file'], 'operation': 'catalog_reuse'}
        return None

    def record(self, asset_id, pose, path, info, references):
        """Keep provenance local; unreviewed AI output never replaces master designs."""
        target = self.root / 'catalog.json'
        catalog = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {
            'character': 'Xeko', 'assets': []}
        row = {'id': asset_id, 'pose': pose, 'file': path.resolve().relative_to(self.output).as_posix(),
               'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'references': [p.relative_to(self.output).as_posix() for p in references],
               'operation': info.get('operation', 'reference_generation'),
               'identity_review': 'catalog source' if info.get('catalog_id') else 'pending review'}
        catalog['assets'] = [a for a in catalog['assets'] if a['id'] != asset_id] + [row]
        target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
