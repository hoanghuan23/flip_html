---
name: detailed-vector
description: >-
  Minh họa Detailed Editorial Vector Illustration + Light 2.5D Scientific Explainer
  theo Plan, với silhouette nhiều lớp, đường cong Bézier, gradient mềm và ánh sáng
  nhất quán. Dùng để thiết kế hình vẽ, asset, pose và chú giải cho video giải thích;
  không quy định cấu trúc đầu ra SVG hoặc cách triển khai animation.
---

# Detailed Vector

Phong cách Detailed Editorial Vector Illustration + Light 2.5D Scientific Explainer.
Detailed editorial illustration with light 2.5D scientific explainer shading.
Áp dụng cùng cách tạo khối và đổ bóng khi xuất SVG hoặc PNG; định dạng đầu ra
do pipeline yêu cầu.
Áp dụng cho mọi chủ đề theo Plan, không mặc định một loại cảnh hay đồ vật.
Style trong JSON cung cấp palette, font, nhận diện và quy ước nội dung; nâng mức
diễn họa theo chuẩn này mà không đổi các ràng buộc đó, kể cả khi notes còn ghi flat.
Góc nhìn theo camera.view và camera.detail của Plan: top-down (từ trên),
side (nhìn ngang) hoặc section (mặt cắt). Giữ phối cảnh, hướng nhìn và tỷ lệ
giữa nền, nhân vật, bộ phận và đồ vật; chỉ đổi góc khi Plan yêu cầu, dùng pose phù hợp.

## HÌNH KHỐI EDITORIAL VÀ CHIỀU SÂU 2.5D NHẸ

- Đối tượng phức tạp cần silhouette đặc trưng và nhiều lớp vector có cấu trúc:
  khối chính, bộ phận chức năng, mặt tiếp giáp, vùng sáng/tối và điểm tương tác.
  Không thay bằng icon, vài ellipse/circle chồng lên nhau hoặc hình xoắn đơn độc.
  Dùng path với đường cong Bézier cho đường bao tự nhiên; hình cơ bản phù hợp
  với bộ phận đơn giản, không phải khuôn mẫu cho mọi đối tượng.
- Tạo thể tích bằng các mặt/lớp chồng hợp lý, linearGradient/radialGradient mềm,
  highlight tiết chế và bóng tiếp xúc/bóng đổ vector opacity 0.12-0.20.
  Chọn một hướng sáng, giữ nhất quán trong cảnh và giữa các pose cùng góc nhìn.
  Thể hiện ranh giới bề mặt, chiều sâu và chất liệu mà không tăng trang trí vô nghĩa.
- Chỉ dùng phối cảnh nhẹ khi phù hợp camera. Với section, giữ đúng mặt cắt,
  vị trí các lớp và cao độ; với top-down, giữ hình chiếu từ trên, không thêm
  đường chân trời hoặc nghiêng thành isometric để tạo cảm giác 3D.
- Người và động vật có tỷ lệ, tư thế, khớp nối và điểm tiếp xúc hợp lý.
  Không photorealistic, 3D thực, texture ảnh chụp, filter hoặc blur.
Màu theo palette và vai trò trong Plan, tương phản đủ với nền. Giữ màu, hình dạng
nhận diện và kích thước tương đối của cùng asset giữa các phase, trừ thay đổi được mô tả.

## NGUYÊN TẮC ĐỒ HỌA GIẢI THÍCH

- Hình phải giúp nhận ra đối tượng và hiện tượng ngay cả khi ẩn caption.
  Mỗi phase có một trọng tâm; dùng khoảng trống, tương phản, lớp hình và thứ tự
  chuyển động để dẫn sự chú ý. Ưu tiên khả năng đọc ở màn hình nhỏ hơn số chi tiết.
- Người xem phải nhận ra trạng thái ban đầu, diễn biến trung gian và kết quả.
  Khi có quan hệ nhân quả, làm rõ vật gây tác động, nơi tương tác và thay đổi tạo ra.
- Tách rõ vật thể, đường chuyển động và chú giải. Chỉ chồng hình khi thể hiện
  tiếp xúc/che khuất có ý nghĩa; không che bộ phận đang giải thích.
- Mũi tên, đường dẫn, nhãn và hiệu ứng phải có nghĩa cụ thể theo Plan, phân biệt
  chỉ dẫn với vật thể thật; dùng ít, nhất quán, không giao cắt làm nhầm hướng hay đối tượng.
- Plan quyết định kiến thức và diễn biến cốt lõi. Chỉ cụ thể hóa cách vẽ và bố trí;
  không tự thêm nguyên nhân, bước cơ chế, dữ kiện hoặc kết quả, không biến minh họa
  hay giả thuyết thành sự thật. Nếu có xung đột, ưu tiên nội dung Plan hơn hiệu ứng đẹp.

