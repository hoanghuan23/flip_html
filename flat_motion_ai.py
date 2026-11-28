"""Dựng SVG vector chi tiết cho mọi chủ đề bằng thư viện asset chung của video."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from scene_logic import REAL_WORLD_RULES

VERSION = "flat-detailed-v4"
NS = "http://www.w3.org/2000/svg"


def load_style(style_context=None):
    """Đọc trực tiếp Skill mặc định theo vị trí module, không cache nội dung."""
    if style_context is not None:
        from render_style import style_prompt
        return style_prompt(style_context)
    path = Path(__file__).resolve().parent / "skills" / "styles" / "character-cartoon" / "SKILL.md"
    return path.read_text(encoding="utf-8")


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


def library_prompt(script, style_context=None):
    return ("Vẽ thư viện SVG dùng chung cho TOÀN BỘ video. Chỉ trả một <svg xmlns=\""
            + NS + "\" viewBox=\"0 0 1920 1080\"><defs id=\"shared-assets\">...</defs></svg>.\n"
            + load_style(style_context) + """
Canvas 1920x1080. Dùng toàn bộ khung hình cho diễn hoạt, không chừa dải chữ
phía dưới. Không vẽ phụ đề hoặc chép caption/narration lên hình.

Mỗi asset và mỗi pose bên dưới phải có đúng một <g id="ID"> trong defs.
Background vẽ tại (0,0), phủ 1920x1080. Asset khác có tâm (0,0), vẽ kích thước
đúng description; KHÔNG đặt sẵn ở tọa độ của phase. Không <symbol>.
Dùng cùng gốc local và điểm neo tương ứng để chuyển pose không làm đối tượng
nhảy vị trí hoặc đổi cỡ ngoài ý muốn.

NHẬN DIỆN VÀ HÌNH HỌC DÙNG CHUNG
Chọn một thiết kế gốc cho từng đối tượng rồi giữ nguyên trong toàn bộ pose:
khuôn mặt, cấu tạo, vật liệu, màu từng bộ phận/trang phục và họa tiết nhận diện.
Phối màu theo skill và vai trò palette của Plan một lần, không chọn lại theo
tên pose hoặc tâm trạng. Với nhóm, giữ đúng từng thành viên và số lượng.
Nếu nội dung chủ đích làm đổi một thuộc tính, chỉ đổi đúng phần Plan nêu và giữ
nhận diện còn lại; không cấm biến đổi hình dạng/vật liệu cần để giải thích quá trình.
Cùng kích thước canvas không có nghĩa là cùng kích thước vật thể: vẽ theo kích
thước silhouette, tỷ lệ cơ thể và điểm neo trong description. Tư thế rộng hơn
không được co toàn thân nhỏ lại để lấp vừa khung; chừa khoảng cho mọi pose.
Nền và thân chính không vẽ lặp bộ phận đã tách asset để đóng/mở, di chuyển hoặc
ẩn/hiện. Không gắn dấu kiểm/nhãn kết quả vào hình gốc nếu chúng là trạng thái
chỉ được công bố ở một thời điểm; phase sẽ đặt lớp chú giải riêng.

CẤU TẠO PHỤC VỤ CHUYỂN ĐỘNG
Đọc description, initial_state, final_state và actions (kể cả note, from/to.pose)
trong toàn video trước khi vẽ.
Bộ phận cần chuyển động độc lập và đã được Plan tách asset phải có hình riêng,
đúng kích thước/điểm nối để lắp khớp; không vẽ lặp bộ phận đó vào thân chính.
Không mặc định các nhóm con trong một <use> có thể được phase điều khiển riêng.
Với morph, vẽ đủ mọi pose được liệt kê.
Không tự tạo hệ xương, action mới hoặc yêu cầu nội suy path; thư viện là hình tĩnh.

