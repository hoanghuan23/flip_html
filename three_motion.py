"""Declarative, validated mesh scenes shared by browser preview and MP4 export."""
import base64
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.narration import cue_time
from backend.inputs import requested_labels

ROOT = Path(__file__).resolve().parent
STYLE = ROOT / 'skills' / '3d-motion-infographic'
VERSION = 'three-motion-v1'
Scalar = Annotated[float, Field(allow_inf_nan=False, ge=-10000, le=10000)]
Vec3 = tuple[Scalar, Scalar, Scalar]
Color = Annotated[str, Field(pattern=r'^#[0-9a-fA-F]{6}$')]


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Material(Model):
    color: Color = '#b9c9d9'
    metalness: float = Field(default=.2, ge=0, le=1, allow_inf_nan=False)
    roughness: float = Field(default=.55, ge=0, le=1, allow_inf_nan=False)
    opacity: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    emissive: Color = '#000000'
    texture: Literal['earth'] | None = None


class Node(Model):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')
    parent: str | None = None
    geometry: Literal['group', 'box', 'sphere', 'plane', 'cylinder', 'cone', 'torus', 'stars']
    position: Vec3 = (0, 0, 0)
    rotation: Vec3 = (0, 0, 0)
    scale: Vec3 = (1, 1, 1)
    material: Material = Field(default_factory=Material)


class Keyframe(Model):
    t: float = Field(ge=0, le=120, allow_inf_nan=False)
    value: Vec3
    cue: str | None = Field(default=None, max_length=200)


class Track(Model):
    target: str
    property: Literal['position', 'rotation', 'scale']
    easing: Literal['linear', 'smooth'] = 'smooth'
    keys: list[Keyframe] = Field(min_length=2, max_length=100)


class CameraKey(Model):
    t: float = Field(ge=0, le=120, allow_inf_nan=False)
    position: Vec3
    lookAt: Vec3 = (0, 0, 0)
    cue: str | None = Field(default=None, max_length=200)


class Overlay(Model):
    type: Literal['label', 'image', 'connector']
    text: str = Field(default='', max_length=200)
    number: int | None = Field(default=None, gt=0)
    start: float = Field(default=0, ge=0, le=120, allow_inf_nan=False)
    end: float = Field(gt=0, le=120, allow_inf_nan=False)
    cue: str | None = Field(default=None, max_length=200)
    target: str | None = None
    anchor: Vec3 = (0, 0, 0)
    endTarget: str | None = None
    endAnchor: Vec3 = (0, 0, 0)
    x: float = Field(default=.1, ge=.05, le=.9, allow_inf_nan=False)
    y: float = Field(default=.15, ge=.05, le=.9, allow_inf_nan=False)
    width: float = Field(default=.32, ge=.1, le=.38, allow_inf_nan=False)


class ScenePlan(Model):
    background: Color = '#080f19'
    ambient: float = Field(default=1.1, ge=0, le=5, allow_inf_nan=False)
    lightPosition: Vec3 = (-8, 8, 10)
    lightIntensity: float = Field(default=3, ge=0, le=10, allow_inf_nan=False)
    fov: float = Field(default=40, ge=15, le=80, allow_inf_nan=False)
    nodes: list[Node] = Field(min_length=1, max_length=800)
    camera: list[CameraKey] = Field(min_length=1, max_length=100)
    tracks: list[Track] = Field(default_factory=list, max_length=500)
    overlays: list[Overlay] = Field(default_factory=list, max_length=40)

    @model_validator(mode='after')
    def references(self):
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError('ID mesh phải khác nhau.')
        if not any(node.geometry not in ('group', 'stars', 'plane') for node in self.nodes):
            raise ValueError('Cảnh cần có chủ thể mesh 3D có thể tích.')
        for node in self.nodes:
            seen = {node.id}
            parent = node.parent
            while parent:
                if parent not in nodes or parent in seen:
                    raise ValueError('Quan hệ cha/con mesh không hợp lệ.')
                seen.add(parent)
                parent = nodes[parent].parent
            if any(v <= 0 for v in node.scale):
                raise ValueError('Tỷ lệ mesh phải dương.')
        targets = [(track.target, track.property) for track in self.tracks]
        if len(set(targets)) != len(targets):
            raise ValueError('Một thuộc tính mesh chỉ được điều khiển bởi một track.')
        for target in [t.target for t in self.tracks] + [o.target for o in self.overlays if o.target] + [o.endTarget for o in self.overlays if o.endTarget]:
            if target not in nodes:
                raise ValueError(f'Mesh không tồn tại: {target}.')
        for overlay in self.overlays:
            if overlay.type == 'label' and not overlay.text.strip():
                raise ValueError('Nhãn chữ không được để trống.')
            if overlay.type == 'image' and overlay.number is None:
                raise ValueError('Khung ảnh phải chỉ rõ số Hình.')
            if overlay.type == 'connector' and not (overlay.target and overlay.endTarget):
                raise ValueError('Đường nối cần mesh đầu và mesh đích.')
        return self


