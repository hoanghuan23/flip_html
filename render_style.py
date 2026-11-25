"""Immutable style inputs shared by CLI, image generation and phase prompts."""
import json
from pathlib import Path
import re

STYLES_ROOT = Path(__file__).resolve().parent / 'skills' / 'styles'


def load_render_style(style_id):
    if not isinstance(style_id, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', style_id):
        raise ValueError('ID phong cách không hợp lệ.')
    directory = STYLES_ROOT / style_id
    try:
        skill = (directory / 'SKILL.md').read_text(encoding='utf-8')
        preset_path = directory / 'style.json'
        preset = json.loads(preset_path.read_text(encoding='utf-8')) if preset_path.is_file() else {}
    except (OSError, ValueError) as error:
        raise ValueError(f'Không đọc được cấu hình phong cách {style_id}.') from error
    if not skill.strip() or not isinstance(preset, dict):
        raise ValueError(f'Cấu hình phong cách {style_id} không hợp lệ.')
    return {'id': style_id, 'skill': skill, 'preset': preset}


def style_prompt(context):
    return ('SELECTED ILLUSTRATION STYLE: ' + context['id'] + '\n'
            + context['skill'] + '\nSTYLE PRESET:\n'
            + json.dumps(context['preset'], ensure_ascii=False)
            + '\nPRIORITY: The selected style controls illustration technique and palette, '
              'overriding aesthetic colors/style in the original Plan. Keep the chosen palette '
              'and identities consistent across every asset, pose and phase. The Plan controls '
              'subjects, camera, geometry, actions and timing. PNG output/alpha requirements '
              'take precedence over SVG examples in the style guide. Do not copy example '
              'subjects, object counts, card dimensions, compositions or decorative elements '
              'that the Plan does not request.\n')


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
