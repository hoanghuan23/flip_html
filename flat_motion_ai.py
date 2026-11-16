"""Dựng SVG vector chi tiết cho mọi chủ đề bằng thư viện asset chung của video."""

import hashlib
import html
import json
import textwrap
import xml.etree.ElementTree as ET

VERSION = "flat-detailed-v3"
NS = "http://www.w3.org/2000/svg"
STYLE = """Phong cách Detailed Flat Vector Illustration / Semi-Flat Infographic.
Áp dụng cho mọi chủ đề; vẽ đúng nội dung, không mặc định một loại cảnh hay đồ vật.
Góc nhìn theo camera.view và mô tả trong kịch bản: nhìn ngang, chính diện,
nhìn từ trên, góc xiên hoặc mặt cắt tùy nội dung; không cố định góc nhìn.
Giữ phối cảnh, tỷ lệ và hướng nhìn nhất quán giữa nền, nhân vật và đồ vật
trong cùng cảnh. Khi kịch bản đổi góc, dùng asset/pose phù hợp với góc mới.
Hình vector rõ nét, silhouette dễ đọc, hình khối bo nhẹ và chi tiết có chọn lọc.
Động vật: tỷ lệ thân/chân/đầu hợp lý, tư thế tự nhiên, khớp nối đúng, mắt/mũi/mồm/đuôi/chi tiết nhận dạng
Con người: tỷ lệ cơ thể, khớp nối, tư thế và điểm tiếp xúc với đồ vật hợp lý theo hành động.
SVG phải đủ chi tiết để nhận ra cấu tạo và chức năng: phân chia bộ phận chính,
khớp nối, đường viền cấu trúc, mặt tiếp giáp, chất liệu và điểm nhấn phù hợp
đối tượng. Không giản lược mọi vật thành hình chữ nhật hoặc hình tròn chung chung.
Nhân vật có tỷ lệ, tư thế, khớp tay/chân và điểm tiếp xúc với đồ vật hợp lý
theo hành động và góc nhìn; các bộ phận nhỏ phải tương phản với nền.
Semi-flat: cho phép linearGradient/radialGradient nhẹ, mảng sáng/tối và highlight
để phân biệt bề mặt, chất liệu và lớp hình; tránh bóng loáng như ảnh thật.
Bóng đổ bằng silhouette vector lệch nhẹ, opacity 0.12-0.20; chọn hướng sáng
phù hợp cảnh và giữ nhất quán. Không filter/blur, texture, ảnh thật hoặc render 3D.
Màu sắc theo palette kịch bản và ngữ cảnh; các chi tiết vẫn đọc được ở màn hình nhỏ.
Bố cục infographic trực quan: rõ vị trí, hướng đi và điểm tương tác, không rối.
Canvas 1920x1080. Diễn hoạt chính y=0..792; vùng y=792..1080 chương trình tự
đặt dải chữ, không đưa đối tượng quan trọng vào đó. Không tự vẽ caption/narration.
"""


def text_lines(text, y, size, fill, width, weight=800):
    """Ngắt dòng và escape chữ trước khi chèn vào SVG."""
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [""]
    return (f'<text x="960" y="{y}" text-anchor="middle" font-size="{size}" font-weight="{weight}" fill="{fill}">'
            + "".join(f'<tspan x="960" dy="{0 if i == 0 else size * 1.25:g}">{html.escape(line)}</tspan>'
                      for i, line in enumerate(lines)) + '</text>')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def asset_spec(script):
    variants = {}
    for phase in script["phases"]:
        for action in phase["actions"]:
            if action["type"] == "morph":
                poses = variants.setdefault(action["target"], [])
                for endpoint in ("from", "to"):
                    pose = action[endpoint].get("pose")
                    if pose and pose not in poses:
                        poses.append(pose)
    return [{**asset, "poses": [{"id": f'{asset["id"]}--pose-{i}', "description": pose}
                                for i, pose in enumerate(variants.get(asset["id"], []), 1)]}
            for asset in script["assets"]]


