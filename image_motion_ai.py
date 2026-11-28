"""PNG asset library from generate_image, animated by the main SVG/CSS pipeline."""

import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET

import flat_motion_ai as vector
from image_asset_generator import ImageAssetGenerator, validate_png
from character_assets import CharacterAssets, is_xeko, reference_prompt
from scene_logic import REAL_WORLD_RULES, CONTRACT_PROMPT, check_scene, validate_contract

VERSION = "image-motion-rig-v1"
NS = vector.NS


def hidden_pose(pose):
    return bool(re.search(r'\b(?:(?:chưa|không(?: còn)?)\s+(?:xuất hiện|hiển thị)'
                          r'|hidden|invisible|not\s+(?:visible|shown))\b', pose, re.I))


def image_specs(script):
    """One local canvas per asset, shared by all its poses and phases."""
    specs = []
    for asset in vector.asset_spec(script):
        background = asset["category"] == "background"
        sizes = re.findall(r"(\d+)\s*[x×]\s*(\d+)", asset.get("description", ""))
        width, height = ((1920, 1080) if background else
                         (max(int(w) for w, _ in sizes), max(int(h) for _, h in sizes)) if sizes else (512, 512))
        if not 1 <= width <= 8192 or not 1 <= height <= 8192:
            raise ValueError(f"{asset['id']}: kích thước asset ngoài khoảng 1..8192.")
        first = re.search(r"\bpose\s+([\w-]+)\s*:", asset.get("description", ""), re.I)
        base_pose = first[1] if first else (asset["poses"][0]["description"] if asset["poses"] else "default")
        # A shared canvas must contain the complete pose envelope. In particular,
        # turning a tall subject sideways must not shrink it to the old width.
        reference_size = [width, height]
        if not background and asset['poses']:
            width = height = max(width, height)
        camera_views = [{k: phase['camera'].get(k) for k in ('view', 'detail')}
                        for phase in script['phases']
                        if any(action['target'] == asset['id'] for action in phase['actions'])]
        specs.append({**asset, 'camera_views': camera_views,
                      "width": width, "height": height, "reference_size": reference_size, "transparent": not background,
                      "base_pose": base_pose})
    return specs