## VẬN DỤNG THEO ĐỐI TƯỢNG (chỉ khi Plan có, không tự thêm vào cảnh khác)

- Mây: khối tích nhiều tầng với đường bao tự nhiên, mặt sáng, lõi tối và chân mây;
  phân biệt cụm dông rời, tháp phát triển cao, dải cong và hệ có tổ chức theo pose.
  Không dùng icon dự báo thời tiết. Biển: phân lớp nước, mặt sóng và sắc độ có
  hướng; khí quyển: lớp màu bán trong suốt khi Plan cần phân biệt các vùng khí.
- Hiện tượng vô hình: giữ bối cảnh nguồn, đường đi và tác động quan sát được;
  hạt, vùng màu hay đường bao chỉ là ký hiệu phụ đúng quy ước của Plan.
  Với bốc hơi, làm rõ mặt nước cung cấp ẩm và không khí ẩm đi lên nếu Plan mô tả;
  không biến hơi nước vô hình thành khói trắng. Giọt ngưng tụ khác ký hiệu hơi ẩm.
- Hệ mây xoáy: nhiều cụm mây kết nối thành dải, có khoảng cách và chiều sâu,
  không thay toàn bộ hệ bằng một nét xoắn. Giữ chiều xoáy/bán cầu do Plan chỉ định;
  không tự thêm mắt bão hoặc chi tiết của giai đoạn chưa được yêu cầu.
- Gió/dòng khí: đường cong Bézier mượt, đầu mũi tên rõ, không che khối chính;
  phân biệt sơ đồ hướng gió tĩnh với mẫu khí đang chuyển động. Cùng nguyên tắc
  nguồn -> đường truyền -> tác động áp dụng cho chất lỏng, máy móc và chủ đề khác.

## THIẾT KẾ ASSET VÀ POSE (khi vẽ thư viện)

Các pose của cùng đối tượng giữ ngoại hình, màu, tỷ lệ và mức độ chi tiết,
trừ biến đổi tư thế, hình dạng hoặc góc nhìn mà Plan yêu cầu.

Mỗi asset/pose phải có bộ phận, khớp, bề mặt và
điểm tiếp xúc cần cho hành động; silhouette phải phân biệt được trạng thái liên quan.
Xây từ các lớp hình học có chủ đích: đường bao Bézier, khối/bề mặt chính,
vùng tối, highlight và chi tiết chức năng theo quy mô thực của asset trên canvas.
Gradient phân biệt thể tích và lớp vật chất, không chỉ tô bóng một icon đơn giản.

Thể hiện đúng biến đổi nội dung của pose,
không chỉ khác màu/kích thước hoặc sao chép hình gốc rồi xoay/co giãn; ngoại lệ
là khi chính Plan yêu cầu thay đổi màu, cỡ hoặc hướng nhìn đó. Giữ các mốc cấu trúc
tương ứng qua pose để khi mờ chuyển vẫn nhận ra cùng đối tượng đang biến đổi.

## CHẤT LƯỢNG HÌNH MINH HỌA

Bóng đổ là hình vector có opacity, không filter.
Dùng lượng phần tử vừa đủ cho silhouette và cấu tạo,
không rải hàng nghìn hạt/sóng/highlight. Tái dùng hình tĩnh và gradient nội bộ
khi phù hợp; ưu tiên path gọn thay vì nhiều chi tiết nhỏ khó nhìn.

## LỚP HÌNH VÀ TƯƠNG PHẢN

Background ở dưới cùng; các lớp còn lại theo vị trí không gian và điểm tương tác,
đảm bảo bộ phận đang giải thích không bị che.
Ưu tiên nền ít tương phản, chủ thể rõ khối, hiệu ứng gắn vùng tác động và chú giải
dễ đọc.

## PHONG CÁCH CHÚ GIẢI THÀNH PHẦN

- Chủ động chú giải các thành phần và quá trình cần nhận diện để hiểu phase,
  theo đúng tên gọi và nội dung Plan; tránh gắn nhãn cho mọi chi tiết trang trí.
- Không giới hạn số từ trong nhãn. Viết đủ nghĩa, dễ hiểu.
- Dùng hộp chữ bo góc, nền sáng, viền mảnh và chữ đậm tương phản rõ. Màu hộp,
  viền và đường dẫn theo palette, có thể dùng sắc ấm/lạnh để liên hệ với đối tượng.
  Giữ font, cỡ chữ và kiểu hộp nhất quán giữa các phase, đủ đọc trên màn hình nhỏ.
- Nối mép hộp với đúng bộ phận hoặc vùng cần giải thích bằng đường dẫn mảnh,
  thẳng hoặc gấp khúc, có đầu mũi tên rõ ở phía đối tượng. Phân biệt đường chú
  giải với mũi tên biểu diễn chuyển động hoặc tác động; không để đường xuyên chữ.