def library_prompt(script):
    return ("Vẽ thư viện SVG dùng chung cho TOÀN BỘ video. Chỉ trả một <svg xmlns=\""
            + NS + "\" viewBox=\"0 0 1920 1080\"><defs id=\"shared-assets\">...</defs></svg>.\n"
            + STYLE + """
Mỗi asset và mỗi pose bên dưới phải có đúng một <g id="ID"> trong defs.
Background vẽ tại (0,0), phủ 1920x1080. Asset khác có tâm (0,0), vẽ kích thước
đúng description; KHÔNG đặt sẵn ở tọa độ của phase. Không <symbol>.
Các pose cùng nhân vật phải giữ ngoại hình, màu, tỷ lệ và mức độ chi tiết;
chỉ thay đổi tư thế hoặc góc nhìn được kịch bản yêu cầu.
Có thể có defs phụ clipPath, linearGradient/radialGradient và stop; mọi id duy nhất.
Gradient, clip và mask chỉ tham chiếu id nội bộ bằng url(#ID); không URL ngoài.
Bóng đổ là hình vector có opacity, không filter. Chỉ SVG hình học và text nhãn ngắn.
Không CSS/style, animation, script, SMIL, image, foreignObject hoặc tài nguyên ngoài.
Thư viện là dữ liệu tĩnh để phase dùng <use href="#ID"> và chuyển động bằng CSS.
""" + "\nSTYLE:\n" + json.dumps(script.get("style", {}), ensure_ascii=False)
            + "\nASSETS VÀ POSES:\n" + json.dumps(asset_spec(script), ensure_ascii=False)
            + "\nKỊCH BẢN ĐẦY ĐỦ (để chọn tỷ lệ và tư thế nhất quán):\n"
            + json.dumps([{k: phase.get(k) for k in ("id", "camera", "initial_state", "final_state", "actions")}
                          for phase in script["phases"]], ensure_ascii=False))


def parse_svg(raw, cleaner, animation=False):
    root = ET.fromstring(cleaner(raw, require_animation=animation))
    if root.get("viewBox") != "0 0 1920 1080":
        raise ValueError("SVG cần viewBox='0 0 1920 1080'.")
    allowed = {"svg", "defs", "g", "style", "path", "rect", "circle", "ellipse",
               "line", "polyline", "polygon", "text", "tspan", "use", "clipPath", "mask", "title", "desc",
               "linearGradient", "radialGradient", "stop"}
    ids = set()
    for element in root.iter():
        if element.tag not in {f"{{{NS}}}{name}" for name in allowed}:
            raise ValueError(f"Thẻ SVG không hỗ trợ: {element.tag}.")
        eid = element.get("id")
        if eid:
            if eid in ids:
                raise ValueError(f"SVG trùng id: {eid}.")
            ids.add(eid)
        for key, value in element.attrib.items():
            local = key.rsplit("}", 1)[-1].lower()
            if local.startswith("on") or (local == "href" and not value.startswith("#")):
                raise ValueError("SVG chỉ cho phép tham chiếu id nội bộ, không event handler.")
    return root


def validate_library(raw, script, cleaner):
    root = parse_svg(raw, cleaner)
    defs = root.find(f"{{{NS}}}defs")
    if defs is None or any(e.tag != f"{{{NS}}}defs" for e in root):
        raise ValueError("Thư viện chỉ chứa <defs> trực tiếp dưới SVG.")
    if root.find(f".//{{{NS}}}style") is not None:
        raise ValueError("Thư viện asset phải là hình tĩnh, không có style.")
    ids = {e.get("id"): e for e in defs.iter() if e.get("id")}
    for asset in asset_spec(script):
        for aid in [asset["id"], *(pose["id"] for pose in asset["poses"])]:
            if aid not in ids or ids[aid].tag != f"{{{NS}}}g" or len(ids[aid]) == 0:
                raise ValueError(f"Thư viện thiếu hình <g id='{aid}'>.")
    for use in root.findall(f".//{{{NS}}}use"):
        if (use.get("href") or use.get(f"{{http://www.w3.org/1999/xlink}}href", ""))[1:] not in ids:
            raise ValueError("Thư viện có <use> trỏ đến id không tồn tại.")
    return ET.tostring(root, encoding="unicode")


