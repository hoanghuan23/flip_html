# mô tả hiệu ứng người dùng muốn

Thêm mưa rơi bên trong vùng tô của từng cột biểu đồ. Hạt mưa lớn, dài và rõ nét có màu trắng sáng nổi bật trên nền tối, nhìn thấy rõ
ngay khi xem toàn cảnh. Cột có lượng mưa cao hơn thì mưa dày hơn, dựa trên dữ
liệu đang có. Các cột lần lượt bắt đầu mưa từ trái sang phải, mỗi giây thêm một
cột; cột đã bắt đầu thì tiếp tục mưa đến hết video.

Nước đọng ở chân mỗi cột dâng dần khi mưa rơi, tạo thành một lớp nước
dễ thấy, thay vì chỉ là một vệt mỏng sát đáy. Mặt nước nhấp nhô nhẹ, có gợn sóng
lan ra rõ ràng khi giọt mưa chạm xuống. Chuyển động mượt, tự nhiên, hài hòa với
phong cách tối của biểu đồ và vẫn để nhìn rõ ảnh nền, nhãn và số liệu.

Bổ sung đám mây đen có nhiều khối mây giống như thật ở phần trên của vùng mưa từng cột.
Thêm tia sét trắng xanh phân nhánh chớp xuống trong cột khi cột đã kích hoạt.
Mây và sét phải rõ, chuyển động đồng bộ với mưa, không che nhãn hoặc số liệu.

Giữ nguyên toàn bộ bố cục, ảnh nền, nhãn, số liệu, màu chữ và chiều cao các cột.
Video dài mười hai giây, không âm thanh.

## Quy tắc kỹ thuật gửi kèm AI

Bạn sửa mã HTML/CSS/JS của dự án HyperFrames theo mô tả ở trên. Có thể bổ sung
hiệu ứng mới, hàm vẽ, phần tử HTML, CSS hoặc file JS mới; không bị giới hạn ở
các trường cấu hình hiệu ứng cũ. Mã hiện tại được gửi trong CURRENT_PROJECT_FILES.

- Chỉ sửa/tạo index.html hoặc các file .html/.css/.js bên trong assets/rain-chart/
  và compositions/. Không sửa ai/, verification/, package.json hoặc tài nguyên gốc.
- rain_chart là nguồn chỉ đọc. Giữ nguyên dữ liệu, ảnh nền, bố cục, font, nhãn,
  màu chữ và chiều cao các cột trên bản sao. Không viết lại hoặc hardcode số liệu.
- Giữ video 12 giây, 1920×1080, 30 fps, không âm thanh; kích hoạt cột i tại giây i
  và tiếp tục hoạt động đến hết video. Không đổi chiều cao cột để chứa hiệu ứng.
- Dùng Canvas/CSS/JS và tài nguyên cục bộ. Mọi hình ảnh phải là hàm của thời gian
  tuyệt đối và seed cố định: không Math.random(), Date.now(), performance.now(),
  timer, requestAnimationFrame, mạng hoặc vòng lặp tự chạy trong mã animation.
- Giữ giao diện window.RainChartEffects.create(chart,data), trả về renderAt(t),
  resize() và getMetrics(). Giữ window.RainChart và window.renderAt(t) để preview
  và kiểm thử. Mọi hiệu ứng mới cũng phải seek tiến/lùi được, không phụ thuộc frame trước.
- getMetrics() giữ thông tin từng cột: label, value, ratio, width, height,
  density và start. Mật độ hiệu dụng/ratio phải bằng nhau giữa các cột; đọc giá trị
  và vùng tô từ biểu đồ. Giữ sáu Canvas .rain-effects để kiểm tra thứ tự kích hoạt.
- Trang HTML độc lập và scene HyperFrames đều phải nạp đủ các file mới. Scene dùng
  timeline paused đăng ký vào window.__timelines và nhận hf-seek như mã hiện tại.
- Đánh dấu mọi lớp trang trí bổ sung bằng data-rain-effect; không gắn vào nội dung
  biểu đồ gốc. Khi ẩn .rain-effects và [data-rain-effect], biểu đồ phải như bản gốc.
- Có thể mở rộng hoặc thay cách dùng effects-config.js/effects-settings.js nếu
  các giới hạn cũ cản trở yêu cầu (ví dụ nước dâng cao, mây hoặc sét). Cập nhật đủ
  các file liên quan để mã chạy được; không chỉ trả về một bộ số cấu hình.
- Trả duy nhất JSON theo RESPONSE_FORMAT, files chứa đường dẫn tương đối và TOÀN
  BỘ nội dung mới của từng file cần đổi/tạo. Chỉ gửi các file thực sự cần thay đổi.
  Không markdown, không diff, không lệnh shell. Nếu không thực hiện được, trả
  {"error":"giải thích ngắn gọn bằng tiếng Việt"}.
