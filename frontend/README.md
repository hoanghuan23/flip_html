# AI Video Studio

Frontend React + TypeScript cho pipeline video Python. Giao diện có bốn bước:
nhập nội dung, chọn phong cách, chỉnh kịch bản, xem trước và xuất MP4.

AI và chat hiện dùng dữ liệu mẫu. Preview HTML được tạo trên backend và chính
những file đó được HyperFrames render thành MP4 thật. Video không có âm thanh.

## Chạy ứng dụng

Cần Python 3.10+, Node.js 22+, Chrome/Chromium và FFmpeg (bao gồm ffprobe).
Từ thư mục gốc dự án:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Mở **http://127.0.0.1:8000**. Build trước khi khởi động backend; sau lần build
đầu tiên cần khởi động lại backend để mount thư mục `dist`.

Kiểm tra công cụ trước lần render đầu:

```bash
node --version
ffmpeg -version
ffprobe -version
npx --yes hyperframes@0.9.33 doctor --json
```

Nếu HyperFrames chưa tìm thấy trình duyệt:

```bash
npx --yes hyperframes@0.9.33 browser ensure
```

Lần chạy đầu có thể cần mạng để tải CLI và runtime của HyperFrames. API
`GET /api/health` kiểm tra sự hiện diện của các công cụ; lệnh `doctor` kiểm tra
khả năng render thực tế. Pipeline giữ phiên bản **0.9.33** của dự án.

## Phát triển

Chạy backend ở cổng 8000 như trên. Trong terminal thứ hai:

```bash
cd frontend
npm run dev
```

Mở **http://127.0.0.1:5173**. Vite chuyển tiếp `/api` đến backend. Frontend
không chứa khóa API, không gọi AI thật và không yêu cầu dịch vụ cloud.

## Luồng xuất video

1. Nhập nội dung (hoặc thử nội dung mẫu), chọn phong cách và tạo kịch bản mẫu.
2. Chỉnh cảnh, thời lượng và chữ giải thích. Chat mẫu hỗ trợ rút ngắn, giọng vui
   hơn và viết lại chữ giải thích cho cảnh đang chọn.
3. Chọn **Đồng ý & tạo animation**. Duyệt các phase bằng phát/dừng và thanh tua.
4. Chọn **Xuất video**, đặt tên, FPS 24/30/60 và chất lượng Nháp/Tiêu chuẩn/Cao.
5. Chọn **Bắt đầu xuất**. Máy chủ chuẩn bị project, kiểm tra HyperFrames, chụp
   khung hình, render và xác minh MP4 bằng ffprobe.
6. Khi hoàn tất, video xuất hiện ngay ở bước 4. Chọn **Tải video xuống** để tải
   đúng file đang xem. MP4 có HTTP Range nên hỗ trợ tua trong trình phát.

Mặc định: MP4 1920×1080, 16:9, 30 fps, chất lượng Cao. Chất lượng ánh xạ đến
`draft`, `looks`, `delivery`. Thời lượng từng cảnh >0 đến 120 giây, tối đa 100
cảnh và tổng thời lượng tối đa 30 phút. Một tác vụ chạy tại một thời điểm;
những tác vụ khác đợi trong hàng đợi. Giới hạn mỗi tác vụ là 60 phút.

## Dữ liệu và khôi phục

- Bản nháp tự lưu sau 500 ms trong localStorage, khóa `ai-video-studio:v1`.
  **Dự án của tôi** cho tạo, đổi tên, mở, xóa và xuất/nhập JSON phiên bản 1.
- Tài liệu TXT/DOCX tối đa 5 MB được đọc trong trình duyệt. DOCX chỉ lấy văn
  bản. File gốc không được lưu lên backend hoặc localStorage.
- Nếu trình duyệt không cho lưu hoặc hết dung lượng, thông báo lưu nháp hiển
  thị lỗi; dùng **Tải JSON** để giữ dữ liệu hiện tại.
- `storage/previews/<id>/` giữ snapshot, bản nháp dùng để dựng và HTML từng phase.
- `storage/exports/<id>/` giữ `job.json`, `render.log`, `video.mp4` và project
  HyperFrames. Các thư mục này không được Git theo dõi và không tự xóa.
