# Giao diện video

Giữ bố cục ba phần, bản nháp và trình phát hiện có. Cấu hình danh mục/phong cách
đang rỗng; mục 2 không có lựa chọn và nút tạo đồ họa bị khóa. Backend chỉ giữ luồng
render HyperFrames từ preview HTML; thao tác tạo nội dung mới báo chưa có cấu hình.

Xem [hướng dẫn cài đặt, render và kiểm thử](../README.md).

```bash
npm ci
npm run dev
```

Vite dùng cổng 5173 và proxy API tới `http://127.0.0.1:8001`.
`npm run build` tạo `dist/` để FastAPI phục vụ cùng API. `npm test` kiểm tra contract
bản nháp và các component. `npm run test:exports` kiểm tra giao diện rỗng cùng luồng
xuất video với fixture HTML local, không gọi dịch vụ AI.