def phase_prompt(script, index, library, previous=None):
    phase = script["phases"][index - 1]
    before = script["phases"][(phase.get("branch_from") or index - 1) - 1] if index > 1 else None
    return ("Dàn cảnh MỘT phase bằng SVG + CSS animation. Chỉ trả một <svg xmlns=\""
            + NS + "\" viewBox=\"0 0 1920 1080\">...</svg>.\n" + STYLE + """
Chỉ đặt <style> và <g id="artwork"> trực tiếp dưới SVG. Không tự tạo defs:
chương trình chèn thư viện bên dưới. Tái sử dụng nhân vật/đồ vật/nền bằng
<use href="#ASSET_ID"> hoặc pose đã định nghĩa; không vẽ lại hình chính.
Mỗi asset được nhắc đến trong actions phải có <use>, kể cả khi opacity=0.
Background ở dưới cùng, rồi effect/object/character. Được vẽ thêm mũi tên và nhãn
tối đa 3 từ trong artwork. Không thêm vật thể không có trong câu chuyện.
Chỉ animation transform và opacity qua @keyframes; fill-mode:both.
Mỗi chuyển động dùng wrapper riêng: <g transform="translate(x y)"> tĩnh bên ngoài,
<g class="motion"> animate bên trong để CSS không ghi đè vị trí đặt ban đầu.
Đặt transform-origin:0 0;transform-box:view-box cho nhóm có gốc local (0,0).
Khi cần đổi tư thế, dùng các pose có sẵn và mờ chuyển; không animate thuộc tính d.
Không script, SMIL, image, foreignObject, URL ngoài, animation-play-state.
Thời gian tương đối theo phase. Mọi animation không lặp kết thúc trong duration.
Giữ nguyên duration và mốc actions của kịch bản; không tự tính lại thời lượng.
Video không có giọng đọc hoặc âm thanh; narration chỉ là chữ giải thích trên màn hình.
Trạng thái t=0 đúng initial_state và t=duration đúng final_state. Không dùng transition
hoặc hiệu ứng phụ thuộc lịch sử phát; tua phải tái hiện được chính xác một trạng thái.
Nếu có branch_from, quay về trạng thái cuối PHASE GỐC, không tiếp sau phase liền trước.
""" + "\nPHASE:\n" + json.dumps(phase, ensure_ascii=False)
            + "\nSTYLE:\n" + json.dumps(script.get("style", {}), ensure_ascii=False)
            + "\nTHƯ VIỆN ASSET (chỉ tham chiếu, KHÔNG trả lại):\n" + library
            + "\nASSET/POSE IDS:\n" + json.dumps(asset_spec(script), ensure_ascii=False)
            + ("\nTRẠNG THÁI PHASE GỐC:\n" + before["final_state"] if before else "")
            + ("\nSVG PHASE GỐC:\n" + previous if previous else ""))


