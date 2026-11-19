# AI Video Studio

Frontend React + TypeScript cho pipeline video Python. Giao diện có ba bước:
nhập nội dung và xem kịch bản, chọn phong cách, xem trước và xuất MP4.
Sau khi chọn **Tạo kịch bản**, danh sách cảnh hiển thị ngay trong mục 1.

Kịch bản được AI phân tích thật qua `plant_kurzge.py`: kiểm tra đầu vào, sinh
JSON chi tiết, kiểm tra và yêu cầu sửa nếu cần. Bảng chỉ trích tên, chữ giải
thích, mô tả hình ảnh và thời lượng từng phase. Hiện chỉ hỗ trợ xem kịch bản;
các nút sửa/thêm/xóa/chat được khóa.

Preview vẫn dùng đồ họa mẫu minh họa, chưa dựng hình từ assets/actions trong
JSON AI. HTML preview được HyperFrames render thành MP4 thật, không có âm thanh.

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

Chạy backend dev ở cổng 8001 từ thư mục gốc dự án:

```bash
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8001 --reload
```

Trong terminal thứ hai:

```bash
cd frontend
npm run dev
```

Mở **http://127.0.0.1:5173**. Vite chuyển tiếp `/api` đến backend ở cổng 8001.
Nếu chỉ chạy Vite, API và hình mẫu HTML sẽ không tải được. Frontend
không chứa khóa API; backend gọi dịch vụ AI theo cấu hình `.env` tại thư mục gốc:

```dotenv
CODEX_API_URL=https://your-ai-service.example/endpoint
CODEX_API_TOKEN=your-token
CODEX_MODEL=your-model
```

Dịch vụ nhận `{prompt, model}` qua POST với header `x-api-key`, trả
`{success: true, result: "chuỗi JSON"}`. Không đặt khóa vào biến `VITE_*`.
Khởi động lại backend sau khi đổi cấu hình.
Lưu file React/CSS hoặc `skills/style_config.json` để Vite tự cập nhật giao
diện. Không cần build lại khi phát triển. Cổng 8000 phục vụ bản build trong
`frontend/dist`, nên cần `npm run build` sau khi sửa giao diện ở chế độ đó.

## Luồng xuất video

1. Nhập nội dung (hoặc thử nội dung mẫu) và chọn **Tạo kịch bản**.
2. Theo dõi AI kiểm tra, tạo và lưu kịch bản. Đọc các cảnh xuất hiện ở mục 1.
   Đầu vào thiếu dữ kiện sẽ hiện lý do cần bổ sung. Tạo lại thất bại vẫn giữ bảng cũ.
3. Chọn danh mục/phong cách ở mục 2 và bấm **Tạo đồ họa**. Duyệt các phase bằng phát/dừng và thanh tua.
4. Chọn **Xuất video**, đặt tên, FPS 24/30/60 và chất lượng Nháp/Tiêu chuẩn/Cao.
5. Chọn **Bắt đầu xuất**. Máy chủ chuẩn bị project, kiểm tra HyperFrames, chụp
   khung hình, render và xác minh MP4 bằng ffprobe.
6. Khi hoàn tất, video xuất hiện ngay ở bước 3. Chọn **Tải video xuống** để tải
   đúng file đang xem. MP4 có HTTP Range nên hỗ trợ tua trong trình phát.

Mặc định: MP4 1920×1080, 16:9, 30 fps, chất lượng Cao. Chất lượng ánh xạ đến
`draft`, `looks`, `delivery`. Thời lượng từng cảnh >0 đến 120 giây, tối đa 100
cảnh và tổng thời lượng tối đa 30 phút. Một tác vụ xuất video chạy tại một thời điểm;
những tác vụ xuất khác đợi trong hàng đợi. Giới hạn mỗi tác vụ xuất là 60 phút.
Tạo kịch bản có hàng đợi riêng và không giới hạn thời gian chờ API AI.

Mục 2 lấy tên danh mục trực tiếp từ `categories.*.label` trong
`skills/style_config.json`. Mỗi danh mục chỉ hiển thị các phong cách thuộc
`allowed_styles`; nếu phong cách đang chọn không còn được phép, ứng dụng tự
chuyển sang phong cách hợp lệ (ưu tiên `default_style`). Lựa chọn danh mục
được lưu cùng bản nháp. Các preset cũ vẫn được đọc và chuyển đổi khi mở lại.
Cấu hình được frontend import trực tiếp từ file JSON. Khi chạy `npm run dev`,
Vite tự cập nhật sau khi lưu file; bản production cần build lại. Giữ nguyên
ID danh mục khi đổi tên để các bản nháp tiếp tục sử dụng danh mục đó.
Danh sách phong cách lấy đầy đủ, theo thứ tự trong `allowed_styles`. Thêm ID
mới sẽ tự hiện lựa chọn và đọc `skills/<styleId>/demo/index.html`; không cần
thêm ID vào danh sách cố định trong frontend. Flat with black và Halftone line
có tên, chú thích và bảng màu riêng. ID khác dùng tên suy ra từ ID và chú thích
mặc định; animation vẫn dùng mẫu minh họa kiểm soát sẵn (bảng màu Flat nếu
chưa có bảng màu riêng), không tự chuyển các hình trong demo thành animation.

Thẻ chọn phong cách chỉ hiển thị tên và chú thích. Khung mẫu lớn hiển thị
`skills/<styleId>/demo/index.html`, ví dụ `skills/flat/demo/index.html`,
trong iframe có thể cuộn để xem toàn bộ nội dung dài. Các demo hiện tại dùng
CSS và SVG nhúng trực tiếp trong HTML. Nếu chưa có file, khung để trống.
HTML được backend đọc trực tiếp; sau khi thêm hoặc thay demo, tải lại trang
hoặc chuyển phong cách để cập nhật, không cần build lại frontend.
Flat là phong cách riêng, được phép trong các danh mục có Outlined cartoon.

