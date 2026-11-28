"""Immutable style inputs shared by CLI, image generation and phase prompts."""
import json
from pathlib import Path
import re

STYLES_ROOT = Path(__file__).resolve().parent / 'skills' / 'styles'
TEMPLATES_ROOT = Path(__file__).resolve().parent / 'skills' / 'templates'


def load_render_style(style_id):
    from backend.models import load_style_config
    config = load_style_config()
    entry = next((row for row in config['styles'] if row['id'] == style_id), None)
    if entry is None:
        raise ValueError(f'Phong cách {style_id!r} chưa được đăng ký.')
    root = STYLES_ROOT.parent.parent.resolve()
    def read_source(field):
        path = (root / entry[field]).resolve()
        if not path.is_relative_to(STYLES_ROOT.resolve()):
            raise ValueError('Đường dẫn phong cách nằm ngoài skills/styles.')
        return path.read_text(encoding='utf-8')
    try:
        skill = read_source('skill_path')
        preset = json.loads(read_source('style_path'))
    except (OSError, KeyError, ValueError) as error:
        raise ValueError(f'Không đọc được cấu hình phong cách {style_id}.') from error
    if not skill.strip() or not isinstance(preset, dict) or preset.get('id') != style_id:
        raise ValueError(f'Cấu hình phong cách {style_id} không hợp lệ.')
    return {'id': style_id, 'skill': skill, 'preset': preset}


def load_render_context(style_id, category_id=None):
    from backend.models import load_style_config
    config = load_style_config()
    category_id = category_id or config['default_category']
    category = next((row for row in config['categories'] if row['id'] == category_id), None)
    if category is None or style_id not in category['allowed_styles']:
        raise ValueError('Phong cách không được phép trong nhóm chủ đề đã chọn.')
    context = load_render_style(style_id)
    if context['preset'].get('character_policy', {}).get('use_template_references'):
        from character_assets import catalog_snapshot
        context['character_library'] = catalog_snapshot()
    return context


def style_prompt(context):
    return ('SELECTED ILLUSTRATION STYLE: ' + context['id'] + '\n'
            + context['skill'] + '\nSTYLE PRESET:\n'
            + json.dumps(context['preset'], ensure_ascii=False)
            + '\nPRIORITY: Follow the selected style and actual character reference images. '
              'Preserve the supplied identity, proportions, costume and facial expression; '
              'change only what the script explicitly requests. The script controls subjects, '
              'camera, actions and timing. Never introduce the template character into a scene '
              'that does not request him. Do not copy unrelated examples from the skill.\n')


def caption_colors(context):
    preset = context.get('preset', {})
    valid = lambda color: isinstance(color, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color)
    background = preset.get('background', '#ffffff')
    if not valid(background):
        background = '#ffffff'

    def luminance(color):
        values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))

    def contrast(color):
        low, high = sorted((luminance(color), luminance(background)))
        return (high + .05) / (low + .05)

    colors = [c.get('hex') for c in preset.get('palette', []) if isinstance(c, dict) and valid(c.get('hex'))]
    ink = max(colors, key=contrast) if colors else '#111111'
    if contrast(ink) < 4.5:
        ink = max(('#111111', '#ffffff'), key=contrast)
    return background, ink