def asset_prompt(script, asset, pose, style_context=None):
    prompt = ("Generate exactly ONE reusable PNG illustration asset, not a complete scene.\n"
            "Keep palette, identity, lighting and anchor consistent across poses. "
            "No captions, watermark, invented labels or unrelated objects.\n"
            "Apply the illustration skill's visual style. The asset, pose, canvas and PNG output "
            "requirements below take precedence over its example compositions and workflows. "
            "Do not add example subjects or decor unless required by the Plan.\n"
            "IDENTITY AND POSE CONTRACT:\n"
            "Treat the asset description and complete pose list as one character/object design. "
            "Use the same face, anatomy, component structure, materials, markings and exact "
            "part-by-part clothing colors in every pose. Apply the skill and palette roles "
            "consistently; a new pose or outcome must not trigger a new outfit or color scheme. "
            "An explicit Plan change may alter the specified property (for example shape, "
            "material or clothing); preserve every other identity feature. Pose/expression "
            "changes alone are not a redesign. "
            "For a group, keep each member's identity, outfit, relative height and total count. "
            "Keep body/object scale and support anchor fixed on the shared local canvas. "
            "Allow a wider silhouette for a wider pose; do not independently fit each pose "
            "to fill the image or shrink the whole subject. Preserve margin for the full pose set. "
            "Respect declared visible bounds, contact points, handles and emission outlets. "
            "For primary subjects and backgrounds, do not bake moving parts supplied as "
            "separate assets, transient action effects, safety/result checkmarks or UI annotations "
            "into the base artwork. A dedicated effect asset must depict its requested effect. "
            "Render only the requested pose, never a pose sheet or multiple views.\n"
            + REAL_WORLD_RULES
            + "ILLUSTRATION SKILL:\n" + vector.load_style(style_context)
            + "\nASSET: " + json.dumps({k: asset.get(k) for k in ("id", "name", "category", "description")}, ensure_ascii=False)
            + "\nBASE POSE (shared identity/scale description): " + asset["base_pose"]
            + "\nCOMPLETE POSE SET (design consistently; render only the requested one): "
            + json.dumps([asset["base_pose"], *(p["description"] for p in asset["poses"])], ensure_ascii=False)
            + "\nSHARED CAST/OBJECT DESIGN CONTEXT: "
            + json.dumps([{k: a.get(k) for k in ("id", "category", "description")}
                          for a in script["assets"]], ensure_ascii=False)
            + "\nRender ONLY this pose: " + pose
            + "\nSTYLE: " + json.dumps(script.get("style", {}), ensure_ascii=False)
            + "\nCAMERA/STATE CONTEXT (choose the view specified for this pose): "
            + json.dumps([{k: p.get(k) for k in ("camera", "initial_state", "final_state", "actions")}
                          for p in script["phases"]], ensure_ascii=False)
            + f"\nLogical local canvas: {asset['width']}x{asset['height']}. "
            + f"Reference visible dimensions before a pose change: {asset['reference_size']}. "
              "The canvas reserves the envelope of all poses; empty space is allowed. "
              "Changing orientation does not shorten body/part lengths. "
            + ("Origin at top left (0,0), full scene canvas 1920x1080. "
               "Use the full canvas for scenery, with no reserved caption strip. Do not include foreground subjects."
               if not asset["transparent"] else
               "Origin at the center (0,0). True transparent alpha, including empty margins. "
               "Respect the described local coordinates and silhouette bounds. "
               "Do not crop tightly or recenter between poses. No scenery or painted background."))
    if not asset['transparent']:
        prompt += ('\nSCENERY OWNERSHIP: Do NOT draw any of these independently rendered subjects/objects, '
                   'even if the background description mentions their location or support region:\n'
                   + json.dumps([{k: a.get(k) for k in ('id', 'name', 'description')}
                                 for a in script['assets'] if a['category'] != 'background'], ensure_ascii=False)
                   + '\nLeave their occupied regions available. Draw only the room/landscape/static environment; '
                     'a support supplied as a separate asset must not also be painted into this image.')
    if hidden_pose(pose):
        visible = next((p['description'] for p in asset['poses'] if not hidden_pose(p['description'])),
                       asset.get('description', ''))
        prompt += ("\nVISIBILITY OVERRIDE: The requested hidden/not-yet-shown state belongs to the "
                   "animation timeline, not the PNG pixels. Draw the underlying subject fully visible "
                   "with nonzero alpha; only the surrounding background is transparent. "
                   "Never return a blank or fully transparent PNG. The animation will hide this image "
                   "with opacity=0 until its appearance cue. Use this visible artwork for the subject: "
                   + visible)
    return prompt


def library_prompt(script, style_context=None):
    return "\n\n".join(asset_prompt(script, a, a["base_pose"], style_context) for a in image_specs(script))


def write_asset_prompts(script, output, style_context=None):
    prompts = output / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "assets.txt").write_text(library_prompt(script, style_context), encoding="utf-8")
    for asset in image_specs(script):
        for aid, pose in [(asset["id"], asset["base_pose"]),
                          *((p["id"], p["description"]) for p in asset["poses"])]:
            # Asset IDs come from validated Plans; never use them as filesystem paths.
            name = vector.digest(aid)[:16]
            (prompts / f"image_{name}.txt").write_text(asset_prompt(script, asset, pose, style_context), encoding="utf-8")


def prompt_library(script, metadata=None):
    """Describe local geometry without sending PNG base64 to the text endpoint."""
    return json.dumps({'assets': image_specs(script), 'measured_geometry': metadata or [],
                       'coordinates': 'bounds are actual visible alpha in local SVG units; PNG margins are empty'},
                      ensure_ascii=False)


