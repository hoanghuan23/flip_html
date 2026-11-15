"""Sinh kịch bản video giải thích (Flat Motion Graphics) dạng JSON.
Dùng --output để lưu cho generate_preview_test.py."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent


def load_env(path=ROOT / ".env"):
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name and not name.startswith("#"):
                os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


load_env()
API_URL = os.getenv("CODEX_API_URL")
API_KEY = os.getenv("CODEX_API_TOKEN")
MODEL = os.getenv("CODEX_MODEL")

NOI_DUNG = """
Dòng chảy xa bờ (tiếng Anh là rip current, thường được ngư dân gọi là dòng xoáy hay ao xoáy) là một dòng nước mạnh, hẹp chảy từ phía bờ biển hướng ngược thẳng ra ngoài khơi.
Sóng liên tục đẩy nước vào bờ. Lượng nước này phải quay trở lại biển, và nó thường dồn qua một lối hẹp, nơi sóng yếu hơn, tạo thành dòng chảy mạnh hướng ra khơi.
Dòng chảy xa bờ có thể kéo người bơi ra xa bờ rất nhanh. Nhiều người hoảng sợ và cố bơi ngược vào bờ, dẫn đến kiệt sức.
Cách xử lý đúng: giữ bình tĩnh, không bơi ngược dòng, bơi song song với bờ để thoát khỏi dòng chảy, sau đó bơi vào bờ. Nếu không thoát được, hãy nổi, vẫy tay và kêu cứu.
"""

DEFAULT_DURATION = 15
WORDS_PER_SECOND = 3.5  # tiếng Việt: mỗi tiếng là một từ, giọng đọc khoảng 3-4 tiếng/giây

PROMPT = """
Bạn là đạo diễn motion graphics phong cách Flat (kiểu Kurzgesagt - In a Nutshell)
và là biên tập viên khoa học.

Nhiệm vụ: biến nội dung đầu vào thành kịch bản video giải thích ngắn.
Chỉ trả về MỘT đối tượng JSON hợp lệ, không markdown, không giải thích.

MỤC TIÊU:
Kịch bản được dùng để tự động vẽ từng phase bằng SVG + CSS animation,
sau đó ghép các phase thành video preview HTML.

THÔNG SỐ
- Tổng thời lượng: <<DURATION>> giây (sai số tối đa 0.5s)
- Canvas 1920x1080, gốc (0,0) ở góc trên trái
- Ngôn ngữ lời bình và chữ trên màn hình: tiếng Việt

PHONG CÁCH (áp dụng cho mọi phase)
- Flat 2D: hình khối hình học, màu đặc, không viền đen, không gradient phức tạp,
  không texture, bóng đổ phẳng.
- Bảng màu cố định 5-7 mã hex trong "style.palette", mỗi vai trò đúng một màu
  (nước sâu, nước nông, bọt sóng, cát, nhân vật, cảnh báo, chữ).
- Cố định góc nhìn top-down cho TẤT CẢ phase. Người bơi nhìn từ trên xuống:
  đầu tròn, thân bầu dục, hai tay và hai chân cùng tỷ lệ, cùng màu, mặt tối giản
  nhìn thấy từ trên. Không chuyển sang người đứng nhìn thẳng hoặc hình người mới.
- Dùng một mẫu nhân vật duy nhất; các tư thế chỉ đổi bằng xoay/dịch chuyển tay,
  chân và thân của CÙNG mẫu, không vẽ lại đầu/mặt/tỷ lệ.
- Một bản đồ bờ biển cố định: bờ cát nằm dưới khung, biển ở trên; dòng chảy xa bờ
  là dải nước hẹp LIỀN MẠCH ở giữa khung, từ sát bờ ra khơi, cắt qua vùng sóng yếu.
  Mũi tên chỉ hướng chỉ là lớp chú thích, không thay thế dải nước. Giữ nguyên hình,
  vị trí và màu dải nước qua các phase; chỉ tăng độ rõ/cường độ khi cần.
- Nền biển/cát phải phủ kín toàn bộ canvas 1920x1080, kể cả dưới đường chân sóng
  và sát mép cát. Không để vùng trong suốt làm lộ nền đen của trình phát.

