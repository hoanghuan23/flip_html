---
name: map-2d
description: Phong cách bản đồ du lịch 2D, tuyến đỏ và biểu tượng phương tiện nổi bật.
---
# Map 2D

## Diện mạo
- Luôn dùng bản đồ nền OpenFreeMap với style Liberty tại `https://tiles.openfreemap.org/styles/liberty`. MapLibre GL JS chỉ là bộ hiển thị bản đồ; không thay nguồn bản đồ nền theo kịch bản hoặc biến môi trường. Dịch vụ tìm tọa độ và định tuyến là dữ liệu riêng, được chọn theo yêu cầu của template và kịch bản.
- Bản đồ phẳng, góc nhìn từ trên xuống, nền đất kem nhạt #F1F0DC, nước xanh nhạt #A9DCEC, công viên xanh nhẹ #C9DFB9; đường nền xám hoặc hồng nhạt. Chữ địa danh xám đậm, dễ đọc. Không dùng nền vệ tinh hay địa hình 3D.
- Tuyến hành trình màu đỏ #D71920, nét liền, đầu tròn, khoảng 6–8 px ở khung 1920×1080. Tuyến đã đi nổi bật; tuyến chưa đi có thể ẩn hoặc hiển thị mờ nếu Plan yêu cầu.
- Điểm đến là chấm tròn đỏ, viền sáng mảnh, đường kính khoảng 18–24 px; điểm đang dừng có vòng nhấn nhẹ. Không tô toàn bộ địa giới nếu kịch bản chỉ nói về một địa điểm.
- Nếu kịch bản có phương tiện, vẽ icon 2D nhìn từ trên xuống hơi chếch, kính và bánh dễ phân biệt. Màu, loại xe và hành lý lấy từ kịch bản; giữ cùng một asset xuyên suốt, đầu xe hướng theo xu hướng của một đoạn tuyến đủ dài để tránh rung lắc ở từng đỉnh đường nhỏ. Vị trí xe vẫn bám đúng tuyến. Kích thước gợi ý 65–90 px ở khung 1920×1080, không tính theo kích thước địa lý thật.
- Nhãn khoảng cách nếu có: chữ trắng trên nền đỏ bo tròn; chỉ dùng số do dữ liệu tuyến cung cấp.
- Ảnh chú giải địa điểm: thẻ nền sáng, viền mảnh, ảnh rõ chủ thể, tên tiếng Việt ở lớp chữ chỉnh sửa được. Giữ một kiểu thẻ, không che xe, tuyến hoặc địa danh quan trọng. Dùng nguyên ảnh minh họa đã tải lên theo mã @image_N và các mốc hiện/thay/thu từ kịch bản; không tái tạo ảnh bằng AI.

## Tài nguyên và kiểm tra
Tách nền bản đồ, tuyến, chấm, xe, chữ và thẻ ảnh thành các lớp riêng; icon nền trong suốt nếu xuất PNG. Duy trì màu sắc, hình dáng, tỷ lệ hiển thị ở mọi phase. Không vẽ lại dữ liệu địa lý theo trí tưởng tượng. Các giá trị pixel là mặc định thẩm mỹ, được điều chỉnh theo độ phân giải và mật độ bản đồ. Không quy định địa điểm, tuyến, thời điểm hay camera trong style; những việc đó thuộc template và Plan.
