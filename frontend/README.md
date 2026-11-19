# AI Video Studio

Frontend React + TypeScript cho pipeline video Python. Giao diện có ba bước:
nhập nội dung và xem kịch bản, chọn phong cách và xem HTML animation.
Sau khi chọn **Tạo kịch bản**, danh sách cảnh hiển thị ngay trong mục 1.

Kịch bản được AI phân tích thật qua `plant_kurzge.py`: kiểm tra đầu vào, sinh
JSON chi tiết, kiểm tra và yêu cầu sửa nếu cần. Bảng chỉ trích tên, chữ giải
thích, mô tả hình ảnh và thời lượng từng phase. Hiện chỉ hỗ trợ xem kịch bản;
các nút sửa/thêm/xóa/chat được khóa.

Mục 2 dùng JSON đầy đủ của bước 1 để sinh thư viện PNG và SVG/CSS animation.
Phong cách được chọn đi vào cả prompt sinh ảnh và prompt diễn hoạt. Mục 3 cho
chọn phase, phát/dừng và tua; sửa/xóa/chat/tạo lại phase chỉ hiển thị ở trạng
thái khóa. Tạo hoặc thử lại đồ họa ở mục 2. Video không có âm thanh.

Bấm **Xuất video** ở mục 3, chọn tên file, FPS (24/30/60) và chất lượng rồi
bấm **Bắt đầu xuất**. Toàn bộ phase của preview được ghép theo thứ tự thành
một MP4, giữ hình ảnh, chữ và thời lượng. Có trạng thái xử lý, tiến độ khi CLI
cung cấp, xem MP4 và **Tải MP4** khi hoàn tất. Tải lại trang hoặc chuyển dự án
vẫn tiếp tục theo dõi đúng tác vụ. Mất kết nối tạm thời tự thử lại; lỗi xuất
cho phép thử lại. Khi kịch bản/phong cách thay đổi, cập nhật đồ họa trước khi xuất.

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
Sinh đồ họa còn cần API ảnh `/generate-image`. Mặc định suy ra URL từ máy chủ
CODEX và dùng chung token/model; có thể đặt riêng:

```dotenv
IMAGE_API_BASE_URL=https://your-ai-service.example/generate-image
IMAGE_API_KEY=your-image-token
IMAGE_MODEL=your-image-model
IMAGE_QUALITY=medium
```

API ảnh nhận `{prompt, model}` với `x-api-key`, trả PNG base64 trong
`{success: true, data: [{b64_json: "..."}]}`. Không tự chuyển sang đồ họa mẫu
khi thiếu cấu hình hoặc API ảnh lỗi. Khởi động lại backend sau khi đổi cấu hình.
Lưu file React/CSS hoặc `skills/style_config.json` để Vite tự cập nhật giao
diện. Không cần build lại khi phát triển. Cổng 8000 phục vụ bản build trong
`frontend/dist`, nên cần `npm run build` sau khi sửa giao diện ở chế độ đó.

## Luồng tạo đồ họa

1. Nhập nội dung hoặc tải TXT/DOCX, chọn **Tạo kịch bản** và đọc bảng ở mục 1.
2. Chọn danh mục/phong cách ở mục 2 rồi bấm **Tạo đồ họa**.
3. Theo dõi các giai đoạn chuẩn bị, sinh ảnh, dựng từng phase và kiểm tra.
   Chỉ thay preview khi hoàn tất toàn bộ phase; lỗi giữa chừng vẫn giữ bản cũ.
4. Ở mục 3, chọn phase, phát/dừng và tua để xem HTML animation thật.
   Các nút chỉnh sửa, tạo lại và xuất video hiện chưa cho thao tác.
5. Đổi phong cách hoặc tạo kịch bản mới sẽ đánh dấu preview cũ cần cập nhật.
   Bấm **Tạo đồ họa** ở mục 2 để dựng bản mới.

Canvas 1920×1080, không âm thanh. Giữ nguyên phase/actions và thời lượng từ
kịch bản; không gọi lại AI phân tích nội dung khi tạo đồ họa. Danh sách cảnh
trên trình duyệt không được dùng thay cho JSON đầy đủ.

Kịch bản, đồ họa và xuất MP4 có hàng đợi riêng. Tác vụ kịch bản/đồ họa chạy
trong tiến trình có thể dừng khi backend tắt, dùng thời gian chờ API hiện có.
Khởi động lại backend đánh dấu tác vụ dang dở là lỗi; bấm tạo lại để tiếp tục.
Gửi lặp trong lúc đang chạy trả cùng ID. Thử lại đồ họa lỗi với cùng đầu vào
dùng thư mục/cache đã kiểm tra; bấm tạo sau khi thành công tạo một bản riêng.