CẤU TRÚC GIẢI THÍCH
1. Hook (<= 2s): nêu hiện tượng hoặc đặt câu hỏi.
2. Cơ chế: vì sao xảy ra (1-2 phase).
3. Hệ quả hoặc mức nguy hiểm.
4. Cách xử lý, thông điệp chốt.
Tổng 4-6 phase, mỗi phase 2-5s, mỗi phase chỉ truyền đạt MỘT ý.
Đảm bảo tính liên tục giữa các phase (trạng thái cuối phase này = trạng thái đầu phase sau).
Phase cuối nói "nếu không thoát được" là nhánh lựa chọn từ lúc nhân vật vẫn ở trong
dòng chảy, KHÔNG phải việc xảy ra sau khi đã bơi thoát ở phase trước. Ghi rõ
"branch_from" là id phase nguy hiểm, và mô tả cú chuyển cảnh quay lại tình huống đó.
Ở phase thoát hiểm, phải thể hiện "giữ bình tĩnh" trước khi bơi ngang; phase cuối
phải làm rõ điều kiện "nếu không thoát được" trước khi nổi/vẫy tay/kêu cứu.
Biểu tượng cảnh báo chỉ hiện lúc nguy hiểm, biến mất trước khi nhân vật bơi bình tĩnh;
không giữ biểu tượng cảnh báo đằng sau tư thế cầu cứu nếu ý nghĩa đã thay đổi.

LỜI BÌNH VÀ NỘI DUNG
- Số từ narration của mỗi phase <= thời lượng phase x 3.5 (mỗi tiếng tính là một từ).
- caption: tối đa 8 từ, hiển thị trên màn hình.
- Chỉ dùng thông tin trong nội dung đầu vào hoặc kiến thức phổ thông chắc chắn đúng.
  Không bịa số liệu, tên riêng, thống kê. Ý bổ sung phải có "added": true.

ASSET
- Mọi asset đều được vẽ bằng SVG (hình học đơn giản). Không dùng ảnh bitmap, sprite sheet.
- "description" phải đủ cụ thể (hình khối, kích thước tương đối, màu theo vai trò
  trong palette) để vẽ lại giống hệt ở mọi phase.
- Mỗi asset có ID duy nhất, tái sử dụng giữa các phase. Tối đa 10 asset.
- category: background | character | object | effect | ui

QUY TẮC KỸ THUẬT
- Tọa độ, kích thước và tốc độ chỉ là giá trị dự kiến, sẽ hiệu chỉnh khi vẽ.
- Thời gian trong "actions" là thời gian tương đối trong phase (0 đến duration).
- Chỉ dùng asset đã khai báo trong "assets".
- Mỗi phase phải có camera, initial_state, final_state và ít nhất 1 action.
- Chỉ dùng chuyển động CSS làm được: di chuyển, xoay, co giãn, mờ hiện, lặp.
  Đổi tư thế nhân vật = "morph" (xoay hoặc co giãn các bộ phận); không dùng "pose".
- Không thêm hành động không đóng góp cho câu chuyện.
- Không sinh HTML/CSS/JS/SVG, không sinh ảnh.
- Tổng duration các phase = total_duration.

SCHEMA
{
  "title": "",
  "total_duration": 0,
  "style": {"palette": {"role": "#hex"}, "font": "", "notes": ""},
  "assets": [
    {"id": "BG_01", "category": "background|character|object|effect|ui",
     "name": "", "description": ""}
  ],
  "phases": [
    {"id": 1, "name": "", "duration": 0, "branch_from": null,
     "narration": "", "caption": "", "added": false,
     "camera": {"view": "top-down|side|section", "motion": "static|pan|zoom", "detail": ""},
     "initial_state": "", "final_state": "",
     "actions": [
       {"target": "ASSET_ID", "type": "move|rotate|scale|fade|morph|loop",
        "from": null, "to": null, "start": 0, "end": 0,
        "easing": "linear|easeInOut", "note": ""}
     ],
     "sound": ""}
  ]
}