def validate_plan(raw, phase, references, alignment=None):
    plan = ScenePlan.model_validate(raw).model_dump(mode='json')
    duration = phase['duration']
    def resolve(item, field):
        if item.get('cue'):
            t = cue_time(alignment, item['cue']) if alignment else None
            if t is None:
                raise ValueError(f"Không tìm được cụm lời đọc: {item['cue']}")
            item[field] = t
    sequences = [('camera', plan['camera']), *(
        (f"tracks[{index}] ({track['target']}.{track['property']}).keys", track['keys'])
        for index, track in enumerate(plan['tracks']))]
    for name, keys in sequences:
        for index, key in enumerate(keys):
            resolve(key, 't')
            if key['t'] > duration:
                raise ValueError(f"Mốc chuyển động {name}[{index}].t={key['t']} nằm ngoài cảnh; "
                                 f'duration={duration}. Mọi t phải <= duration.')
            if index and keys[index - 1]['t'] >= key['t']:
                raise ValueError(f"Mốc chuyển động phải tăng dần: {name}[{index - 1}].t="
                                 f"{keys[index - 1]['t']} >= {name}[{index}].t={key['t']} "
                                 f'sau khi đồng bộ cue; duration={duration}.')
        if keys[0]['t'] != 0:
            raise ValueError(f"{name}[0].t={keys[0]['t']}: camera và track phải khai báo trạng thái tại t=0, không có cue.")
    available = {r['number'] for r in references}
    for overlay in plan['overlays']:
        resolve(overlay, 'start')
        if not 0 <= overlay['start'] < overlay['end'] <= duration:
            raise ValueError(f"Thời gian hiển thị lớp thông tin không hợp lệ: start={overlay['start']}, "
                             f"end={overlay['end']}; cần 0 <= start < end <= duration={duration}.")
        if overlay['type'] == 'image' and overlay['number'] not in available:
            raise ValueError(f"Thiếu ảnh tham chiếu Hình {overlay['number']}.")
    for label in requested_labels(phase.get('description', '')):
        if not any(o['text'] == label for o in plan['overlays']):
            raise ValueError('Phải hiển thị nguyên văn nhãn: ' + label)
    for number in set(map(int, re.findall(r'(?i)\bhình\s+(\d+)\b', phase.get('description', '')))):
        if not any(o['type'] == 'image' and o['number'] == number for o in plan['overlays']):
            raise ValueError(f'Cảnh phải có khung ảnh Hình {number} theo mô tả.')
    return plan