class Renderer:
    def __init__(self, script, output, request, cleaner):
        self.script, self.output, self.request, self.cleaner = script, output, request, cleaner
        self.library = None

    def generate(self, prompt, validator):
        error = ""
        for attempt in range(3):
            raw = self.request(prompt + ("\nLẦN TRƯỚC LỖI: " + error + "\nTrả SVG đầy đủ đã sửa." if error else ""))
            try:
                return validator(raw)
            except ValueError as problem:
                error = str(problem)
                print(f"  Lần {attempt + 1}: {error}", flush=True)
        raise ValueError(error)

    def prepare(self):
        path = self.output / "assets.svg"
        meta_path = self.output / "assets.meta.json"
        fingerprint = digest({"version": VERSION, "prompt": library_prompt(self.script)})
        try:
            data, meta = path.read_text(encoding="utf-8"), json.loads(meta_path.read_text())
            if meta["fingerprint"] == fingerprint and meta["sha256"] == digest(data):
                self.library = validate_library(data, self.script, self.cleaner)
        except (OSError, ValueError, KeyError):
            pass
        if self.library is None:
            print("  Đang vẽ thư viện asset chung cho video…", flush=True)
            prompts = self.output / "prompts"
            prompts.mkdir(exist_ok=True)
            (prompts / "assets.txt").write_text(library_prompt(self.script), encoding="utf-8")
            self.library = self.generate(library_prompt(self.script), lambda raw: validate_library(raw, self.script, self.cleaner))
            path.write_text(self.library, encoding="utf-8")
            meta_path.write_text(json.dumps({"fingerprint": fingerprint, "sha256": digest(self.library)}, indent=2), encoding="utf-8")
        self.fingerprint = digest({"version": VERSION, "script": self.script, "library": self.library})
        return self

    def clean_phase(self, raw, index):
        root = parse_svg(raw, self.cleaner, animation=True)
        # Chỉ gỡ những lớp do chính chương trình chèn khi kiểm tra lại cache.
        if root.get("data-renderer") == VERSION:
            for element in list(root):
                if element.get("id") in {"program-assets", "program-captions"}:
                    root.remove(element)
        if any(e.tag not in {f"{{{NS}}}style", f"{{{NS}}}g"} for e in root):
            raise ValueError("Phase chỉ đặt style và artwork dưới SVG; không tự vẽ defs.")
        artwork = root.find(f"{{{NS}}}g[@id='artwork']")
        if artwork is None or any(e.tag == f"{{{NS}}}g" and e is not artwork for e in root):
            raise ValueError("Cần đúng một <g id='artwork'> trực tiếp dưới SVG.")
        library = ET.fromstring(self.library)
        ids = {e.get("id") for e in library.iter() if e.get("id")}
        if any(e.get("id") in ids | {"program-captions", "program-assets"} for e in root.iter()):
            raise ValueError("Phase dùng trùng id của thư viện/chương trình.")
        refs = set()
        for use in root.findall(f".//{{{NS}}}use"):
            aid = (use.get("href") or use.get(f"{{http://www.w3.org/1999/xlink}}href", ""))[1:]
            if aid not in ids:
                raise ValueError(f"<use> trỏ đến asset/pose không có trong thư viện: {aid}.")
            refs.add(aid.split("--pose-", 1)[0])
        required = {a["target"] for a in self.script["phases"][index - 1]["actions"]}
        if required - refs:
            raise ValueError("Thiếu <use> cho asset: " + ", ".join(sorted(required - refs)))
        backgrounds = {a["id"] for a in self.script["assets"] if a["category"] == "background"}
        if backgrounds and not backgrounds & refs:
            raise ValueError("Phase thiếu <use> nền từ thư viện chung.")
        defs = ET.Element(f"{{{NS}}}defs", {"id": "program-assets"})
        for group in library:
            defs.extend(group)
        root.insert(0, defs)
        phase = self.script["phases"][index - 1]
        caption = phase.get("caption", "")
        captions = ('<g xmlns="' + NS + '" id="program-captions">'
                    '<rect y="792" width="1920" height="288" fill="#f4c97a"/>'
                    + text_lines(caption, 890 if len(caption) > 48 else 918,
                                 48 if len(caption) > 48 else 60, "#3b2a12", 48)
                    + text_lines(phase.get("narration", ""), 1015, 36, "#6b4a1c", 86, 500) + '</g>')
        root.append(ET.fromstring(captions))
        root.set("data-renderer", VERSION)
        root.set("data-fingerprint", self.fingerprint)
        return ET.tostring(root, encoding="unicode")

    def render(self, index, previous=None):
        prompt = phase_prompt(self.script, index, self.library, previous)
        prompts = self.output / "prompts"
        prompts.mkdir(exist_ok=True)
        (prompts / f"phase_{index}.txt").write_text(prompt, encoding="utf-8")
        return self.generate(prompt, lambda raw: self.clean_phase(raw, index))
