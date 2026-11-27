#!/usr/bin/env python3
"""Ghép PNG theo config thành HTML/SVG độc lập, không sửa ảnh nguồn.

python3 assemble_character.py --check
python3 assemble_character.py --gallery --output storage/character_rig/index.html
python3 assemble_character.py --preset front_happy --output storage/character_rig/happy.svg
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
from html import escape
import json
import math
from pathlib import Path
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parent
JOINT_PARENTS = {"shoulder_L": "arm_L", "shoulder_R": "arm_R"}
SLOTS = {"head", "suit", "arm_L", "arm_R", "legs_pair", "leg_L", "leg_R"} | JOINT_PARENTS.keys()


class CharacterConfigError(ValueError):
    pass


def number(value, label, *, positive=False):
    valid = not isinstance(value, bool) and isinstance(value, (int, float))
    try:
        result = float(value) if valid else math.nan
    except OverflowError:
        result = math.nan
    if not math.isfinite(result) or (positive and result <= 0):
        raise CharacterConfigError(f"{label}: cần số {'dương ' if positive else ''}hữu hạn.")
    return result


def point(value, label, *, positive=False):
    if not isinstance(value, list) or len(value) != 2:
        raise CharacterConfigError(f"{label}: cần mảng [x, y].")
    return tuple(number(v, label, positive=positive) for v in value)


def object_value(value, label):
    if not isinstance(value, dict):
        raise CharacterConfigError(f"{label}: cần object JSON.")
    return value


def load_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CharacterConfigError(f"Không đọc được config {path}: {exc}") from exc
    value = object_value(value, str(path))
    if type(value.get("version")) is not int or value["version"] != 1:
        raise CharacterConfigError(f"{path}: chỉ hỗ trợ version 1.")
    return value


@dataclass(frozen=True)
class Layer:
    slot: str
    source: str
    render_source: str
    path: Path
    size: tuple[int, int]
    scale: float
    x: float
    y: float
    rotation: float
    pivot: tuple[float, float]
    clip_rect: tuple[float, float, float, float] | None = None


class CharacterRig:
    def __init__(self, assets_path=ROOT / "config/character_assets.json",
                 presets_path=ROOT / "config/character_presets.json"):
        self.catalog = load_json(assets_path)
        self.config = load_json(presets_path)
        asset_root = self.catalog.get("asset_root")
        if not isinstance(asset_root, str) or not asset_root:
            raise CharacterConfigError("asset_root: thiếu đường dẫn thư viện ảnh.")
        # asset_root is project-relative, independent of the caller's working directory.
        self.asset_root = (ROOT / asset_root).resolve()
        if not self.asset_root.is_dir():
            raise CharacterConfigError(f"Không tìm thấy asset_root: {self.asset_root}")
        self.assets = object_value(self.catalog.get("assets"), "assets")
        self.profiles = object_value(self.catalog.get("rig_profiles"), "rig_profiles")
        self.presets = object_value(self.config.get("presets"), "presets")
        self.default = self.config.get("default_preset")
        if not isinstance(self.default, str) or self.default not in self.presets:
            raise CharacterConfigError("default_preset không có trong presets.")
        self._image_cache = {}
        self._data_cache = {}

    def asset_path(self, value):
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise CharacterConfigError(f"Đường dẫn ảnh phải tương đối với asset_root: {value!r}")
        path = (self.asset_root / value).resolve()
        if not path.is_relative_to(self.asset_root) or path.suffix.lower() != ".png":
            raise CharacterConfigError(f"Đường dẫn PNG nằm ngoài thư viện hoặc sai định dạng: {value}")
        if not path.is_file():
            raise CharacterConfigError(f"Không tìm thấy ảnh: {value}")
        return path

    def image_size(self, path):
        if path not in self._image_cache:
            try:
                with Image.open(path) as image:
                    if image.format != "PNG" or "A" not in image.getbands():
                        raise CharacterConfigError(f"Ảnh phải là PNG có kênh alpha: {path}")
                    image.load()
                    if not image.getchannel("A").getbbox():
                        raise CharacterConfigError(f"Ảnh hoàn toàn trong suốt: {path}")
                    self._image_cache[path] = image.size
            except OSError as exc:
                raise CharacterConfigError(f"Không đọc được ảnh {path}: {exc}") from exc
        return self._image_cache[path]

    def layout(self, preset_id):
        if not isinstance(preset_id, str) or preset_id not in self.presets:
            raise CharacterConfigError(f"Không có preset: {preset_id!r}")
        preset = object_value(self.presets[preset_id], f"preset {preset_id}")
        profile_id = preset.get("rig_profile")
        if not isinstance(profile_id, str) or profile_id not in self.profiles:
            raise CharacterConfigError(f"{preset_id}: rig_profile không tồn tại.")
        profile = object_value(self.profiles[profile_id], profile_id)
        if not isinstance(preset.get("view"), str) or preset["view"] != profile.get("view"):
            raise CharacterConfigError(f"{preset_id}: góc nhìn không khớp rig_profile.")
        if not isinstance(profile.get("suit_id"), str):
            raise CharacterConfigError(f"{profile_id}: thiếu suit_id.")
        canvas = point(profile.get("canvas"), "canvas", positive=True)
        sockets = object_value(profile.get("sockets"), "sockets")
        parts = object_value(preset.get("parts"), f"{preset_id}.parts")
        slots = set(parts)
        if not {"head", "suit", "arm_L", "arm_R"} <= slots or slots - SLOTS:
            raise CharacterConfigError(f"{preset_id}: cần head, suit, arm_L, arm_R và các slot chân hợp lệ.")
        if not ((slots & {"legs_pair", "leg_L", "leg_R"}) in
                ({"legs_pair"}, {"leg_L", "leg_R"})):
            raise CharacterConfigError(f"{preset_id}: dùng legs_pair HOẶC cả leg_L và leg_R.")
        order = preset.get("layer_order", profile.get("layer_order"))
        if (not isinstance(order, list) or not all(isinstance(s, str) for s in order)
                or len(order) != len(slots) or set(order) != slots):
            raise CharacterConfigError(f"{preset_id}: layer_order phải chứa mỗi slot đúng một lần.")
        transforms = object_value(preset.get("transforms", {}), "transforms")
        if set(transforms) - slots:
            raise CharacterConfigError(f"{preset_id}: transforms chứa slot không có trong parts.")
        layers = []
        for slot in order:
            asset_id = parts[slot]
            if not isinstance(asset_id, str) or asset_id not in self.assets:
                raise CharacterConfigError(f"{preset_id}.{slot}: ảnh chưa đăng ký trong character_assets.json.")
            asset = object_value(self.assets[asset_id], asset_id)
            if asset.get("slot") != slot or asset.get("view") != preset["view"]:
                raise CharacterConfigError(f"{asset_id}: sai slot hoặc góc nhìn cho {preset_id}.{slot}.")
            suits = asset.get("compatible_suits")
            if not isinstance(suits, list) or profile["suit_id"] not in suits:
                raise CharacterConfigError(f"{asset_id}: không tương thích suit {profile['suit_id']}.")
            self.asset_path(asset.get("source"))
            if "reference_source" in asset:
                self.asset_path(asset["reference_source"])
            path = self.asset_path(asset.get("render_source"))
            size = self.image_size(path)
            attach = point(asset.get("attach_point"), f"{asset_id}.attach_point")
            pivot = point(asset.get("pivot"), f"{asset_id}.pivot")
            if any(v < 0 or v > bound for pair in (attach, pivot) for v, bound in zip(pair, size)):
                raise CharacterConfigError(f"{asset_id}: attach_point/pivot nằm ngoài ảnh render_source.")
            clip = None
            if "clip_rect" in asset:
                rect = asset["clip_rect"]
                if not isinstance(rect, list) or len(rect) != 4:
                    raise CharacterConfigError(f"{asset_id}.clip_rect: cần [x, y, width, height].")
                clip = tuple(number(v, f"{asset_id}.clip_rect") for v in rect)
                cx, cy, cw, ch = clip
                if cx < 0 or cy < 0 or cw <= 0 or ch <= 0 or cx + cw > size[0] or cy + ch > size[1]:
                    raise CharacterConfigError(f"{asset_id}.clip_rect: vùng cắt không hợp lệ hoặc nằm ngoài ảnh.")
            transform = object_value(transforms.get(slot, {}), f"transforms.{slot}")
            if set(transform) - {"offset", "scale", "rotation"}:
                raise CharacterConfigError(f"transforms.{slot}: chỉ hỗ trợ offset, scale, rotation.")
            parent_slot = asset.get("parent_slot", slot)
            inherited = {}
            if slot in JOINT_PARENTS:
                if parent_slot != JOINT_PARENTS[slot] or parent_slot not in parts:
                    raise CharacterConfigError(f"{slot}: parent_slot phải là {JOINT_PARENTS[slot]} có trong parts.")
                inherited = object_value(transforms.get(parent_slot, {}), f"transforms.{parent_slot}")
            elif parent_slot != slot:
                raise CharacterConfigError(f"{slot}: chỉ khớp vai được khai báo parent_slot.")
            own_offset = point(transform.get("offset", [0, 0]), f"{slot}.offset")
            parent_offset = point(inherited.get("offset", [0, 0]), f"{slot}.parent_offset")
            offset = tuple(own_offset[i] + parent_offset[i] for i in (0, 1))
            socket = point(sockets.get(parent_slot), f"sockets.{parent_slot}")
            scale = number(number(asset.get("scale"), f"{asset_id}.scale", positive=True)
                           * number(transform.get("scale", 1), f"{slot}.scale", positive=True)
                           * number(inherited.get("scale", 1), f"{slot}.parent_scale", positive=True),
                           f"{slot}.effective_scale", positive=True)
            x, y = (socket[i] + offset[i] - attach[i] * scale for i in (0, 1))
            rotation = (number(transform.get("rotation", 0), f"{slot}.rotation")
                        + number(inherited.get("rotation", 0), f"{slot}.parent_rotation"))
            layers.append(Layer(slot, asset["source"], asset["render_source"], path, size,
                                scale, x, y, rotation,
                                (x + pivot[0] * scale, y + pivot[1] * scale), clip))
        return canvas, layers

    def validate(self):
        for preset_id in self.presets:
            self.layout(preset_id)

    def data_uri(self, path):
        if path not in self._data_cache:
            self._data_cache[path] = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        return self._data_cache[path]

    def svg(self, preset_id, *, debug=False, image_ids=None):
        canvas, layers = self.layout(preset_id)
        description = escape(str(self.presets[preset_id].get("description", preset_id)))
        content = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas[0]:g} {canvas[1]:g}" '
                   f'width="{canvas[0]:g}" height="{canvas[1]:g}" role="img" aria-label="{description}">',
                   f"<title>{description}</title>"]
        for layer in layers:
            width, height = layer.size
            content.append(f'<g data-slot="{layer.slot}" transform="rotate({layer.rotation:g} '
                           f'{layer.pivot[0]:g} {layer.pivot[1]:g})">'
                           f'<g transform="translate({layer.x:g} {layer.y:g}) scale({layer.scale:g})">')
            clip_attr = ""
            if layer.clip_rect is not None:
                clip_id = "clip-" + hashlib.sha256(preset_id.encode()).hexdigest()[:16] + "-" + layer.slot
                x, y, w, h = layer.clip_rect
                content.append(f'<defs><clipPath id="{clip_id}" clipPathUnits="userSpaceOnUse">'
                               f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"/>'
                               '</clipPath></defs>')
                clip_attr = f' clip-path="url(#{clip_id})"'
            if image_ids is None:
                content.append(f'<image width="{width}" height="{height}"{clip_attr} '
                               f'href="{self.data_uri(layer.path)}"/>')
            else:
                content.append(f'<use href="#{image_ids[layer.path]}"{clip_attr}/>')
            content.append('</g></g>')
        if debug:
            for layer in layers:
                x, y = layer.pivot
                content.append(f'<circle cx="{x:g}" cy="{y:g}" r="3" fill="#008dff" '
                               f'stroke="white" stroke-width="1"><title>{layer.slot}</title></circle>')
        return "\n".join(content + ["</svg>"])

    def html(self, preset_ids, *, debug=False):
        image_ids = {}
        definitions = []
        for preset_id in preset_ids:
            _, layers = self.layout(preset_id)
            for layer in layers:
                if layer.path not in image_ids:
                    image_id = f'bitmap-{len(image_ids)}'
                    image_ids[layer.path] = image_id
                    width, height = layer.size
                    definitions.append(f'<image id="{image_id}" data-source="{escape(layer.render_source)}" '
                                       f'width="{width}" height="{height}" href="{self.data_uri(layer.path)}"/>')
        library = ('<svg class="asset-library" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">'
                   '<defs>' + ''.join(definitions) + '</defs></svg>')
        cards = []
        for preset_id in preset_ids:
            preset = self.presets[preset_id]
            config = escape(json.dumps(preset, ensure_ascii=False, indent=2))
            cards.append(f'<article><h2>{escape(preset_id)}</h2>'
                         f'<p>{escape(str(preset.get("description", preset_id)))}</p>'
                         f'<div class="character" data-state="static">'
                         '<p class="image-status" role="status"></p>'
                         f'{self.svg(preset_id, debug=debug, image_ids=image_ids)}</div>'
                         f'<section class="preset-config" aria-label="Config {escape(preset_id)}">'
                         f'<h3>Config: <code>{escape(preset_id)}</code></h3>'
                         f'<pre>{config}</pre></section></article>')
        return '''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ghép nhân vật áo đỏ</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:28px;background:#f3f5f8;color:#202733;font:15px/1.55 system-ui,sans-serif}
main{max-width:1500px;margin:auto}h1{font-size:26px;margin:0}header p{max-width:820px;color:#546173}
.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;margin-top:24px}
article{min-width:0;padding:20px;background:white;border:1px solid #dce2e9;border-radius:16px}
h2{font-size:17px;margin:0}article p{min-height:47px;color:#546173;margin:6px 0}
.character{background-color:#fafbfd;background-image:linear-gradient(45deg,#edf0f5 25%,transparent 25%),linear-gradient(-45deg,#edf0f5 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#edf0f5 75%),linear-gradient(-45deg,transparent 75%,#edf0f5 75%);background-size:20px 20px;background-position:0 0,0 10px,10px -10px,-10px 0;border-radius:10px}
svg{display:block;width:100%;height:auto;max-height:440px}
.preset-config{margin-top:16px}.preset-config>h3{margin:0;padding:10px 12px;background:#edf2f8;border:1px solid #dce2e9;border-radius:8px;color:#202733;font-size:14px;overflow-wrap:anywhere}
pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f8;padding:12px;border-radius:8px}
.asset-library{position:absolute;width:0;height:0;overflow:hidden}
.character{position:relative}.image-status{position:absolute;inset:0;display:none;place-content:center;padding:16px;text-align:center}
.character[data-state="error"]>svg{visibility:hidden}
.character[data-state="error"]>.image-status{display:grid;color:#9c1c24}
@media(max-width:540px){body{padding:16px}.gallery{grid-template-columns:1fr}}
</style></head><body>
<main><header><h1>Ghép nhân vật áo đỏ</h1>
<p>Thân suit được AI vẽ lại theo ảnh tham chiếu DEFAULT để khớp bộ nhân vật.
Đầu, tay và chân dùng các PNG đã chọn trong config. Bản xem thử mở trực tiếp khi không có mạng.</p>
</header>''' + library + '<div class="gallery">' + "\n".join(cards) + '''</div></main>
<script>
const bitmapLoads = new Map();
for (const source of document.querySelectorAll('.asset-library image')) {
  const bitmap = new Image();
  bitmap.decoding = 'sync';
  bitmap.src = source.getAttribute('href');
  bitmapLoads.set(source.id, bitmap.decode().catch(() => {
    throw new Error(source.dataset.source);
  }));
}
window.characterPreviewErrors = [];
window.characterPreviewReady = Promise.all([...document.querySelectorAll('.character')].map(async card => {
  try {
    await Promise.all([...card.querySelectorAll('use')].map(node => bitmapLoads.get(node.getAttribute('href').slice(1))));
    card.dataset.state = 'ready';
    return true;
  } catch (error) {
    card.dataset.state = 'error';
    card.querySelector('.image-status').textContent = 'Không tải đủ ảnh nhân vật: ' + error.message;
    window.characterPreviewErrors.push(error.message);
    return false;
  }
})).then(results => results.every(Boolean));
</script></body></html>
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assets", type=Path, default=ROOT / "config/character_assets.json")
    parser.add_argument("--presets", type=Path, default=ROOT / "config/character_presets.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preset", help="ID preset; mặc định dùng default_preset trong config")
    mode.add_argument("--gallery", action="store_true", help="Xem tất cả preset trong một HTML")
    mode.add_argument("--check", action="store_true", help="Kiểm tra tất cả preset, không ghi file")
    mode.add_argument("--list", action="store_true", help="Liệt kê preset, không ghi file")
    parser.add_argument("--output", type=Path, default=ROOT / "storage/character_rig/index.html")
    parser.add_argument("--debug", action="store_true", help="Hiện điểm nối trên bản xem thử")
    parser.add_argument("--overwrite", action="store_true", help="Ghi đè bản xuất đã tồn tại")
    args = parser.parse_args(argv)
    try:
        rig = CharacterRig(args.assets, args.presets)
        if args.list:
            for key, preset in rig.presets.items():
                print(f"{key}: {object_value(preset, key).get('description', '')}")
            return 0
        if args.check:
            rig.validate()
            print(f"Hợp lệ: {len(rig.presets)} preset, {len(rig.assets)} asset đã đăng ký.")
            return 0
        preset_ids = list(rig.presets) if args.gallery else [args.preset or rig.default]
        output = args.output.resolve()
        if output.is_relative_to(rig.asset_root):
            raise CharacterConfigError("Hãy lưu bản xuất ngoài thư mục asset_root để giữ nguyên ảnh nguồn.")
        if output.suffix.lower() not in {".html", ".svg"}:
            raise CharacterConfigError("--output phải là file .html hoặc .svg.")
        if args.gallery and output.suffix.lower() == ".svg":
            raise CharacterConfigError("--gallery cần đầu ra .html.")
        if output.exists() and not args.overwrite:
            raise CharacterConfigError(f"File đã tồn tại: {output}. Dùng --overwrite để xuất lại.")
        content = (rig.svg(preset_ids[0], debug=args.debug) if output.suffix.lower() == ".svg"
                   else rig.html(preset_ids, debug=args.debug))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Đã xuất {len(preset_ids)} preset: {output}")
        return 0
    except (CharacterConfigError, OSError) as exc:
        print(f"Lỗi ghép nhân vật: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