- Mỗi tác vụ gắn với snapshot bất biến. Tiếp tục sửa kịch bản không thay đổi
  video đang render. Preview cũ sẽ chặn lần xuất mới đến khi được cập nhật.
- Tải lại trang tiếp tục theo dõi `jobId`. Backend khởi động lại sẽ đánh dấu
  các tác vụ dở dang là lỗi để người dùng thử lại; video đã hoàn tất vẫn còn.
- Khi chuyển máy hoặc xóa storage, tạo lại preview từ bản nháp trước khi xuất.
  JSON nhập lại chỉ khôi phục dữ liệu chỉnh sửa, không tin các URL media bên trong.

Ứng dụng mặc định chỉ bind localhost và phục vụ một người dùng. API chưa có
đăng nhập hoặc cơ chế phân quyền cho hosting công khai.

Biến môi trường tùy chọn, đặt khi khởi động backend:

- `VIDEO_STORAGE_DIR`: thư mục dữ liệu thay cho `storage/`.
- `HYPERFRAMES_COMMAND`: lệnh CLI đã cài sẵn, ví dụ `hyperframes`; mặc định là
  `npx --yes hyperframes@0.9.33`. Không nhận lệnh này từ trình duyệt.
- `PUPPETEER_EXECUTABLE_PATH`: đường dẫn Chrome khi cần chỉ định riêng.

## API

| Endpoint | Nội dung |
| --- | --- |
| `POST /api/previews` | `{projectId, title, styleId, scenes}` → snapshot và URL phase |
| `GET /api/previews/{id}` | Kiểm tra snapshot còn tồn tại |
| `GET /api/previews/{id}/phase_N.html` | HTML phase kiểm soát sẵn, có `renderAt(time)` |
| `POST /api/exports` | `{snapshotId, config: {filename, fps, quality}}` → tác vụ, HTTP 202 |
| `GET /api/exports/{id}` | Trạng thái, giai đoạn, tiến độ nếu CLI cung cấp, lỗi/kết quả |
| `GET /api/exports/{id}/video` | MP4 inline, hỗ trợ Range |
| `GET /api/exports/{id}/download` | Cùng MP4, Content-Disposition attachment |

Schema tương tác ở **http://127.0.0.1:8000/docs**. Không dùng JSON bản nháp
frontend trực tiếp làm `kich_ban.json` của pipeline AI hiện tại: đây là mô hình
giao diện và template minh họa, chưa chứa hợp đồng asset/action đầy đủ.

## Kiểm thử

```bash
python3 -m unittest backend.test_api -v
python3 -m unittest discover -s tests -p test_render_hyperframes.py -v
cd frontend
npm test
npm run build
```

API tests dùng thư mục tạm và mock worker, kiểm tra validation, snapshot, chống
gửi lặp, khôi phục tác vụ và Range/download. Test xác minh video kiểm tra sai
thời lượng, kích thước và FPS. Frontend tests kiểm tra bản nháp, invalidation
preview, giới hạn AI demo và việc nhập JSON không mang theo URL lạ.

Các lần render thật và kiểm tra trình duyệt khi triển khai được lưu trong
`storage/qa/` (ảnh desktop/tablet/mobile, khung hình MP4 và báo cáo JSON).

Để chạy lại kiểm thử toàn luồng, khởi động backend với bản frontend đã build,
rồi mở terminal khác:

```bash
cd frontend
npm run test:e2e
```

Test dùng `puppeteer-core` với Chrome có sẵn, đọc TXT/DOCX, sửa kịch bản, chat,
tạo preview và render video ngắn 24 fps/Nháp thật. Test tải lại trang khi render,
kiểm tra MP4, tua/tải xuống, nhập JSON và bố cục 375/768 px. Báo cáo nằm ở
`storage/qa/browser-report.json`. Có thể đặt `CHROME_PATH`, `STUDIO_URL` và
`PYTHON_COMMAND` nếu các đường dẫn/lệnh mặc định khác trên máy bạn.