NỘI DUNG ĐẦU VÀO
<<TEXT>>
"""


def request_text(prompt, *, api_url=None, api_key=None, model=None):
    request = Request(
        API_URL if api_url is None else api_url,
        data=json.dumps({"prompt": prompt, "model": MODEL if model is None else model}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": API_KEY if api_key is None else api_key},
        method="POST",
    )
    with urlopen(request, timeout=600) as response:
        data = json.load(response)
    if (not isinstance(data, dict) or data.get("success") is not True
            or not isinstance(data.get("result"), str) or not data["result"].strip()):
        raise ValueError("Server không trả kết quả text thành công.")
    return data["result"].strip()


def extract_json(text):
    """Lấy đối tượng JSON từ phản hồi, bỏ qua hàng rào ```json nếu có."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("Không tìm thấy JSON trong kết quả.")
    return json.loads(text[start:end + 1])


def validate(script, duration):
    """Trả về danh sách lỗi; rỗng nghĩa là kịch bản hợp lệ."""
    errors = []
    phases = script.get("phases") or []
    if not phases:
        return ["Thiếu danh sách phases."]
    ids = {a.get("id") for a in script.get("assets", [])}
    phase_ids = {p.get("id") for p in phases}
    total = sum(p.get("duration", 0) for p in phases)
    if abs(total - duration) > 0.5:
        errors.append(f"Tổng thời lượng phase = {total}, cần {duration}.")
    for p in phases:
        pid = p.get("id")
        spoken = (p.get("narration", "") + " " + p.get("caption", "")).lower()
        if "bơi song song" in spoken and "bình tĩnh" not in spoken:
            errors.append(f"Phase {pid}: cách thoát cần nói rõ 'giữ bình tĩnh'.")
        if "nổi" in spoken and "vẫy tay" in spoken and "không thoát" not in spoken:
            errors.append(f"Phase {pid}: cách cầu cứu cần nói rõ điều kiện 'nếu không thoát được'.")
        if p.get("camera", {}).get("view") != "top-down":
            errors.append(f"Phase {pid}: camera phải là top-down để giữ nhân vật nhất quán.")
        branch = p.get("branch_from")
        if branch is not None and (branch not in phase_ids or branch >= pid):
            errors.append(f"Phase {pid}: branch_from phải trỏ đến phase trước đó.")
        if "không thoát" in (spoken + " " + p.get("name", "").lower()) and branch is None:
            errors.append(f"Phase {pid}: nhánh 'không thoát được' cần branch_from.")
        if not p.get("actions"):
            errors.append(f"Phase {pid}: thiếu actions.")
        for a in p.get("actions", []):
            if a.get("type") not in {"move", "rotate", "scale", "fade", "morph", "loop"}:
                errors.append(f"Phase {pid}: action '{a.get('type')}' không hỗ trợ; dùng morph cho tư thế.")
            if a.get("target") not in ids:
                errors.append(f"Phase {pid}: asset '{a.get('target')}' chưa khai báo.")
            if a.get("end", 0) > p.get("duration", 0):
                errors.append(f"Phase {pid}: action vượt thời lượng phase.")
    return errors


def narration_warnings(script):
    """Lời bình quá dài so với thời lượng phase: chỉ cảnh báo, không làm hỏng kịch bản."""
    warnings = []
    for p in script.get("phases", []):
        words = len(p.get("narration", "").split())
        limit = p.get("duration", 0) * WORDS_PER_SECOND
        if words > limit:
            warnings.append(f"Phase {p.get('id')}: narration {words} từ, nên <= {limit:.0f} từ "
                            f"cho {p.get('duration', 0):g} giây.")
    return warnings


def generate_script(text, duration=DEFAULT_DURATION, retries=2):
    prompt = PROMPT.replace("<<DURATION>>", str(duration)).replace("<<TEXT>>", text)
    problems = []
    for attempt in range(retries + 1):
        script, errors, warnings = None, [], []
        try:
            script = extract_json(request_text(prompt))
            errors = validate(script, duration)
            warnings = narration_warnings(script)
        except ValueError as error:  # gồm cả JSONDecodeError
            errors = [str(error)]
        if script and not errors and (not warnings or attempt == retries):
            for warning in warnings:  # hết lượt thử: chấp nhận, chỉ báo
                print("Cảnh báo:", warning, file=sys.stderr)
            return script
        problems = errors + warnings
        prompt += "\n\nLẦN TRƯỚC BỊ LỖI, hãy sửa và trả lại JSON đầy đủ:\n- " + "\n- ".join(problems)
    raise ValueError("Kịch bản không đạt kiểm tra:\n" + "\n".join(problems))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="File nội dung thay cho NOI_DUNG.")
    parser.add_argument("--output", type=Path, help="Lưu kịch bản JSON để phân tích và dựng preview sau.")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION, help="Tổng thời lượng video (giây).")
    args = parser.parse_args(argv)
    content = args.input.read_text(encoding="utf-8") if args.input else NOI_DUNG
    screenplay = generate_script(content, args.duration)
    text_out = json.dumps(screenplay, ensure_ascii=False, indent=2)
    print(text_out, flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text_out + "\n", encoding="utf-8")
        print(f"Đã lưu kịch bản: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"API trả HTTP {error.code}.")
    except (URLError, TimeoutError, ValueError, OSError) as error:
        raise SystemExit(f"Lỗi: {error}")