def json_script(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def phase_page(phase, plan, reference_data, fingerprint):
    metadata = {'phase': phase, 'renderer': VERSION, 'fingerprint': fingerprint, 'width': 1920, 'height': 1080}
    return ('<!doctype html><html lang="vi" data-renderer="' + VERSION + '" data-fingerprint="' + fingerprint + '"><head><meta charset="utf-8"><title>' + escape(phase['name'])
            + '</title><style>' + (STYLE / 'runtime' / 'scene.css').read_text() + '</style></head><body>'
            + '<main id="stage"><canvas id="scene"></canvas><svg id="connectors" viewBox="0 0 1920 1080"></svg><div id="overlays"></div><div id="scene-error" role="alert" hidden></div></main>'
            + '<script type="application/json" id="scene-data">' + json_script(metadata) + '</script>'
            + '<script type="application/json" id="mesh-data">' + json_script({'plan': plan, 'references': reference_data}) + '</script>'
            + '<script>window.renderAt=function(t){window.pendingTime=t};</script>'
            + '<script src="assets/runtime/three-scene.js"></script></body></html>')


def build_preview(script, output, request, *, style_context, references=None, on_progress=None, **_):
    references = references or []
    runtime = STYLE / 'runtime' / 'three-scene.js'
    if not runtime.is_file():
        raise ValueError('Chưa có runtime 3D. Chạy npm run build trong frontend/.')
    identity = {'script': script, 'style': style_context, 'references': references,
                'runtime': hashlib.sha256(runtime.read_bytes()).hexdigest(), 'version': VERSION}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assets = output / 'assets' / 'runtime'
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime, assets / runtime.name)
    fonts = output / 'assets' / 'fonts'
    fonts.mkdir(exist_ok=True)
    for path in (ROOT / 'frontend' / 'public' / 'fonts').glob('*.woff2'):
        shutil.copy2(path, fonts / path.name)
    texture = STYLE / 'assets' / 'earth.jpg'
    source_manifest = STYLE / 'assets' / 'sources.json'
    reference_data = {str(r['number']): {'src': 'data:image/' + ('jpeg' if r['src'].endswith('.jpeg') else Path(r['src']).suffix[1:])
                      + ';base64,' + base64.b64encode((output / r['src']).read_bytes()).decode(), 'name': r['name']} for r in references}
    for index, phase in enumerate(script['phases'], 1):
        if on_progress:
            on_progress('phases', index - 1, len(script['phases']))
        alignment = json.loads((output / phase['audio']['alignment']).read_text())['alignment'] if phase.get('audio') else None
        path = output / f'phase_{index}.scene.json'
        try:
            cached = json.loads(path.read_text()) if path.exists() and not _.get('redo') else {}
        except (OSError, ValueError):
            cached = {}
        plan = None
        if cached.get('fingerprint') == fingerprint:
            try:
                plan = validate_plan(cached['plan'], phase, references, alignment)
            except ValueError:
                pass
        if plan is None:
            schema = ScenePlan.model_json_schema()
            for definition, fields in [('CameraKey', ['t']), ('Keyframe', ['t']), ('Overlay', ['start', 'end'])]:
                for field in fields:
                    schema['$defs'][definition]['properties'][field]['maximum'] = phase['duration']
            speech = []
            if alignment:
                text = ''.join(alignment['characters'])
                speech = [{'text': word[0], 't': alignment['character_start_times_seconds'][word.start()]}
                          for word in re.finditer(r'\S+', text)]
            timing_instructions = (
                'Later keys may have cue: an EXACT short phrase from the voiceover. '
                'A cue REPLACES t (or overlay start) with the FIRST occurrence of that phrase in the audio; '
                'the resolved time must still be strictly after the preceding key and before the next. '
                'Do not reuse a cue in one key sequence or add a cue to its initial key. '
                'Use the speech word times below to check ordering before returning JSON. '
                'Give overlays a cue to reveal them during the related sentence; end must be after the resolved start. '
                if alignment else
                'No speech timestamps are available. Omit every cue field and use numeric t/start/end times. ')
            prompt = ('Return ONLY JSON for a real Three.js editorial infographic scene. Do not output code.\n'
                      + style_context['skill'] + '\nSTYLE PRESET:\n' + json.dumps(style_context.get('preset', {}), ensure_ascii=False)
                      + '\nJSON SCHEMA:\n' + json.dumps(schema)
                      + '\nGeometry units: sphere radius=1, box/plane size=1, cylinder/cone radius=.5 height=1, torus radius=1 tube=.06. '
                      'All rotation values are radians. Use parent group nodes to build recognizable detailed subjects. '
                      'Use enough separate parts for readable solar panels, body and structures, not a featureless block. '
                      'stars makes a seeded distant field. Texture earth is a locally bundled photographic global Earth map. '
                      'Nodes support only texture earth; do not invent any other texture. '
                      'Camera and every track must begin at t=0 with no cue. '
                      'Each key sequence must be strictly increasing, with no duplicate times. '
                      + timing_instructions
                      + f"Times are absolute seconds LOCAL to this phase, between 0 and {phase['duration']} inclusive. "
                      'Use this exact measured duration for final keys; do not round it up or use the full video duration. '
                      'Overlays x/y are normalized top-left screen coordinates. A target label anchors to a mesh. '
                      'Connector target/anchor and endTarget/endAnchor are mesh-local 3D endpoints BEFORE scale; '
                      'on a scaled sphere a surface anchor still has length 1, not the world radius. '
                      'Leave empty space for the photo cards. Render the requested references as image overlays. '
                      'No permanent bottom caption strip. Do not use voiceover as full-screen copy.\n'
                      + 'REFERENCES:\n' + json.dumps(references, ensure_ascii=False)
                      + '\nSPEECH WORD TIMES (seconds within this phase):\n' + json.dumps(speech, ensure_ascii=False)
                      + '\nFULL SCRIPT CONTEXT:\n' + json.dumps({'title': script['title'], 'assets': script['assets']}, ensure_ascii=False)
                      + '\nPHASE:\n' + json.dumps(phase, ensure_ascii=False))
            (output / 'prompts').mkdir(exist_ok=True)
            from plant_kurzge import extract_json
            for attempt in range(3):
                (output / 'prompts' / f'phase_{index}_3d.txt').write_text(prompt, encoding='utf-8')
                response = request(prompt)
                (output / 'prompts' / f'phase_{index}_3d_response_{attempt + 1}.txt').write_text(response, encoding='utf-8')
                try:
                    plan = validate_plan(extract_json(response), phase, references, alignment)
                    break
                except ValueError as error:
                    if attempt == 2:
                        raise ValueError(f'Cảnh 3D {index} không hợp lệ: {error}') from error
                    prompt += ('\nREJECTED JSON RESPONSE:\n' + response
                               + '\nRepair the JSON; validation failed: ' + str(error)
                               + '\nReturn the complete corrected scene JSON, preserving the subject and valid geometry.')
            path.write_text(json.dumps({'fingerprint': fingerprint, 'plan': plan}, ensure_ascii=False), encoding='utf-8')
        textures = {}
        if any(n['material']['texture'] == 'earth' for n in plan['nodes']):
            if not texture.is_file():
                raise ValueError('Thiếu texture Trái Đất cục bộ trong style 3D.')
            textures['earth'] = 'data:image/jpeg;base64,' + base64.b64encode(texture.read_bytes()).decode()
            shutil.copy2(texture, output / 'assets' / 'earth.jpg')
            if source_manifest.exists():
                shutil.copy2(source_manifest, output / 'assets' / 'sources.json')
        render_plan = {**plan, 'textures': textures}
        (output / f'phase_{index}.html').write_text(phase_page(phase, render_plan, reference_data, fingerprint), encoding='utf-8')
        if on_progress:
            on_progress('phases', index, len(script['phases']))
    from generate_kurzge import write_index
    write_index(script, output, fingerprint)
    return fingerprint


