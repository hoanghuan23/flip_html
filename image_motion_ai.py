"""PNG asset library from generate_image, animated by the main SVG/CSS pipeline."""

import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET

import flat_motion_ai as vector
from image_asset_generator import ImageAssetGenerator

VERSION = "image-motion-v1"
NS = vector.NS


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
        specs.append({**asset, "width": width, "height": height, "transparent": not background,
                      "base_pose": base_pose})
    return specs


def asset_prompt(script, asset, pose):
    return ("Generate exactly ONE reusable PNG illustration asset, not a complete scene.\n"
            "Detailed editorial illustration with light 2.5D scientific explainer shading. "
            "Keep palette, identity, lighting and anchor consistent across poses. "
            "No captions, watermark, invented labels or unrelated objects.\n"
            + "ASSET: " + json.dumps({k: asset.get(k) for k in ("id", "name", "category", "description")}, ensure_ascii=False)
            + "\nRender ONLY this pose: " + pose
            + "\nSTYLE: " + json.dumps(script.get("style", {}), ensure_ascii=False)
            + "\nCAMERA/STATE CONTEXT (choose the view specified for this pose): "
            + json.dumps([{k: p.get(k) for k in ("camera", "initial_state", "final_state", "actions")}
                          for p in script["phases"]], ensure_ascii=False)
            + f"\nLogical local canvas: {asset['width']}x{asset['height']}. "
            + ("Origin at top left (0,0), full scene canvas 1920x1080. "
               "Keep the caption area y=792..1080 plain. Do not include foreground subjects."
               if not asset["transparent"] else
               "Origin at the center (0,0). True transparent alpha, including empty margins. "
               "Respect the described local coordinates and silhouette bounds. "
               "Do not crop tightly or recenter between poses. No scenery or painted background."))


def library_prompt(script):
    return "\n\n".join(asset_prompt(script, a, a["base_pose"]) for a in image_specs(script))


def write_asset_prompts(script, output):
    prompts = output / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "assets.txt").write_text(library_prompt(script), encoding="utf-8")
    for asset in image_specs(script):
        for aid, pose in [(asset["id"], asset["base_pose"]),
                          *((p["id"], p["description"]) for p in asset["poses"])]:
            # Asset IDs come from validated Plans; never use them as filesystem paths.
            name = vector.digest(aid)[:16]
            (prompts / f"image_{name}.txt").write_text(asset_prompt(script, asset, pose), encoding="utf-8")


def prompt_library(script):
    """Describe local geometry without sending PNG base64 to the text endpoint."""
    return json.dumps(image_specs(script), ensure_ascii=False)


def phase_prompt(script, index, library, previous=None):
    if previous:
        root = ET.fromstring(previous)
        for element in list(root):
            if element.get("id") == "program-assets":
                root.remove(element)
        previous = ET.tostring(root, encoding="unicode")
    return (vector.phase_prompt(script, index, library, previous).replace("texture, ảnh raster", "texture")
            + "\nTHƯ VIỆN PNG: chương trình đã vẽ mọi asset/pose qua generate_image. "
            "Chỉ tham chiếu các ID được liệt kê bằng <use>; không trả image, base64 hoặc defs. "
            "Mỗi PNG đã nằm trong nhóm local: nền gốc trên trái, asset khác gốc giữa. "
            "Morph dùng các pose PNG riêng và crossfade theo đúng mốc Plan, không nội suy path. "
            "Không vẽ lại chủ thể bằng hình học SVG.")


class Renderer(vector.Renderer):
    def prepare(self):
        write_asset_prompts(self.script, self.output)
        generator = ImageAssetGenerator(self.output / "image_cache")
        root = ET.Element(f"{{{NS}}}svg", {"viewBox": "0 0 1920 1080"})
        defs = ET.SubElement(root, f"{{{NS}}}defs", {"id": "shared-assets"})
        assets_dir = self.output / "assets"
        assets_dir.mkdir(exist_ok=True)
        metadata = []
        for asset in image_specs(self.script):
            generated = {}
            for aid, pose in [(asset["id"], asset["base_pose"]),
                              *((p["id"], p["description"]) for p in asset["poses"])]:
                if pose not in generated:
                    print(f"  generate_image: {asset['id']} ({pose})…", flush=True)
                    generated[pose] = generator.generate(asset_prompt(self.script, asset, pose),
                                                        transparent=asset["transparent"],
                                                        requested_size=[asset["width"], asset["height"]])
                path, info = generated[pose]
                data = path.read_bytes()
                filename = vector.digest(aid)[:16] + ".png"
                (assets_dir / filename).write_bytes(data)
                group = ET.SubElement(defs, f"{{{NS}}}g", {"id": aid})
                ET.SubElement(group, f"{{{NS}}}image", {
                    "href": "data:image/png;base64," + base64.b64encode(data).decode("ascii"),
                    "x": str(-asset["width"] / 2 if asset["transparent"] else 0),
                    "y": str(-asset["height"] / 2 if asset["transparent"] else 0),
                    "width": str(asset["width"]), "height": str(asset["height"]),
                    "preserveAspectRatio": "none"})
                metadata.append({"id": aid, "pose": pose, "file": "assets/" + filename,
                                 "sha256": hashlib.sha256(data).hexdigest(), **info})
        self.library = ET.tostring(root, encoding="unicode")
        self.fingerprint = vector.digest({"version": VERSION, "script": self.script, "library": self.library})
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
        result = super().clean_phase(raw, index)
        return result.replace(f'data-renderer="{vector.VERSION}"', f'data-renderer="{VERSION}"', 1)

    def render(self, index, previous=None):
        prompt = phase_prompt(self.script, index, prompt_library(self.script), previous)
        (self.output / "prompts" / f"phase_{index}.txt").write_text(prompt, encoding="utf-8")
        return self.generate(prompt, lambda raw: self.clean_phase(raw, index))