Các API xuất MP4 hiện có vẫn được giữ cho giai đoạn sau, chưa được gọi từ giao diện.

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
mặc định. Renderer đọc `skills/<styleId>/SKILL.md` và `style.json` nếu có.
Thiếu hướng dẫn hoặc cấu hình không hợp lệ sẽ báo lỗi, không dùng Flat thay thế.
Phong cách quyết định cách vẽ và palette; đối tượng/camera/actions/thời lượng
lấy từ kịch bản. Không đưa chủ đề, số vật thể hoặc trang trí trong demo vào video.
Bản demo là tài liệu xem phong cách, không được chuyển trực tiếp thành animation.

Thẻ chọn phong cách chỉ hiển thị tên và chú thích. Khung mẫu lớn hiển thị
`skills/<styleId>/demo/index.html`, ví dụ `skills/flat/demo/index.html`,
trong iframe có thể cuộn để xem toàn bộ nội dung dài. Các demo hiện tại dùng
CSS và SVG nhúng trực tiếp trong HTML. Nếu chưa có file, khung để trống.
HTML được backend đọc trực tiếp; sau khi thêm hoặc thay demo, tải lại trang
hoặc chuyển phong cách để cập nhật, không cần build lại frontend.
Flat là phong cách riêng, được phép trong các danh mục có Outlined cartoon.

## Dữ liệu và khôi phục

- Bản nháp tự lưu sau 500 ms trong localStorage, khóa `ai-video-studio:v1`.
  ID tác vụ kịch bản/đồ họa đang chạy được lưu ngay để khôi phục khi tải lại.
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
- `storage/graphics/<id>/job.json` giữ trạng thái và tiến độ tác vụ đồ họa;
  `worker.log` giữ thông tin tiến trình.
- `storage/previews/<id>/` giữ bản sao `kich_ban.json`, `render_config.json`
  (snapshot hướng dẫn/preset phong cách), `assets/`, `image_cache/`, `prompts/`,
  `assets.svg`, SVG/HTML từng phase, playlist `index.html` và `render.log`.
  `snapshot.json` chỉ được công bố sau khi đủ mọi phase đúng thứ tự/thời lượng.
  Trước đó, GET preview/HTML trả 404; người dùng tiếp tục xem bản cũ.
  JSON gốc bước 1 giữ nguyên. Đổi nội dung phong cách hoặc cấu hình API ảnh
  làm cache tương ứng bị vô hiệu; không dùng nhầm ảnh của phong cách trước.
- `storage/exports/<id>/` giữ `job.json`, `render.log`, `video.mp4` và project
  HyperFrames. Các thư mục này không được Git theo dõi và không tự xóa.
- Mỗi tác vụ đồ họa gắn với kịch bản và phong cách bất biến. Trong dự án đang
  dựng, khóa nhập nội dung/chọn phong cách. Vẫn cho chuyển dự án; kết quả cập nhật
  đúng dự án và tải lại trang sẽ tiếp tục theo dõi `graphicsJobId`.
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
| `POST /api/graphics` | `{projectId, scriptId, categoryId, styleId}` → tác vụ PNG/HTML nền, HTTP 202 |
| `GET /api/graphics/{id}` | Trạng thái, `stage`, `completed/total`, lỗi hoặc snapshot hoàn chỉnh trong `result` |
| `POST /api/previews` | API tạo template cũ, giữ tương thích; giao diện mới không gọi API này |
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
python3 -m unittest backend.test_api backend.test_scripts backend.test_graphics -v
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

Để kiểm tra luồng đồ họa bằng worker thật và API văn bản/ảnh giả lập trên server trên:

```bash
cd frontend
npm run test:graphics
# test:e2e chạy cùng bài kiểm tra giao diện đồ họa hiện tại
```

Bài kiểm tra xác nhận PNG được nhúng trong HTML, tua tái hiện cùng trạng thái,
đúng phong cách, không hiện phase dở dang, giữ preview cũ khi lỗi, dùng cache
khi thử lại, khôi phục sau tải lại/chuyển dự án và bố cục 375/768/1440 px.
Báo cáo: `storage/qa/graphics-browser-report.json`. Không gọi dịch vụ AI thật.
Có thể đặt `CHROME_PATH` và `STUDIO_URL` để thay đường dẫn/cổng mặc định.

Kiểm thử xuất MP4 qua trình duyệt trên cùng server QA:

```bash
cd frontend
npm run test:exports
```

Bài kiểm tra dùng preview ngắn để render MP4 thật, kiểm tra cấu hình, chống
gửi lặp, tải lại/chuyển dự án, mất kết nối, lỗi/thử lại và tải MP4 hỗ trợ Range.
Báo cáo: `storage/qa/exports-browser-report.json`.

CLI giữ cách dùng cũ; để chọn phong cách rõ ràng:

```bash
python3 generate_kurzge.py --script kich_ban.json --style halftone-line --output preview_halftone
python3 generate_kurzge.py --resume --output preview_halftone
```

`--resume` giữ snapshot phong cách đã lưu; truyền `--style` để đọc phiên bản
phong cách hiện tại. Cache sẽ được kiểm tra lại theo nội dung phong cách.