def verify_phases(output, script, fingerprint):
    from render_hyperframes import MetadataParser
    rows = []
    references = json.loads((output / 'references.json').read_text()) if (output / 'references.json').exists() else []
    for index, phase in enumerate(script['phases'], 1):
        page = (output / f'phase_{index}.html').read_text()
        metadata = MetadataParser(page)
        scene, mesh = metadata.data('scene-data'), metadata.data('mesh-data')
        cached = json.loads((output / f'phase_{index}.scene.json').read_text())
        alignment = json.loads((output / phase['audio']['alignment']).read_text())['alignment'] if phase.get('audio') else None
        plan = validate_plan(cached['plan'], phase, references, alignment)
        if (scene['phase'] != phase or scene['renderer'] != VERSION or scene['fingerprint'] != fingerprint
                or cached['fingerprint'] != fingerprint or {k: v for k, v in mesh['plan'].items() if k != 'textures'} != plan):
            raise ValueError(f'Cảnh 3D {index} không khớp snapshot.')
        if not (output / 'assets/runtime/three-scene.js').is_file():
            raise ValueError('Thiếu runtime 3D.')
        rows.append({'id': str(phase['id']), 'name': phase['name'], 'duration': phase['duration'],
                     'url': f'/api/previews/{output.name}/phase_{index}.html'})
    return rows