RÀNG BUỘC SVG
Có thể có defs phụ clipPath, linearGradient/radialGradient và stop; mọi id duy nhất.
Gradient, clip và mask chỉ tham chiếu id nội bộ bằng url(#ID); không URL ngoài.
Tiền tố id phụ theo asset (ví dụ CLOUD_01-shade); tránh id dành cho chương trình
program-assets/program-captions. Khai báo đủ mọi id được href/url(#ID) tham chiếu,
không tham chiếu vòng. Khi dùng lại <use>, không nhân bản bộ phận vốn đã có trong hình.
Chỉ SVG hình học và text nhãn ngắn.
Không CSS/style, animation, script, SMIL, image, foreignObject hoặc tài nguyên ngoài.
Thư viện là dữ liệu tĩnh để phase dùng <use href="#ID"> và chuyển động bằng CSS.
Giữ toàn SVG dưới 250000 byte.
""" + "\nSTYLE:\n" + json.dumps(script.get("style", {}), ensure_ascii=False)
            + "\nASSETS VÀ POSES:\n" + json.dumps(asset_spec(script), ensure_ascii=False)
            + "\nTRẠNG THÁI VÀ ACTIONS TOÀN VIDEO (để chọn cấu tạo, tỷ lệ và pose):\n"
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


def phase_prompt(script, index, library, previous=None, *, style_context=None):
    phase = script["phases"][index - 1]
    before = script["phases"][(phase.get("branch_from") or index - 1) - 1] if index > 1 else None
    return ("Dàn cảnh MỘT phase bằng SVG + CSS animation. Chỉ trả một <svg xmlns=\""
            + NS + "\" viewBox=\"0 0 1920 1080\">...</svg>.\n" + load_style(style_context) + REAL_WORLD_RULES + """
Canvas 1920x1080. Dùng toàn bộ khung hình cho diễn hoạt, không chừa dải chữ
phía dưới. Không vẽ phụ đề hoặc chép caption/narration lên hình.

Chỉ đặt <style> và <g id="artwork"> trực tiếp dưới SVG. Không tự tạo defs:
chương trình chèn thư viện bên dưới. Tái sử dụng nhân vật/đồ vật/nền bằng
<use href="#ASSET_ID"> hoặc pose đã định nghĩa; không vẽ lại hình chính.
Mỗi asset được nhắc đến trong actions phải có <use>, kể cả khi opacity=0.
Được vẽ thêm mũi tên và nhãn trong artwork để làm rõ ý Plan,
không thêm vật thể ngoài câu chuyện.
Được vẽ lớp SVG phụ cho hiệu ứng của hành động đã nêu trong Plan: dòng truyền,
vệt tác động hoặc dấu tại điểm tiếp xúc. Đây là biểu diễn quá trình, không phải
vẽ lại chủ thể chính; không dùng biểu tượng/mũi tên thay phần tác động cần thấy.
Bóng/gradient đã nằm trong thư viện, không phủ thêm hiệu ứng che cấu tạo.

CHÚ GIẢI THÀNH PHẦN
- Nhãn dài được ngắt dòng bằng tspan và nới hộp theo chữ,
  không cắt chữ hoặc thu chữ quá nhỏ.
- Đặt hộp trong khoảng trống của canvas 1920x1080, chừa đệm quanh chữ; tránh chồng
  nhãn, giao cắt đường dẫn hoặc che chủ thể và vùng tương tác.
- Cho chú giải xuất hiện cùng nội dung liên quan và ẩn khi đối tượng biến mất.
  Khi đối tượng chuyển động hoặc đổi pose, giữ đầu chỉ dẫn gắn đúng vùng đích
  trong toàn khoảng hiển thị bằng wrapper/animation phù hợp, không chỉ ở khung đầu.

DÀN CẢNH VÀ DIỄN BIẾN
Đọc name, caption, narration, trạng thái và actions để xác định ý chính của phase.
Bố trí đối tượng trong vùng diễn hoạt theo camera và tọa độ dự kiến; chừa khoảng
cho đường chuyển động, nhãn và kết quả, kể cả kích thước asset khi đang chuyển động.
Kế thừa bố cục và vị trí từ phase gốc khi nối liên tục; đặt đúng from/to của JSON.
Chọn lớp và vị trí chú giải để giữ điểm tiếp xúc, hướng và khoảng trống mà không
đổi tọa độ, tỷ lệ hay diễn biến đã được Plan chỉ định.
Kiểm tra khoảng trống theo toàn bộ silhouette, bóng, đường đi và các pose trong
suốt phase; không chỉ tránh giao nhau tại vị trí tâm hoặc ở khung đầu/cuối.
Kiểm tra tỷ lệ bằng phần hình nhìn thấy, không dựa vào kích thước khung PNG/SVG.
Dùng một tỷ lệ không gian cho cùng góc máy; tách lớp đặt vị trí, tỷ lệ cố định và
chuyển động để pose không nhảy cỡ. Giữ chân/đáy/điểm cầm đúng bề mặt hoặc điểm
nối; quỹ đạo phải theo lối đi và không cắt chủ thể ra ngoài khung hình.
Khi cần che khuất có chủ đích, vẫn giữ rõ hành động, điểm tiếp xúc và từng thành
viên quan trọng. Không dùng đổi lớp hoặc dịch đồ họa để giấu một mâu thuẫn của Plan.
Mũi tên có đầu/cuối rõ, gắn đúng nguồn và đích của tác động hoặc dòng di chuyển;
không xuyên nhãn hay che vùng tương tác. Hiệu ứng xuất hiện đúng nơi, đúng lúc
theo action.note, không thay hành động thật bằng biểu tượng hoặc nhấp nháy.
Hiệu ứng của hành động phải có nguồn, đích và thời điểm bật/tắt rõ. Gắn gốc hiệu
ứng vào đúng điểm phát trên pose đang hiện, cập nhật cùng wrapper khi chủ thể
di chuyển; không nối vào tâm asset hay giữ một tọa độ màn hình cố định. Đầu còn
lại phải tới đúng vùng tác động. Bắt đầu sau khi dụng cụ/bộ phận sẵn sàng, duy trì
khi quá trình đang diễn ra, kết thúc theo Plan; nối liên tục giữa các phase nếu
quá trình còn tiếp diễn. Nếu cần thấy dòng chảy, dùng các đoạn/hạt SVG nhỏ chuyển
động bằng transform/opacity hữu hạn, không chỉ một nét tĩnh hoặc hiệu ứng toàn hình.
Triển khai from -> diễn biến -> to theo từng action, nối đúng initial_state đến
final_state. Tác động và kết quả phải đọc được theo thứ tự Plan đã nêu, kể cả khi
có nhiều action đồng thời; giữ kết quả trong thời gian còn lại nếu action đã kết thúc.
move/loop thể hiện đường đi, rotate thể hiện quay, scale thể hiện đổi kích thước,
fade thể hiện ẩn/hiện; không dùng xoay/phóng to/mờ cả hình để thay cơ chế nhiều bước.
Dùng các asset bộ phận và pose mà Plan đã cấp để thể hiện các bước đó.
Nếu có nhiều morph nối tiếp, chỉ chồng hai pose trong cửa sổ chuyển tương ứng;
giữ các mốc cấu trúc và chi tiết nhận diện để thấy bước thay đổi, không quay cứng
cả hệ hoặc kéo giãn một hình để giả sự phát triển cấu trúc.

ĐƯỜNG ĐI VÀ QUỸ ĐẠO
Renderer hiện dùng transform/opacity, không có action path hay nội suy đường cong
từ schema. Giữ nguyên từng move/loop và các điểm from/to, mốc start/end, easing
trong JSON; nối đúng các đoạn đã có, không tự thêm action hay dùng offset-path/SMIL.
Có thể vẽ đường cong chỉ dẫn tĩnh trong artwork theo đường đi mà Plan mô tả,
nhưng đường đó không phải cơ chế tự chạy asset và không được làm sai các điểm đã cho.

RÀNG BUỘC CHUYỂN ĐỘNG
Chỉ animation transform và opacity qua @keyframes; fill-mode:both.
Mỗi chuyển động dùng wrapper riêng: <g transform="translate(x y)"> tĩnh bên ngoài,
<g class="motion"> animate bên trong để CSS không ghi đè vị trí đặt ban đầu.
Đặt transform-origin:0 0;transform-box:view-box cho nhóm có gốc local (0,0).
Với morph, dùng đúng from.pose/to.pose có sẵn và mờ chuyển trong khoảng start/end;
chỉ hiện pose tương ứng trước/sau khoảng này, không chồng cả các pose suốt phase.
Giữ điểm neo khi chuyển pose; không animate thuộc tính d hoặc điều khiển riêng
bộ phận bên trong <use>. Bộ phận tách asset dùng wrapper riêng theo actions.
Không script, SMIL, image, foreignObject, URL ngoài, animation-play-state.
Thời gian tương đối theo phase. Mọi animation không lặp kết thúc trong duration.
Giữ nguyên duration và mốc actions của kịch bản; không tự tính lại thời lượng.
caption/narration chỉ cung cấp ngữ cảnh, không được tự hiển thị thành phụ đề.
Nếu có voiceover/audio, giữ diễn biến khớp lời đọc và thời lượng đã cung cấp.
Trạng thái t=0 đúng initial_state và t=duration đúng final_state. Không dùng transition
hoặc hiệu ứng phụ thuộc lịch sử phát; tua phải tái hiện được chính xác một trạng thái.
Nếu có branch_from, quay về trạng thái cuối PHASE GỐC, không tiếp sau phase liền trước.
Chỉ animate wrapper cần thiết; không tạo hàng trăm chuyển động chi tiết hoặc
hiệu ứng ngẫu nhiên theo thời gian thực. Mọi id phase phải khác thư viện và id
program-assets/program-captions; mọi href/url(#ID) phải có đích trong SVG ghép.
Tự kiểm tra khung đầu, giữa, cuối và lúc đổi pose: hình thể hiện đúng hiện tượng,
đủ khoảng trống, không mất tham chiếu, trạng thái tái hiện đúng khi tua ngược/xuôi.
Rà cả lúc hai đối tượng đi ngang nhau và lúc chạm bề mặt: nhận diện có giữ nguyên,
silhouette có chồng mất ý, điểm tựa/điểm nối có khớp và tác động có thật sự nhìn thấy?
""" + "\nPHASE:\n" + json.dumps(phase, ensure_ascii=False)
            + "\nSTYLE:\n" + json.dumps(script.get("style", {}), ensure_ascii=False)
            + "\nTHƯ VIỆN ASSET (chỉ tham chiếu, KHÔNG trả lại):\n" + library
            + "\nASSET/POSE IDS:\n" + json.dumps(asset_spec(script), ensure_ascii=False)
            + ("\nTRẠNG THÁI PHASE GỐC:\n" + before["final_state"] if before else "")
            + ("\nSVG PHASE GỐC:\n" + previous if previous else ""))


class Renderer:
    def __init__(self, script, output, request, cleaner, *, style_context=None, on_progress=None):
        self.script, self.output, self.request, self.cleaner = script, output, request, cleaner
        self.library = None
        self.style_context = style_context
        self.on_progress = on_progress

    def progress(self, stage, completed, total):
        if self.on_progress:
            self.on_progress(stage, completed, total)

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
        prompt = library_prompt(self.script, self.style_context)
        fingerprint = digest({"version": VERSION, "prompt": prompt})
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
            (prompts / "assets.txt").write_text(prompt, encoding="utf-8")
            self.library = self.generate(prompt, lambda raw: validate_library(raw, self.script, self.cleaner))
            path.write_text(self.library, encoding="utf-8")
            meta_path.write_text(json.dumps({"fingerprint": fingerprint, "sha256": digest(self.library)}, indent=2), encoding="utf-8")
        # Phụ thuộc prompt asset (gồm Skill), kể cả khi SVG sinh lại giống hệt.
        self.fingerprint = digest({"version": VERSION, "script": self.script, "library": self.library,
                                   "assets": fingerprint})
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
        root.set("data-renderer", VERSION)
        root.set("data-fingerprint", self.fingerprint)
        return ET.tostring(root, encoding="unicode")

    def render(self, index, previous=None):
        prompt = phase_prompt(self.script, index, self.library, previous, style_context=self.style_context)
        prompts = self.output / "prompts"
        prompts.mkdir(exist_ok=True)
        (prompts / f"phase_{index}.txt").write_text(prompt, encoding="utf-8")
        return self.generate(prompt, lambda raw: self.clean_phase(raw, index))
