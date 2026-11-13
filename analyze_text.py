"""Sinh và in kịch bản AI. Dùng --output để lưu cho generate_preview.py."""

import argparse
import json
import os
from pathlib import Path
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
**Chủ đề: Vụ tai nạn tại ngã tư**
Vào một buổi sáng đông đúc, một nam thanh niên điều khiển xe máy trên đường đến nơi làm việc. Khi đến ngã tư, anh cố vượt đèn vàng đúng lúc một chiếc ô tô bắt đầu rẽ trái. Hai phương tiện va chạm khiến người đi xe máy ngã xuống đường.
Những người xung quanh nhanh chóng chạy đến giúp đỡ, gọi cấp cứu và cảnh báo các phương tiện khác. Lực lượng chức năng sau đó có mặt để xử lý hiện trường.
"""

PROMPT = """
Bạn là đạo diễn và chuyên gia thiết kế hoạt hình 2D.

Nhiệm vụ: Chuyển nội dung đầu vào thành một kịch bản video
hoàn chỉnh, bao gồm KỊCH BẢN NỘI DUNG và KỊCH BẢN KỸ THUẬT
trong cùng một tài liệu Markdown.

MỤC TIÊU:
Kịch bản sẽ được sử dụng để tự động tạo ảnh nền, nhân vật,
sprite animation và dựng HTML/CSS/JavaScript cho từng phase.
Các phase sau đó được ghép thành video bằng HyperFrames.

I. PHÂN TÍCH CÂU CHUYỆN

1. Xác định nhân vật, phương tiện, vật thể và bối cảnh.
2. Chia câu chuyện thành các phase theo trình tự hợp lý.
3. Đề xuất thời lượng phù hợp, ưu tiên video ngắn gọn.
4. Mỗi phase phải có diễn biến rõ ràng theo từng khoảng thời gian.
5. Đảm bảo tính liên tục giữa các phase.
6. Có thể bổ sung chi tiết hợp lý nhưng không thay đổi
   nội dung chính của câu chuyện.

II. PHÂN TÍCH KỸ THUẬT ANIMATION

Với mỗi phase, bắt buộc xác định:

1. Camera:
   - Góc nhìn và vị trí camera.
   - Camera cố định hay chuyển động.
   - Hướng chuyển động nếu có.

2. Đối tượng:
   - Nhân vật, phương tiện, vật thể xuất hiện.
   - Vị trí bắt đầu và kết thúc.
   - Hướng di chuyển và tỷ lệ hiển thị.

3. Sprite Animation:
   - Các tư thế (pose) cần tạo.
   - Thứ tự chuyển đổi giữa các pose.
   - Hành động nào cần nhiều frame animation.

4. Timeline:
   - Thời điểm bắt đầu và kết thúc từng hành động.
   - Chuyển động của đối tượng theo thời gian.
   - Các hành động diễn ra đồng thời hoặc nối tiếp.

5. Phương pháp thực hiện:
   - CSS transform cho di chuyển, xoay, thay đổi tỷ lệ.
   - Sprite Animation cho thay đổi tư thế nhân vật.
   - JavaScript cho điều khiển timeline và trạng thái.
   - Hiệu ứng bổ sung nếu cần.

6. Trạng thái:
   - Trạng thái ban đầu của phase.
   - Trạng thái kết thúc của phase.
   - Những thông tin cần kế thừa sang phase tiếp theo.

III. QUẢN LÝ ASSET

Trước danh sách phase, tạo danh sách asset dùng chung:

- Background: các ảnh nền cần sinh.
- Character: các nhân vật cần sinh.
- Object: phương tiện và vật thể cần sinh.
- Sprite: danh sách pose và animation cần thiết.

Mỗi asset có ID duy nhất.
Tái sử dụng asset giữa các phase.
Không tạo lại asset giống nhau nếu không cần thiết.

IV. QUY TẮC KỸ THUẬT

- Canvas chuẩn: 1920x1080.
- Hệ tọa độ có gốc (0,0) tại góc trên bên trái.
- Tọa độ, kích thước và tốc độ chỉ là giá trị dự kiến
  trước khi sinh ảnh, cần hiệu chỉnh theo asset thực tế.
- Không tự ý thay đổi thiết kế nhân vật giữa các phase.
- Các chuyển động phải hợp lý về không gian và thời gian.
- Không thêm hành động không đóng góp cho câu chuyện.
- Không sinh mã HTML, CSS hoặc JavaScript.
- Không sinh ảnh ở bước này.

V. CẤU TRÚC ĐẦU RA

# KỊCH BẢN VIDEO
Tổng thời lượng: ... giây

## 1. Danh sách asset dùng chung
Liệt kê ID, tên, mô tả và mục đích sử dụng.

## 2. Danh sách phase

### Phase N — Tên phân cảnh
Thời lượng: ... giây

#### A. Kịch bản nội dung
- Bối cảnh
- Nhân vật
- Diễn biến theo thời gian
- Âm thanh
- Trạng thái đầu
- Trạng thái cuối

#### B. Kịch bản kỹ thuật
- Camera
- Asset sử dụng
- Vị trí và hướng di chuyển
- Sprite pose cần thiết
- Timeline animation
- Phương pháp animation
- Trạng thái kỹ thuật đầu/cuối

VI. YÊU CẦU CUỐI CÙNG

- Kịch bản nội dung và kỹ thuật phải thống nhất.
- Tổng thời lượng phải bằng tổng thời lượng các phase.
- Timeline của từng phase phải nằm trong thời lượng phase.
- Không bỏ trống phần kỹ thuật của bất kỳ phase nào.
- Trình bày rõ ràng, dễ đọc bằng tiếng Việt.
- Chỉ trả về nội dung Markdown.

Nội dung đầu vào:
{user_text}
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


def generate_script(text):
    return request_text(PROMPT.format(user_text=text))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="File nội dung thay cho NOI_DUNG.")
    parser.add_argument("--output", type=Path, help="Lưu kịch bản để phân tích và dựng preview sau.")
    args = parser.parse_args(argv)
    content = args.input.read_text(encoding="utf-8") if args.input else NOI_DUNG
    screenplay = generate_script(content)
    print(screenplay, flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(screenplay.rstrip() + "\n", encoding="utf-8")
        print(f"Đã lưu kịch bản: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"API trả HTTP {error.code}.")
    except (URLError, TimeoutError, ValueError, OSError) as error:
        raise SystemExit(f"Lỗi: {error}")
