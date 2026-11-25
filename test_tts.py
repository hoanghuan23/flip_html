
from vieneu import Vieneu
import time

tts = Vieneu()

text = """
Có bao giờ bạn tự hỏi tại sao những người thành công
thường có những thói quen rất khác biệt?
Thực ra, bí quyết không nằm ở may mắn,
mà nằm ở những lựa chọn nhỏ bé mỗi ngày.
"""

start = time.time()

audio = tts.infer(
    text=text,
    voice="Hải Đăng"
)

tts.save(audio, "output.wav")

print(f"Thời gian xử lý: {time.time() - start:.2f}s")
print("Đã lưu file output.wav")
