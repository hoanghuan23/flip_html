"""Generate reviewable phase artwork without narration or animation."""
import hashlib
import json

from image_asset_generator import ImageAssetGenerator, validate_png
from render_style import style_prompt
from token_usage import phase_usage
from scene_logic import REAL_WORLD_RULES
from .illustrations import still_with_illustration
from character_assets import CharacterAssets, reference_prompt


def load_stills(output, *, complete=False):
    script = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
    path = output / 'stills.json'
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    if not isinstance(rows, list) or len(rows) > len(script['phases']):
        raise ValueError('Danh sách ảnh preview không hợp lệ.')
    for index, (row, phase) in enumerate(zip(rows, script['phases']), 1):
        if row['id'] != str(phase['id']) or row['name'] != phase['name']:
            raise ValueError('Ảnh preview không khớp kịch bản.')
        data = (output / f'phase_{index}.preview.png').read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError(f'Ảnh preview phase {index} đã thay đổi. Hãy tạo lại đồ họa.')
        validate_png(data)
    if complete and len(rows) != len(script['phases']):
        raise ValueError('Cần đủ ảnh preview của tất cả phase trước khi xác nhận.')
    return [{**row, 'url': f'/api/graphics/{output.name}/previews/phase_{index}.png'}
            for index, row in enumerate(rows, 1)]


def build_stills(script, output, context, on_progress):
    generator = ImageAssetGenerator(output / 'still_cache')
    characters = CharacterAssets(context, output)
    characters.prepare(script, generator, on_progress)
    prompts = output / 'prompts'
    prompts.mkdir(exist_ok=True)
    rows = []
    manifest_path = output / 'references.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else []
    total = len(script['phases'])
    on_progress('stills', 0, total)
    for index, phase in enumerate(script['phases'], 1):
        prompt = (
            'Generate ONE complete static key visual for this phase of a video storyboard. '
            'A single composed scene in a 16:9 canvas, with the requested background, subjects '
            'and objects together. Choose a clear representative moment of the phase. '
            'No animation, motion sequence, multi-panel layout, player controls or watermark. '
            'Do not print narration, voiceover, phase number or a caption strip. '
            'Only include short labels explicitly required by the phase. '
            'Keep cast identities, clothing, object design, proportions and palette consistent '
            'with the shared design descriptions across all phases. '
            'The style controls drawing technique; the script controls the subject and staging.\n'
            + style_prompt(context)
            + REAL_WORLD_RULES
            + '\nSHARED DESIGN CONTEXT:\n'
            + json.dumps({'title': script['title'], 'assets': script['assets'],
                          'style': script.get('style', {})}, ensure_ascii=False)
            + '\nSTORY CONTEXT:\n'
            + json.dumps([{'name': p['name'], 'description': p['description']}
                          for p in script['phases']], ensure_ascii=False)
            + '\nPHASE TO ILLUSTRATE:\n' + json.dumps(phase, ensure_ascii=False)
        )
        references = characters.phase_references(script, phase)
        prompt += reference_prompt(references, output)
        (prompts / f'phase_{index}_still.txt').write_text(prompt, encoding='utf-8')
        with phase_usage(phase['id']):
            source, info = generator.generate(prompt, transparent=False, requested_size=[1920, 1080],
                                              reference_images=references)
        data = still_with_illustration(source.read_bytes(), phase, output, manifest)
        target = output / f'phase_{index}.preview.png'
        temporary = target.with_suffix('.tmp')
        temporary.write_bytes(data)
        temporary.replace(target)
        rows.append({'id': str(phase['id']), 'name': phase['name'],
                     'width': info['size'][0], 'height': info['size'][1],
                     'sha256': hashlib.sha256(data).hexdigest()})
        temporary = output / 'stills.tmp'
        temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(output / 'stills.json')
        on_progress('stills', index, total)

