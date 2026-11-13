Yêu cầu Codex: Thêm hiệu ứng và xuất video HyperFrames
Đầu vào
- thư mực rain_chart đã có HTML/CSS/JS biểu đồ và số liệu, chưa có hiệu ứng mưa và nước đọng.
- Giữ nguyên bố cục, hình nền, các cột, nhãn và toàn bộ giá trị dữ liệu.

Prompt hiệu ứng
Thêm mưa rơi bên trong từng cột biểu đồ, mật độ mưa tỷ lệ với giá trị lượng mưa của cột. Tạo lớp nước đọng mỏng ở chân cột, có gợn sóng và vòng nước lan ra khi giọt mưa chạm mặt nước. Hiệu ứng mượt, tự nhiên, đồng bộ với phong cách tối của biểu đồ. Các cột lần lượt kích hoạt từ trái sang phải; tổng video 12 giây. Không thay đổi dữ liệu hay thiết kế gốc.

phần cấu hình gọi AI (url, model, key) đã có sẵn trong .env áp dụng theo

Thực hiện
1. Đọc mã nguồn rain_chart, xác định vị trí/kích thước từng cột và lấy giá trị lượng mưa từ dữ liệu hiện có; không hardcode số liệu.
2. Sinh hiệu ứng bằng CSS/JS hoặc Canvas, tách logic animation khỏi logic biểu đồ. Tránh sửa các phần không liên quan.
3. Animation phải điều khiển được bằng thời gian tuyệt đối renderAt(timeSeconds) và có seed ngẫu nhiên cố định; cùng một thời điểm phải cho cùng một frame. Không phụ thuộc setInterval, thời gian thực hoặc trạng thái frame trước.
4. Tạo composition HyperFrames từ dự án hiện có, nối thời gian HyperFrames với renderAt, cấu hình 12 giây, 1920×1080, 30 fps. Dùng API/CLI đúng theo phiên bản HyperFrames đang cài; kiểm tra lệnh bằng npx hyperframes --help nếu cần.
5. Preview, render ra output/rain_chart.mp4; kiểm tra file tồn tại và video hiển thị đúng mưa, nước đọng, số liệu.
Kết quả cần bàn giao
- Mã nguồn rain_chart đã bổ sung hiệu ứng.
- Composition/cấu hình HyperFrames chạy được.
- File output/rain_chart.mp4.
- Hướng dẫn ngắn lệnh preview và render thực tế.
Nếu gặp lỗi, sửa và thử render lại; không chỉ mô tả cách làm.