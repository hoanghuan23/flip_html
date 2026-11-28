"""Shared staging rules and checks on the scene actually drawn in the browser.

The model names the intended relationships. The checker measures the rendered
transforms against PNG alpha bounds; it does not infer semantics from pixels.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

VERSION = 'scene-logic-v1'
NS = 'http://www.w3.org/2000/svg'
ROOT = Path(__file__).resolve().parent

REAL_WORLD_RULES = """
LOGIC OF THE DEPICTED WORLD (applies to every subject, prop and environment):
Plan the action as a causal interaction, not as independently arranged pictures.
Identify each physical object's support, contact surface, container, attachment,
free motion or intentional diagram role at each beat. A seated body's pelvis
rests on the seat being used; hands reach the controls or held object. Walking
feet meet the traversable surface. Rigid bodies do not pass through solid objects.
Held/carried/attached parts follow the relevant contact point as either object
moves or changes pose. A receiving object must be present before an interaction;
the visible result must follow its cause. Show transfer paths from actual source
to actual destination. Maintain mass, object count, identity and spatial continuity
unless the story explicitly changes them. Soft objects drape over and occlude the
surface they cover; overlap alone does not establish support or contact.
Use a coherent camera and world scale, meaningful reach and usable clearances.
Check the entire occupied silhouette and swept path, not only object centers.
An object's relationship can change over time: release before free motion, land
before resting, grasp before carrying. Show the intermediate action the story needs.
Dreams, cutaways, diagrams and intentional exaggeration need an explicit separate
space or transition; do not accidentally depict them as literal physical movement.
Assign one owner to every visible component: scenery excludes independently
rendered objects. A prop must not exist both painted into the background and as
a separate foreground copy. Labels and effects must not become physical supports.
If the planned coordinates contradict the intended interaction, resolve the
staging using actual visible bounds; preserve narrative, action order and timing.
Do not hide a contradiction by shrinking a subject, moving a label, or changing
paint order alone. Validate support, contact, occlusion, reach, collision and
cause/effect together at the beginning, middle, end and every interaction change.
"""

CONTRACT_PROMPT = """
REQUIRED MACHINE-CHECKED SCENE CONTRACT:
Return the SVG with one direct <desc id="scene-logic"> containing JSON:
{"version":1,"instances":[
 {"id":"unique-use-id","asset":"EXACT_ASSET_OR_POSE_ID","space":"world-name",
  "mode":"supported|attached|contained|free|environment|overlay","reason":"why this mode fits the action"}
],"relations":[
 {"type":"supported_by","a":"use-id","b":"support-use-id","start":0,"end":2,
  "point":[0.5,1],"surface":[[0,0.3],[1,0.3]],"tolerance":8},
 {"type":"contact","a":"use-id","b":"other-use-id","start":0,"end":2,
  "a_point":[0.8,0.5],"b_point":[0.2,0.6],"tolerance":8},
 {"type":"contained_in","a":"use-id","b":"container-use-id","start":0,"end":2,
  "region":[0,0,1,1],"tolerance":8},
 {"type":"size_ratio","a":"use-id","b":"other-use-id","start":0,"end":2,
  "a_axis":"width|height","b_axis":"width|height","min":0.5,"max":1.2},
 {"type":"covers|in_front|separate","a":"use-id","b":"other-use-id","start":0,"end":2}
],"causality":[{"cause":0,"effect":1,"trigger":"start|end"}]}
Include ONLY applicable relations, never copy example values or object counts.
Every artwork <use>, including hidden states/backgrounds, must have a unique id
and exactly one instance declaration. asset is its exact href without #. Assign
physical objects to their real space. Overlay = diagram/annotation explicitly
requested by the story; never classify a person or prop as an overlay to skip checks.
free = intentional airborne/unsupported motion, not a workaround for floating.
For supported/attached/contained instances declare respectively supported_by,
contact or contained_in over every interval they are visible in that mode.
Relations can cover shorter intervals and refer to individual pose-use ids, so
support/attachment may change correctly with the story. Different poses may have
different modes; the visible pose must satisfy its active relation throughout.
Every coexisting pair that interacts needs its appropriate relationship. Include
separate for solid obstacles along a moving object's path; in_front for intended
depth order; covers for an object that actually overlaps and covers another.
Use size_ratio where real-world size/reach is essential to the action; derive
its bounds from the subject and camera, never a universal human/prop ratio.
Points, surface endpoints and region are fractions of the MEASURED VISIBLE BOUNDS
of each PNG, not fractions of its transparent canvas. region is [left,top,right,bottom]
in b's local visible bounds. Use actual anatomical/functional contact points, not
the bitmap center or bottom when that is not the real point of contact.
tolerance is in scene pixels, 0..16; it is a small drawing allowance, not permission
to miss the target. covered objects and supports must actually overlap/be visible.
causality uses zero-based action indices from PHASE; effect starts at/after the
cause's named trigger. Include the causal dependencies described by the story,
not just decorative effects. Use [] only when there are no such dependencies.
The browser checker seeks every 0.1s AND either side of action/relation boundaries,
measures actual animated transforms/opacity and checks those relationships.
It rejects missing contracts, floating contacts, lost supports, wrong paint order,
collisions, duplicate visible copies and premature effects. Fix the scene, do not
remove an applicable relation or reclassify an object to bypass validation.
Keep <use> x=y=0 (position/scale/rotation live on wrappers). Escape JSON as XML
text when necessary (&amp;, &lt;). The desc is data, never visible screen text.
This is the single exception to the earlier instruction limiting direct SVG
children to style/artwork: the machine-readable desc is required as well.
"""


def _number(value):
    return type(value) in (float, int) and math.isfinite(value)


def validate_contract(root, phase, asset_ids):
    """Reject malformed/vacuous declarations before invoking a browser."""
    def require(condition, message):
        if not condition:
            raise ValueError('Logic cảnh: ' + message)

    nodes = root.findall(f'{{{NS}}}desc[@id="scene-logic"]')
    require(len(nodes) == 1, 'thiếu đúng một <desc id="scene-logic"> với quan hệ tương tác.')
    try:
        contract = json.loads(nodes[0].text or '')
    except ValueError as error:
        raise ValueError('Logic cảnh: JSON scene-logic không hợp lệ.') from error
    require(isinstance(contract, dict) and type(contract.get('version')) is int
            and contract['version'] == 1, 'version phải là 1.')
    instances = contract.get('instances')
    require(isinstance(instances, list) and 0 < len(instances) <= 512, 'instances phải là danh sách không rỗng.')
    artwork = root.find(f'{{{NS}}}g[@id="artwork"]')
    require(artwork is not None, 'thiếu artwork.')
    uses = list(artwork.iter(f'{{{NS}}}use'))
    declared = {}
    for item in instances:
        require(isinstance(item, dict), 'instance phải là object.')
        iid = item.get('id')
        require(isinstance(iid, str) and re.fullmatch(r'[A-Za-z_][\w-]*', iid, re.ASCII)
                and iid not in declared, 'id instance phải hợp lệ và duy nhất.')
        require(isinstance(item.get('asset'), str) and item['asset'] in asset_ids, f'{iid}: asset không tồn tại.')
        require(isinstance(item.get('mode'), str)
                and item['mode'] in {'supported', 'attached', 'contained', 'free', 'environment', 'overlay'},
                f'{iid}: mode không hợp lệ.')
        for field in ('space', 'reason'):
            require(isinstance(item.get(field), str) and bool(item[field].strip()), f'{iid}: thiếu {field}.')
        declared[iid] = item
    require(len(uses) == len(declared) and {u.get('id') for u in uses} == set(declared),
            'mỗi <use> cần id duy nhất và một instance tương ứng.')
    for use in uses:
        iid = use.get('id')
        href = use.get('href') or use.get('{http://www.w3.org/1999/xlink}href', '')
        require(href == '#' + declared[iid]['asset'], f'{iid}: asset không khớp href.')
        require(all(use.get(k, '0') in ('0', '0.0') for k in ('x', 'y')),
                f'{iid}: đặt vị trí bằng wrapper, giữ use x=y=0.')
    relations = contract.get('relations')
    require(isinstance(relations, list) and len(relations) <= 2048, 'relations phải là danh sách.')

    def point(value):
        return isinstance(value, list) and len(value) == 2 and all(_number(v) and 0 <= v <= 1 for v in value)

    for relation in relations:
        require(isinstance(relation, dict), 'relation phải là object.')
        kind, a, b = (relation.get(k) for k in ('type', 'a', 'b'))
        require(isinstance(kind, str) and kind in {'supported_by', 'contact', 'contained_in', 'covers', 'in_front', 'separate', 'size_ratio'},
                'loại quan hệ không hỗ trợ.')
        require(isinstance(a, str) and isinstance(b, str) and a in declared and b in declared and a != b,
                'quan hệ cần hai instance khác nhau có thật.')
        require(declared[a]['space'] == declared[b]['space'], f'{a}/{b}: tương tác giữa hai không gian khác nhau.')
        start, end = relation.get('start'), relation.get('end')
        require(_number(start) and _number(end) and 0 <= start < end <= phase['duration'],
                f'{a}/{b}: khoảng quan hệ ngoài duration.')
        tolerance = relation.get('tolerance', 8)
        require(_number(tolerance) and 0 <= tolerance <= 16, f'{a}/{b}: tolerance phải trong 0..16 pixel.')
        if kind == 'supported_by':
            surface = relation.get('surface')
            require(point(relation.get('point')) and isinstance(surface, list) and len(surface) == 2
                    and all(point(p) for p in surface) and surface[0] != surface[1], f'{a}/{b}: thiếu điểm tựa/bề mặt đỡ.')
        if kind == 'contact':
            require(point(relation.get('a_point')) and point(relation.get('b_point')), f'{a}/{b}: thiếu điểm tiếp xúc.')
        if kind == 'contained_in':
            region = relation.get('region')
            require(isinstance(region, list) and len(region) == 4 and all(_number(v) and 0 <= v <= 1 for v in region)
                    and region[0] < region[2] and region[1] < region[3], f'{a}/{b}: vùng chứa không hợp lệ.')
        if kind == 'size_ratio':
            require(all(relation.get(k) in ('width', 'height') for k in ('a_axis', 'b_axis'))
                    and all(_number(relation.get(k)) for k in ('min', 'max'))
                    and 0 < relation['min'] <= relation['max'] <= 1000, f'{a}/{b}: khoảng tỷ lệ không hợp lệ.')
    for iid, item in declared.items():
        needed = {'supported': 'supported_by', 'attached': 'contact', 'contained': 'contained_in'}.get(item['mode'])
        require(not needed or any(r['a'] == iid and r['type'] == needed for r in relations),
                f'{iid}: mode {item["mode"]} thiếu quan hệ {needed}.')
    causes = contract.get('causality')
    require(isinstance(causes, list), 'causality phải là danh sách.')
    graph = {}
    for cause in causes:
        require(isinstance(cause, dict), 'causality phải chứa object.')
        a, b, trigger = (cause.get(k) for k in ('cause', 'effect', 'trigger'))
        require(type(a) is int and type(b) is int and a != b and 0 <= a < len(phase['actions'])
                and 0 <= b < len(phase['actions']) and isinstance(trigger, str)
                and trigger in {'start', 'end'}, 'chỉ số/trigger nguyên nhân không hợp lệ.')
        require(phase['actions'][b]['start'] >= phase['actions'][a][trigger],
                f'action {b}: kết quả xảy ra trước nguyên nhân action {a}.')
        graph.setdefault(a, []).append(b)

    def visit(node, active, seen):
        require(node not in active, 'chuỗi nguyên nhân bị vòng lặp.')
        if node not in seen:
            for child in graph.get(node, []):
                visit(child, active | {node}, seen)
            seen.add(node)

    seen = set()
    for node in graph:
        visit(node, set(), seen)
    return contract, nodes[0]


def check_scene(svg, contract, geometry, phase, output, index):
    """Seek the actual SVG/CSS, including between actions, before publication."""
    times = {0., float(phase['duration'])}
    times.update(i / 10 for i in range(1, math.ceil(phase['duration'] * 10)))
    for entry in [*phase['actions'], *contract['relations']]:
        for boundary in (entry['start'], entry['end']):
            times.update(max(0., min(phase['duration'], boundary + delta)) for delta in (-.001, 0, .001))
    payload = {'svg': svg, 'contract': contract, 'geometry': geometry, 'phase': phase, 'times': sorted(times)}
    checker = ROOT / 'frontend/scripts/check-scene-logic.cjs'
    checker_hash = hashlib.sha256(Path(__file__).read_bytes() + checker.read_bytes()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps({'version': VERSION, 'checker': checker_hash, **payload}, sort_keys=True).encode()).hexdigest()
    report_path = output / f'phase_{index}.logic.json'
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if report.get('fingerprint') == fingerprint and report.get('passed') is True:
            return
    except (OSError, ValueError):
        pass
    try:
        result = subprocess.run(['node', str(checker)],
                                input=json.dumps(payload), capture_output=True, text=True, timeout=60, cwd=ROOT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('Không chạy được kiểm tra logic cảnh bằng Node/Chrome.') from error
    if result.returncode:
        raise ValueError('Không chạy được kiểm tra logic cảnh: ' + result.stderr.strip()[-1200:])
    try:
        report = json.loads(result.stdout)
    except ValueError as error:
        raise ValueError('Bộ kiểm tra logic cảnh không trả JSON hợp lệ.') from error
    report.update(fingerprint=fingerprint, version=VERSION, visual_review='required')
    temporary = report_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(report_path)
    if not report.get('passed'):
        raise ValueError('Logic cảnh: ' + '; '.join(report.get('errors', ['Kiểm tra thất bại.'])[:12]))
