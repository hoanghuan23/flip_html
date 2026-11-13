import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Sửa trực tiếp các biến dưới đây, rồi chạy: python3 analyze_text.py
API_URL = "http://127.0.0.1:8000/generate-video"
API_KEY = "23092003"
MODEL = "gpt-5.6-luna"

NOI_DUNG = """
Một cô bé tìm thấy chiếc ô màu vàng trước cửa nhà vào một buổi sáng mưa.
Trên đường đến trường, cô che mưa cho một chú mèo và một bạn nhỏ.
Khi trời tạnh, cả ba cùng nhìn thấy cầu vồng.
"""

PROMPT = f"""
Bạn là đạo diễn AI, có nhiệm vụ chuyển nội dung văn bản thành kịch bản video.

Dựa trên nội dung đầu vào, hãy:

1. Phân tích nhân vật, bối cảnh và diễn biến câu chuyện.
2. Chia câu chuyện thành các phân cảnh (phase) theo trình tự hợp lý.
3. Với mỗi phase, mô tả rõ bối cảnh, nhân vật, hành động, chuyển động, âm thanh và thời lượng.
4. Tự đề xuất thời lượng phù hợp với nội dung, tránh kéo dài các hành động đơn giản hoặc không cần thiết.
5. Trong mỗi phase, mô tả thứ tự hành động và thời điểm diễn ra tương đối so với thời gian bắt đầu phase.
6. Đảm bảo các phase liên kết tự nhiên. Trạng thái nhân vật, vật thể và bối cảnh ở cuối phase trước phải được kế thừa hợp lý ở đầu phase tiếp theo. Cần kiểm tra trạng thái đầu và cuối phase
7. Có thể bổ sung chi tiết hoặc hành động phụ để câu chuyện tự nhiên, sinh động hơn nhưng không làm thay đổi nội dung chính.
8. Mô tả hành động đủ cụ thể để có thể chuyển thành hình ảnh và chuyển động trong video.

Ưu tiên kịch bản ngắn gọn, nhịp kể tự nhiên. Thời lượng mỗi phase phải tương ứng với số lượng và độ phức tạp của hành động, không kéo dài chỉ để tạo cảm giác điện ảnh
Các hành động đơn giản nên diễn ra trong khoảng 1-3 giây; chỉ dành thời gian dài hơn cho những chuyển động hoặc sự kiện thực sự cần thiết. Không thêm cảnh mở đầu, kết thúc hoặc hành động phụ
nếu không đóng góp đáng kể vào câu chuyện

Trả về kịch bản dễ đọc, có cấu trúc rõ ràng bằng tiếng Việt, bao gồm tổng thời lượng và thời lượng từng phase.

Chỉ trả về văn bản kịch bản

Nội dung đầu vào:
{{USER_TEXT}}

Nội dung đầu vào:
{NOI_DUNG}
"""


if __name__ == "__main__":
    request = Request(
        API_URL,
        data=json.dumps({"prompt": PROMPT, "model": MODEL}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": API_KEY},
        method="POST",
    )

    try:
        with urlopen(request, timeout=600) as response:
            data = json.load(response)
        if data.get("success") is not True or not isinstance(data.get("result"), str):
            raise ValueError("Server không trả kết quả text thành công.")
        print(data["result"])
    except HTTPError as error:
        raise SystemExit(f"API trả HTTP {error.code}.")
    except (URLError, TimeoutError, ValueError) as error:
        raise SystemExit(f"Lỗi: {error}")