def phase_prompt(script, index, library, previous=None, *, style_context=None):
    if previous:
        root = ET.fromstring(previous)
        for element in list(root):
            if element.get("id") == "program-assets":
                root.remove(element)
        previous = ET.tostring(root, encoding="unicode")
    return (vector.phase_prompt(script, index, library, previous, style_context=style_context).replace("texture, ảnh raster", "texture")
            + "\nTHƯ VIỆN PNG: chương trình đã vẽ mọi asset/pose qua generate_image. "
            "Chỉ tham chiếu các ID được liệt kê bằng <use>; không trả image, base64 hoặc defs. "
            "Mỗi PNG đã nằm trong nhóm local: nền gốc trên trái, asset khác gốc giữa. "
            "Morph dùng các pose PNG riêng và crossfade theo đúng mốc Plan, không nội suy path. "
            "Không vẽ lại chủ thể bằng hình học SVG. "
            "Canvas PNG có khoảng trong suốt; không coi cạnh canvas là silhouette hoặc điểm tiếp xúc. "
            "Dùng kích thước phần hình và các điểm neo/điểm phát mà Plan mô tả để đặt tỷ lệ và hiệu ứng. "
            "Không điều khiển riêng chi tiết đã nằm trong một PNG: gắn lớp SVG phụ cạnh <use> "
            "trong cùng hệ tọa độ, thay điểm gắn theo pose khi cần. Hiệu ứng hành động đã nêu "
            "được vẽ bằng SVG phụ theo quy tắc chung; không được bỏ chỉ vì không có PNG hiệu ứng riêng. "
            "Pose chỉ mô tả chưa xuất hiện/chưa hiển thị/ẩn vẫn có PNG chứa hình nhìn thấy được. "
            "Trong animation, trạng thái đó phải có opacity=0. Khi chuyển từ ẩn sang hiện, "
            "dùng opacity 0→1 theo mốc action; không crossfade hai ảnh cùng nhìn thấy được. "
            "Khi chuyển từ hiện sang ẩn, dùng opacity 1→0."
            + CONTRACT_PROMPT)


def measured_geometry(library):
    """Measure source alpha in the same uniform image transform used by SVG."""
    rows = []
    for group in ET.fromstring(library).find(f'{{{NS}}}defs'):
        image = group.find(f'{{{NS}}}image')
        if image is None:
            continue
        data = base64.b64decode(image.get('href').split(',', 1)[1], validate=True)
        info = validate_png(data)
        cw, ch = float(image.get('width')), float(image.get('height'))
        iw, ih = info['size']
        scale = min(cw / iw, ch / ih)
        x = float(image.get('x')) + (cw - iw * scale) / 2
        y = float(image.get('y')) + (ch - ih * scale) / 2
        left, top, right, bottom = info.get('visible_bbox', info['content_bbox'])
        rows.append({'id': group.get('id'), 'bounds': [x + left * scale, y + top * scale,
                                                      x + right * scale, y + bottom * scale]})
    return rows


