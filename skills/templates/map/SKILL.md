---
name: map
description: Diễn họa nội dung trên không gian địa lý.
---

# Map Template

## 1. Mục tiêu

Sử dụng bản đồ làm không gian diễn họa chính để
truyền tải nội dung và diễn biến của kịch bản.

Không giới hạn quốc gia, khu vực, đối tượng,
chủ đề hoặc loại sự kiện.

## 2. Nguyên tắc diễn họa

- Bản đồ là hệ quy chiếu không gian chính.
- Các đối tượng được đặt tại vị trí địa lý tương ứng.
- Sự di chuyển được thể hiện bằng sự thay đổi
  vị trí của đối tượng trên bản đồ.
- Mối liên kết giữa các địa điểm được thể hiện
  bằng tuyến đường hoặc đường kết nối khi cần.
- Các khu vực được làm nổi bật khi có ý nghĩa
  đối với nội dung.
- Nhãn và thông tin xuất hiện theo diễn biến
  của kịch bản.

## 3. Phân tích kịch bản

Tự xác định phạm vi địa lý, đối tượng, địa điểm,
sự kiện, mối quan hệ không gian và trình tự thời gian.

Tự lựa chọn bố cục, tỷ lệ bản đồ, góc nhìn,
chuyển động camera và phương thức diễn họa
phù hợp với nội dung.

Không giới hạn khả năng diễn họa vào các ví dụ
hoặc tình huống đã được định nghĩa trước.

## 4. Chuyển động

- Đối tượng di chuyển theo diễn biến kịch bản.
- Camera có thể zoom, pan hoặc theo dõi đối tượng.
- Đối tượng, nhãn và tuyến đường phải đồng bộ
  với hệ tọa độ bản đồ khi camera thay đổi.
- Duy trì tính liên tục giữa các phase và scene.
- Chuyển động đồng bộ với timeline và lời đọc
  nếu có.

## 5. Tính nhất quán

- Giữ nguyên nhận diện đối tượng xuyên suốt video.
- Duy trì hệ tọa độ và quy ước biểu diễn nhất quán.
- Không tự thay đổi hình dạng địa lý.
- Không tự thêm dữ kiện hoặc sự kiện ngoài kịch bản.
- Sử dụng dữ liệu địa lý đáng tin cậy.
- Phân biệt tuyến đường thực tế và đường minh họa.

## 6. Phân quyền với Style Skill

Template này chỉ quyết định phương thức diễn họa.

Không áp đặt:
- Màu sắc.
- Nét vẽ.
- Chất liệu.
- Ánh sáng.
- Phong cách 2D hoặc 3D.
- Kỹ thuật minh họa.

Các thuộc tính trên do Style Skill được chọn
quyết định.

Kịch bản quyết định nội dung.
Template quyết định phương thức diễn họa.
Style quyết định diện mạo hình ảnh.
Renderer quyết định kỹ thuật triển khai.

## 7. Kiểm tra kết quả

- Vị trí và quan hệ địa lý chính xác.
- Trình tự sự kiện đúng kịch bản.
- Chuyển động đúng tuyến đã xác định.
- Các đối tượng không bị thay đổi nhận diện.
- Camera và các lớp hình ảnh đồng bộ.
- Phong cách hình ảnh đúng Style Skill đã chọn.