## Dữ liệu và khôi phục

- Bản nháp tự lưu sau 500 ms trong localStorage, khóa `ai-video-studio:v1`.
  ID tác vụ kịch bản đang chạy được lưu ngay để khôi phục khi tải lại.
  **Dự án của tôi** cho tạo, đổi tên, mở, xóa và nhập bản nháp JSON phiên bản 1.
  Không có nút tải JSON; bản đầy đủ được lưu trên máy chủ.
- Tài liệu TXT/DOCX tối đa 5 MB được đọc trong trình duyệt. DOCX chỉ lấy văn
  bản. File gốc không được lưu lên backend hoặc localStorage.
- Nếu trình duyệt không cho lưu hoặc hết dung lượng, thông báo lưu nháp hiển
  thị lỗi. JSON AI đã tạo vẫn nằm trên máy chủ.
- `storage/scripts/<id>/kich_ban.json` là bản AI đầy đủ, UTF-8 và có thụt dòng;
  đối chiếu `phases[*].name/narration/description/duration` với bảng trên màn hình.
  `input.txt` giữ đầu vào; `job.json` giữ trạng thái và dữ liệu trích xuất cho bảng.
  Mỗi lần tạo có ID riêng; không tạo JSON riêng cho bản user và không có API tải JSON.
- Tác vụ tạo kịch bản chạy trong tiến trình riêng, độc lập hàng đợi xuất video.
  Tải lại trang tiếp tục theo dõi ID đã lưu; chuyển dự án không trộn kết quả.
  Backend khởi động lại đánh dấu tác vụ dang dở là lỗi, giữ nguyên file đã hoàn tất.
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
| `POST /api/scripts` | `{projectId, content}` → tác vụ nền, HTTP 202; gửi lặp khi tác vụ còn chạy trả cùng ID |
| `GET /api/scripts/{id}` | Trạng thái/giai đoạn, lỗi hoặc `{title, scenes}` trích xuất; không trả JSON AI đầy đủ |
| `POST /api/previews` | `{projectId, title, categoryId, styleId, scenes}` → snapshot và URL phase |
| `GET /api/previews/{id}` | Kiểm tra snapshot còn tồn tại |
| `GET /api/previews/{id}/phase_N.html` | HTML phase kiểm soát sẵn, có `renderAt(time)` |
| `GET /api/styles/{styleId}/preview` | URL demo HTML, hoặc `null` nếu chưa có file |
| `GET /api/styles/{styleId}/demo/index.html` | Trang demo HTML của phong cách |
| `POST /api/exports` | `{snapshotId, config: {filename, fps, quality}}` → tác vụ, HTTP 202 |
| `GET /api/exports/{id}` | Trạng thái, giai đoạn, tiến độ nếu CLI cung cấp, lỗi/kết quả |
| `GET /api/exports/{id}/video` | MP4 inline, hỗ trợ Range |
| `GET /api/exports/{id}/download` | Cùng MP4, Content-Disposition attachment |

Schema tương tác ở **http://127.0.0.1:8000/docs**. Không dùng JSON bản nháp
frontend trực tiếp làm `kich_ban.json` của pipeline AI: bản nháp chỉ chứa dữ liệu
giao diện. Dùng file `storage/scripts/<id>/kich_ban.json` cho pipeline AI chi tiết.

## Kiểm thử

```bash
python3 -m unittest backend.test_api backend.test_scripts -v
python3 -m unittest discover -s tests -p test_render_hyperframes.py -v
cd frontend
npm test
npm run build
```

API tests dùng thư mục tạm và mock worker, kiểm tra validation, snapshot, chống
gửi lặp, khôi phục tác vụ và Range/download. Test xác minh video kiểm tra sai
thời lượng, kích thước và FPS. Frontend tests kiểm tra bản nháp, invalidation
preview, hợp đồng API kịch bản và việc nhập JSON không mang theo URL lạ.
Kiểm thử kịch bản dùng phản hồi giả lập; bài tích hợp chạy tiến trình Python thật
với dịch vụ AI giả lập trên localhost, không gọi dịch vụ AI thật.

Các lần render thật và kiểm tra trình duyệt khi triển khai được lưu trong
`storage/qa/` (ảnh desktop/tablet/mobile, khung hình MP4 và báo cáo JSON).

Để kiểm tra giao diện kịch bản với AI giả lập, build frontend rồi chạy từ gốc:

```bash
python3 frontend/scripts/qa_server.py
```

Trong terminal khác:

```bash
cd frontend
npm run test:scripts
```

Server kiểm thử chỉ bind localhost cổng 8123, dùng dữ liệu giả lập, lưu tại
`storage/qa/script-api/`. Bài kiểm tra bao gồm gửi lặp, tải lại khi đang tạo,
từ chối đầu vào, lỗi API, mất kết nối tạm thời, chuyển dự án, đối chiếu JSON
đầy đủ và bố cục 375/768/1440 px. Báo cáo: `storage/qa/script-browser-report.json`.

Kiểm thử preview/render có sẵn cũng dùng server giả lập này để tránh gọi AI thật:

```bash
cd frontend
STUDIO_URL=http://127.0.0.1:8123 npm run test:e2e
```

Bài này render MP4 24 fps/Nháp thật, cần các công cụ render nêu trên. Báo cáo
nằm ở `storage/qa/browser-report.json`. Có thể đặt `CHROME_PATH`, `STUDIO_URL`
và `PYTHON_COMMAND` để thay đường dẫn/lệnh mặc định.