class Renderer(vector.Renderer):
    def prepare(self):
        write_asset_prompts(self.script, self.output, self.style_context)
        generator = ImageAssetGenerator(self.output / "image_cache")
        characters = CharacterAssets(self.style_context, self.output)
        root = ET.Element(f"{{{NS}}}svg", {"viewBox": "0 0 1920 1080"})
        defs = ET.SubElement(root, f"{{{NS}}}defs", {"id": "shared-assets"})
        assets_dir = self.output / "assets"
        assets_dir.mkdir(exist_ok=True)
        metadata = []
        specs = image_specs(self.script)
        total = sum(len({a['base_pose'], *(p['description'] for p in a['poses'])}) for a in specs)
        completed = 0
        self.progress('images', completed, total)
        for asset in specs:
            generated = {}
            xeko = characters.enabled and is_xeko(asset)
            character = characters.enabled and asset['category'] == 'character'
            for aid, pose in [(asset["id"], asset["base_pose"]),
                              *((p["id"], p["description"]) for p in asset["poses"])]:
                if pose not in generated:
                    print(f"  generate_image: {asset['id']} ({pose})…", flush=True)
                    try:
                        references = characters.references(pose + ' ' + asset['description'], asset) if xeko else []
                        if not references:
                            for index, phase in enumerate(self.script['phases'], 1):
                                still = self.output / f'phase_{index}.preview.png'
                                if still.is_file() and asset['id'] in json.dumps(phase):
                                    references = [still]
                                    break
                        prompt = asset_prompt(self.script, asset, pose, self.style_context)
                        prompt += reference_prompt(references, self.output)
                        (self.output / 'prompts' / f'image_{vector.digest(aid)[:16]}.txt').write_text(
                            prompt, encoding='utf-8')
                        generated[pose] = characters.reuse(asset, pose) or generator.generate(
                            prompt, transparent=asset["transparent"],
                            requested_size=[asset["width"], asset["height"]], reference_images=references)
                    except ValueError as error:
                        raise ValueError(f"Asset {asset['id']} ({pose}): {error}") from error
                    completed += 1
                    self.progress('images', completed, total)
                path, info = generated[pose]
                data = path.read_bytes()
                filename = vector.digest(aid)[:16] + ".png"
                relative = 'characters/poses/' + filename if character else filename
                target = assets_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                if character:
                    characters.record(aid, pose, target, info,
                                      references, asset=asset)
                group = ET.SubElement(defs, f"{{{NS}}}g", {"id": aid})
                ET.SubElement(group, f"{{{NS}}}image", {
                    "href": "data:image/png;base64," + base64.b64encode(data).decode("ascii"),
                    "x": str(-asset["width"] / 2 if asset["transparent"] else 0),
                    "y": str(-asset["height"] / 2 if asset["transparent"] else 0),
                    "width": str(asset["width"]), "height": str(asset["height"]),
                    "preserveAspectRatio": "xMidYMid meet"})
                metadata.append({"id": aid, "pose": pose, "file": "assets/" + relative,
                                 "sha256": hashlib.sha256(data).hexdigest(), **info})
        self.library = ET.tostring(root, encoding="unicode")
        self.geometry = measured_geometry(self.library)
        bounds = {row['id']: row['bounds'] for row in self.geometry}
        for row in metadata:
            row['render_bounds'] = bounds[row['id']]
        self.fingerprint = vector.digest({"version": VERSION, "script": self.script, "library": self.library, "style": self.style_context})
        (self.output / "assets.svg").write_text(self.library, encoding="utf-8")
        (self.output / "assets.meta.json").write_text(json.dumps({"renderer": VERSION,
            "fingerprint": self.fingerprint, "assets": metadata}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self

    def clean_phase(self, raw, index):
        # Strip only program-inserted cache layers before the strict SVG validator.
        # The trusted PNG library is always reattached from validated local images.
        if f'data-renderer="{VERSION}"' in raw:
            root = ET.fromstring(raw)
            if root.get("data-fingerprint") != self.fingerprint:
                raise ValueError("Cache khác kịch bản/thư viện/phiên bản đồ họa.")
            for element in list(root):
                if element.get("id") in {"program-assets", "program-captions"}:
                    root.remove(element)
            root.set("data-renderer", vector.VERSION)
            raw = ET.tostring(root, encoding="unicode")
        # Parse untrusted SVG through the existing security checks BEFORE browser
        # inspection. Remove only the machine contract for the vector validator.
        parsed = vector.parse_svg(raw, self.cleaner, animation=True)
        ids = {e.get('id') for e in ET.fromstring(self.library).iter() if e.get('id')}
        contract, description = validate_contract(parsed, self.script['phases'][index - 1], ids)
        parsed.remove(description)
        raw = ET.tostring(parsed, encoding='unicode')
        result = super().clean_phase(raw, index)
        # Each PNG group is self-contained. Embed only those used by this scene,
        # so a multi-scene player does not decode every full-resolution PNG nine times.
        root = ET.fromstring(result)
        used = {(e.get('href') or e.get('{http://www.w3.org/1999/xlink}href', ''))[1:]
                for e in root.findall(f'.//{{{NS}}}use')}
        defs = root.find(f'{{{NS}}}defs[@id="program-assets"]')
        for group in list(defs):
            if group.get('id') not in used:
                defs.remove(group)
        root.set('data-renderer', VERSION)
        root.insert(1, description)
        result = ET.tostring(root, encoding='unicode')
        if not hasattr(self, 'geometry'):
            self.geometry = measured_geometry(self.library)
        check_scene(result, contract, {r['id']: r for r in self.geometry},
                    self.script['phases'][index - 1], self.output, index)
        return result

    def render(self, index, previous=None):
        prompt = phase_prompt(self.script, index, prompt_library(self.script, self.geometry), previous, style_context=self.style_context)
        (self.output / "prompts" / f"phase_{index}.txt").write_text(prompt, encoding="utf-8")
        return self.generate(prompt, lambda raw: self.clean_phase(raw, index))
