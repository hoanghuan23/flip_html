# AI Video Studio

Frontend React + TypeScript cho pipeline video Python. Giao diện có ba bước:
nhập nội dung và xem kịch bản, chọn phong cách và duyệt ảnh tĩnh, xem HTML animation.
Sau khi chọn **Tạo kịch bản**, danh sách cảnh hiển thị ngay trong mục 1.

Kịch bản được AI phân tích thật qua `plant_kurzge.py`: kiểm tra đầu vào, sinh
JSON chi tiết, kiểm tra và yêu cầu sửa nếu cần. Bảng trích tên, lời đọc, mô tả,
chú giải và thời lượng từng phase; nguồn/cảnh báo có thể thu gọn. Hiện chỉ hỗ trợ xem kịch bản;
các nút sửa/thêm/xóa/chat được khóa.

Mục 2 dùng JSON đầy đủ của bước 1 để sinh ảnh tĩnh từng phase cho người dùng duyệt.
Sau **Xác nhận và tạo hoàn chỉnh**, backend mới tạo thư viện PNG và SVG/CSS animation.
HTML animation không chèn dải phụ đề phía dưới; chữ giải thích vẫn nằm trong
bảng kịch bản. Chỉ các nhãn ngắn theo nội dung được đặt trong cảnh.
Phong cách được chọn đi vào cả prompt sinh ảnh và prompt diễn hoạt. Mục 3 cho
chọn phase, phát/dừng và tua; sửa/xóa/chat/tạo lại phase chỉ hiển thị ở trạng
thái khóa. Tạo hoặc thử lại đồ họa ở mục 2. Nội dung có phần “Thuyết minh:”
được chuyển thành giọng đọc; nội dung cũ tiếp tục chạy không âm thanh.

## Phân tích văn bản: chủ đề, kịch bản chi tiết và input cũ

Web và CLI dùng chung `plant_kurzge.generate_script()`; không có bộ chọn loại.
`general_script` dành cho kịch bản tổng quát (case 1): bối cảnh, diễn biến/các bước
xử lý và kết quả mong muốn, chưa mô tả chi tiết từng phase hoặc có lời đọc riêng.
Ví dụ hướng dẫn phòng cháy chữa cháy và thoát hiểm chung cư có các mục `## 1. ...`.
AI bám sát nội dung, tự chia phase và viết `voiceover` tiếng Việt hoàn chỉnh cho
từng phase; `narration` chỉ là ghi chú ngắn riêng. Nhánh này không có bước nghiên
cứu bổ sung (`research.status=not_required`). Thiếu hoặc rỗng `voiceover` sẽ yêu cầu
AI sửa trước khi lưu `kich_ban.json`. Cần tạo lại kịch bản để áp dụng cho job đã lưu.

`topic` nghiên cứu câu hỏi như “Mưa đá hình thành như thế nào?”, rồi tự viết
phase, hoạt ảnh, `voiceover` và chú giải. Nghiên cứu dùng endpoint văn bản hiện có.
`research.status=sources_reported` chỉ có nghĩa AI cung cấp nguồn hỗ trợ, chưa
được hệ thống xác minh độc lập; `unverified` là bản nháp chưa kiểm chứng bằng web.
Không tra cứu được vẫn cho phép dùng kiến thức phổ thông đủ chắc, kèm cảnh báo;
thiếu dữ kiện cốt lõi thì yêu cầu bổ sung, không tự bịa.

`detailed_script` (case 2) nhận cấu trúc rõ với các tiêu đề Phase/Cảnh/Phần đánh số;
từng phase cần một mục hình ảnh và một mục lời đọc. Tên mục có thể thay đổi:

- Hình ảnh: `Hoạt ảnh:`, `Diễn biến:`, `Mô tả:`.
- Lời đọc: `Audio:`, `Thuyết minh:`, `Lời đọc:`, `Lời bình:`, `Voiceover:`.

Chấp nhận tên ghép cùng nhóm như `Audio - Thuyết minh:` hoặc `Hoạt ảnh / Diễn biến:`,
không phân biệt hoa thường; hỗ trợ khoảng trắng, tiêu đề Markdown và chữ đậm.
Tên mục nằm đầu dòng và kết thúc bằng dấu hai chấm. Ví dụ:

```text
## Phase 1: Giới thiệu
Hoạt ảnh: Vệ tinh chuyển động phía trên Trái Đất; nhãn độ cao ở cạnh vệ tinh.
Audio: Vệ tinh này hoạt động ở độ cao khoảng 550 km.

## Cảnh 2: So sánh
Diễn biến: Camera lùi để thấy Trái Đất và hai quỹ đạo.
Audio - Thuyết minh: Quỹ đạo thấp nằm gần bề mặt Trái Đất hơn quỹ đạo địa tĩnh.
```

Hệ thống giữ số phase, thứ tự, tên đã đặt và nguyên văn audio (kể cả xuống dòng),
chỉ bổ sung chi tiết dựng cảnh. Thiếu phần hoạt ảnh/audio hoặc ranh giới không rõ
thì yêu cầu sửa input. Không tự chia phase quá dài; tối đa 100 phase, 120 giây/phase,
30 phút/video và 10.000 ký tự audio/phase. Luồng `legacy` tiếp tục giữ nguyên lời
đọc trong Mô tả/Thuyết minh chưa chia phase. Bài viết, bản tin hoặc câu chuyện
chưa có lời đọc riêng chuyển sang `general_script`, kể cả khi AI phân loại `legacy`.
Phản hồi phân loại cũ không có `input_type` vẫn giữ luồng tương thích trước đây.

Chú giải lưu riêng trong `annotations`: `text`, `target` (asset ID), `action_index`
(tùy chọn, đếm từ 0), `cue` (tùy chọn, cụm lời đọc để canh thời điểm). Cue khác
chữ hoa/thường hoặc khoảng trắng được khớp lại với audio gốc; cue không khớp
được bỏ qua, giữ timeline hoạt ảnh thay vì chặn kịch bản. Danh sách
có thể rỗng. Đợt này chuẩn hóa và hiển thị để duyệt; chưa ép renderer vẽ đủ mọi chú giải.
`input_type`, `research`, `warnings` nằm ở cấp kịch bản, đồng thời có trong
`job.json.result`; mỗi cảnh mới có `duration_status=estimated`. Bản nháp cũ vẫn đọc được.

Thời lượng dự kiến lấy lớn nhất giữa lời đọc, timeline hoạt ảnh và thời gian đọc
chú giải. Tốc độ mặc định 210 cụm cách nhau bởi khoảng trắng/phút, có cộng nghỉ
theo dấu câu; cấu hình qua `SCRIPT_SPEECH_UNITS_PER_MINUTE` (số dương hữu hạn).
Sau TTS, pipeline hiện tại tiếp tục dùng thời lượng audio thực tế. CLI chỉ xuất JSON,
không tự tạo audio. Lỗi JSON/nội dung sinh được yêu cầu sửa tối đa hai lần.

Ảnh tải lên được lưu nguyên bản trên backend và truyền mã ảnh cùng loại ảnh khi
tạo kịch bản. Mã `@image_N` trong Hoạt ảnh yêu cầu ảnh tương ứng đã tải lên;
ảnh minh họa được hiện hoặc thay theo cụm lời đọc chỉ định.

Kiểm thử phân tích: `python3 -m unittest backend.test_analysis -v`.
Kiểm thử giao diện độc lập với AI: sau `npm run build`, chạy `npm run test:analysis`
trong `frontend/`; báo cáo và ảnh màn hình lưu tại `storage/qa/analysis-*`.

## Thuyết minh và 3D Motion Infographic

Nhập chung một ô, ví dụ:

```text
Vệ tinh Starlink trong không gian
Mô tả:
Trái Đất ở dưới trái, vệ tinh chuyển động chậm. Camera tiến gần rồi lùi ra.
Hiện dòng chữ "Quỹ đạo thấp – khoảng 550 km" ở góc phải.

Thuyết minh:
Đây là một vệ tinh Starlink đang hoạt động ngoài không gian...
```

Ảnh tham chiếu và ảnh minh họa được tải lên backend; bản nháp chỉ giữ ảnh thu nhỏ
để xem lại giao diện. Bấm **Tạo kịch bản**, chọn phong cách, rồi **Tạo đồ họa**.
Duyệt đủ ảnh tĩnh rồi bấm **Xác nhận và tạo hoàn chỉnh** để dựng cảnh 3D và audio.

Backend giữ nguyên lời thuyết minh khi chia cảnh. VieNeu tạo audio WAV trước
khi dựng đồ họa; `ffprobe` đo thời lượng, làm tròn lên ở 30 FPS. Thời lượng
trong kịch bản là ước tính cho đến khi có snapshot; sau đó cả bảng cảnh, player
và MP4 dùng thời lượng thực tế. Player chờ WebGL và audio sẵn sàng, đồng bộ
phát/dừng/tua theo audio. Lỗi audio không tạo ra snapshot thiếu giọng đọc.

VieNeu dùng `Vieneu()`, `infer(text=..., voice=...)` và `save(...)` như
`test_tts.py`. Cài bằng `python3 -m pip install -r requirements.txt`; lần chạy
đầu cần tải model nếu chưa có trong cache. Model được khởi tạo một lần cho
mỗi worker và dùng chung cho các cảnh. Không cần khóa API TTS.

Tùy chọn giọng trong `.env` ở gốc, chỉ đọc ở backend:

```dotenv
# Mặc định giống test_tts.py:
VIENEU_VOICE=Hải Đăng
```

Audio và metadata được cache trong `storage/audio_cache/` theo nội dung,
giọng và phiên bản VieNeu. Đổi style/ảnh hoặc thử lại tác vụ không gọi lại TTS
cho audio đã hoàn tất. Cache WAV tách biệt với audio MP3 cũ; preview MP3 đã
lưu vẫn phát được. Tác vụ báo lỗi thiếu thư viện, tải model, tạo hoặc lưu audio.

API waveform của VieNeu không trả mốc thời gian từng ký tự/từ;
`alignment` trong metadata là `null`. Mốc action được co giãn theo thời lượng
audio thực tế; kế hoạch 3D dùng giây cụ thể thay cho cue theo lời đọc.

Style mới dùng Three.js với kế hoạch JSON được kiểm tra: mesh, vật liệu,
camera, track chuyển động và lớp ảnh/chữ. Mỗi frame được dựng từ `renderAt(t)`;
runtime, font và texture được đóng gói cục bộ, chạy trong iframe sandbox.
Chỉ các nhãn ngắn xuất hiện trên hình; không tự tạo phụ đề từ lời đọc.

`npm run build` cũng dựng bundle Three.js. Sau khi sửa nguồn runtime hoặc
style, tạo lại mẫu bằng `python3 skills/styles/3d-motion-infographic/scripts/build_demo.py`
từ thư mục gốc. Texture Trái Đất có thông tin nguồn trong `assets/sources.json`
của style. Scene hỗ trợ group/box/sphere/plane/cylinder/cone/torus/stars;
chủ thể phức tạp được ghép từ nhiều mesh, không có bước sinh mô hình GLB tự động.

MP4 dùng audio từng cảnh ở timeline gốc HyperFrames, không phát lặp audio
trong iframe. Export kiểm tra cả H.264/video, luồng audio và thời lượng.

Bấm **Xuất video** ở mục 3, chọn tên file, FPS (24/30/60) và chất lượng rồi
bấm **Bắt đầu xuất**. Toàn bộ phase của preview được ghép theo thứ tự thành
một MP4, giữ hình ảnh, chữ và thời lượng. Có trạng thái xử lý, tiến độ khi CLI
cung cấp, xem MP4 và **Tải MP4** khi hoàn tất. Tải lại trang hoặc chuyển dự án
vẫn tiếp tục theo dõi đúng tác vụ. Mất kết nối tạm thời tự thử lại; lỗi xuất
cho phép thử lại. Khi kịch bản/phong cách thay đổi, cập nhật đồ họa trước khi xuất.

## Chạy ứng dụng

Cần Python 3.12 để cài VieNeu 3.8.5 trên Windows, Node.js 22+,
Chrome/Chromium và FFmpeg (bao gồm ffprobe) nếu xuất MP4.
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
Lưu file React/CSS hoặc `config/style_config.json` để Vite tự cập nhật giao
diện. Không cần build lại khi phát triển. Cổng 8000 phục vụ bản build trong
`frontend/dist`, nên cần `npm run build` sau khi sửa giao diện ở chế độ đó.

## Luồng tạo đồ họa

1. Nhập nội dung hoặc tải TXT/DOCX, chọn **Tạo kịch bản** và đọc bảng ở mục 1.
2. Chọn danh mục/phong cách ở mục 2 rồi bấm **Tạo đồ họa**.
3. Xem dải **Preview các phase** ngay trong mục 2: AI sinh một ảnh tĩnh minh họa
   bố cục/phong cách cho từng phase, phase nào xong hiện ngay phase đó. Bấm ảnh
   thu nhỏ để xem lớn; đóng bằng nút Đóng, phím Escape hoặc bấm ngoài hộp thoại.
   Lượt này chưa tạo thuyết minh, animation hoặc snapshot ở mục 3.
4. Khi đủ ảnh, nút đổi thành **Xác nhận và tạo hoàn chỉnh**. Bấm để bắt đầu tạo
   audio, asset và HTML animation theo kịch bản/phong cách đã chọn. Ảnh duyệt là
   hình minh họa riêng; API ảnh hiện chỉ nhận prompt văn bản nên ảnh này không
   được gửi làm ảnh tham chiếu cho lượt tạo asset animation. Chỉ thay snapshot
   ở mục 3 khi toàn bộ animation hoàn tất; lỗi vẫn giữ snapshot cũ và ảnh đã tạo.
   Ở mục 3, chọn phase, phát/dừng và tua để xem animation, rồi xuất MP4.
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

Mục 2 hiển thị “Nhóm chủ đề”, lấy tên trực tiếp từ `categories.*.label` trong
`config/style_config.json`. Mỗi nhóm khai báo các template trong `templates`,
mỗi template có danh sách `allowed_styles`. “Tất cả phong cách” giữ đầy đủ
danh sách phong cách hiện có. Nhóm trống không
hiển thị mẫu và không cho tạo đồ họa; chọn “Tất cả phong cách” để tiếp tục.
Mỗi nhóm hiển thị hợp các danh sách `templates.*.allowed_styles`, theo thứ tự
khai báo và bỏ ID trùng lặp; nếu phong cách đang chọn không còn được phép, ứng dụng tự
chuyển sang phong cách hợp lệ (ưu tiên `default_style`). Nhóm trống giữ lại
phong cách đã chọn để dùng khi chuyển nhóm. Lựa chọn nhóm chủ đề
được lưu cùng bản nháp. Các preset cũ vẫn được đọc và chuyển đổi khi mở lại.
Cấu hình được frontend import trực tiếp từ file JSON. Khi chạy `npm run dev`,
Vite tự cập nhật sau khi lưu file; bản production cần build lại. Giữ nguyên
ID danh mục khi đổi tên để các bản nháp tiếp tục sử dụng danh mục đó.
Thêm ID vào `templates.<templateId>.allowed_styles` sẽ tự hiện lựa chọn và đọc
`skills/styles/<styleId>/demo/index.html`; không cần
thêm ID vào danh sách cố định trong frontend. Flat with black và Halftone line
có tên, chú thích và bảng màu riêng. ID khác dùng tên suy ra từ ID và chú thích
mặc định. Renderer đọc `skills/styles/<styleId>/SKILL.md` và `style.json` nếu có.
Thiếu hướng dẫn hoặc cấu hình không hợp lệ sẽ báo lỗi, không dùng Flat thay thế.
Phong cách quyết định cách vẽ và palette; đối tượng/camera/actions/thời lượng
lấy từ kịch bản. Không đưa chủ đề, số vật thể hoặc trang trí trong demo vào video.
Bản demo là tài liệu xem phong cách, không được chuyển trực tiếp thành animation.

Thẻ chọn phong cách chỉ hiển thị tên và chú thích. Khung mẫu lớn hiển thị
`skills/styles/<styleId>/demo/index.html`, ví dụ `skills/styles/flat/demo/index.html`,
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
- Vùng **Thêm hình ảnh tham khảo** bên dưới ô nhập hỗ trợ chọn nhiều ảnh hoặc
  kéo thả JPG/PNG/WEBP, không giới hạn số lượng, tối đa 5 MB/ảnh; có ảnh thu nhỏ và xóa riêng
  từng ảnh. Ảnh được thu nhỏ tối đa 1280 px, nén WEBP tối đa 256 KB để lưu cùng
  từng bản nháp trong trình duyệt và khôi phục khi tải lại/chuyển dự án.
  Mỗi ảnh có nhãn **Hình 1**, **Hình 2**… để nhắc đến trong văn bản đầu vào.
  Số được lưu cùng ảnh; xóa ảnh không đổi số các ảnh còn lại và không dùng lại
  số đã xóa, tránh nhầm ảnh được nhắc đến trong nội dung.
  API tạo kịch bản hiện chỉ nhận văn bản; ảnh tham khảo chưa gửi cho AI.
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
  `worker.log` giữ thông tin tiến trình. `awaiting_confirmation` là trạng thái đã
  đủ ảnh tĩnh, đang chờ xác nhận; trạng thái này được giữ khi backend khởi động lại.
  Lượt sinh ảnh lỗi có thể thử lại với cache đã kiểm tra. Lượt animation lỗi có
  thể bấm **Xác nhận và tạo hoàn chỉnh** để tiếp tục cùng tác vụ.
- `storage/previews/<id>/` giữ bản sao `kich_ban.json`, `render_config.json`
  (snapshot hướng dẫn/preset phong cách), `assets/`, `image_cache/`, `prompts/`,
  `assets.svg`, SVG/HTML từng phase, playlist `index.html` và `render.log`.
  `snapshot.json` chỉ được công bố sau khi đủ mọi phase đúng thứ tự/thời lượng.
  Trước đó, GET preview/HTML trả 404; người dùng tiếp tục xem animation cũ.
  Ảnh tĩnh ở `phase_N.preview.png`, danh sách/hash ở `stills.json`, cache ở
  `still_cache/` và prompt ở `prompts/phase_N_still.txt`; endpoint ảnh tĩnh riêng
  phục vụ từng phase đã hoàn tất mà không công bố snapshot dở dang.
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
| `POST /api/graphics` | `{projectId, scriptId, categoryId, styleId, previewOnly: true}` → tác vụ ảnh tĩnh nền, HTTP 202; bỏ `previewOnly` giữ API animation cũ |
| `GET /api/graphics/{id}` | Trạng thái, `stage`, `completed/total`, `previews` đã xong, `confirmed`, lỗi hoặc snapshot hoàn chỉnh trong `result` |
| `GET /api/graphics/{id}/previews/phase_N.png` | PNG tĩnh của phase đã hoàn tất, kể cả khi các phase khác đang sinh |
| `POST /api/graphics/{id}/confirm` | Kiểm tra đủ ảnh/hash, xác nhận và xếp hàng tạo audio/animation; gửi lặp trả cùng tác vụ |
| `POST /api/previews` | API tạo template cũ, giữ tương thích; giao diện mới không gọi API này |
| `GET /api/previews/{id}` | Kiểm tra snapshot còn tồn tại |
| `GET /api/previews/{id}/phase_N.html` | HTML phase kiểm soát sẵn, có `renderAt(time)` |
| `GET /api/previews/{id}/assets/{path}` | Audio, runtime, font hoặc ảnh trong snapshot đã công bố |
| `GET /api/styles/{styleId}/preview` | URL demo HTML, hoặc `null` nếu chưa có file |
| `GET /api/styles/{styleId}/demo/index.html` | Trang demo HTML của phong cách |
| `POST /api/exports` | `{snapshotId, config: {filename, fps, quality}}` → tác vụ, HTTP 202 |
| `GET /api/exports/{id}` | Trạng thái, giai đoạn, tiến độ nếu CLI cung cấp, lỗi/kết quả |
| `GET /api/exports/{id}/video` | MP4 inline, hỗ trợ Range |
| `GET /api/exports/{id}/download` | Cùng MP4, Content-Disposition attachment |

Schema tương tác ở **http://127.0.0.1:8000/docs**. Không dùng JSON bản nháp
frontend trực tiếp làm `kich_ban.json` của pipeline AI: bản nháp chỉ chứa dữ liệu
giao diện. Dùng file `storage/scripts/<id>/kich_ban.json` cho pipeline AI chi tiết.

Ảnh tham chiếu và ảnh minh họa được gửi qua `POST /api/images`, rồi liên kết bằng
`imageId` trong `POST /api/scripts`. Ảnh gốc được sao vào tác vụ kịch bản và
preview khi cần. Snapshot có renderer
`three-motion-v1` hoặc renderer ảnh hiện có; phase có thể có
`audio: {url, duration}`. `voiceover` là lời đọc, tách khỏi `narration` cũ.

## Kiểm thử

```bash
python3 -m unittest discover -s backend -p 'test_*.py' -v
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

Bài kiểm tra xác nhận ảnh tĩnh xuất hiện lần lượt, phóng to/đóng ảnh, giữ trạng
thái chờ xác nhận sau tải lại và không tạo animation trước khi xác nhận. PNG
animation được nhúng trong HTML, tua tái hiện cùng trạng thái, đúng phong cách,
không công bố animation dở dang, giữ preview cũ khi lỗi, dùng cache
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

Kiểm tra player 3D/audio độc lập, không gọi API trả phí (audio là tín hiệu thử):

```bash
# Từ gốc dự án; build frontend trước:
python3 frontend/scripts/narrated-qa.py
VIDEO_STORAGE_DIR=storage/qa/narrated python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8134
# Terminal khác:
cd frontend
npm run test:narrated
```

Bài kiểm tra bao gồm phát/dừng/tua, đổi phase, tua ngược tái hiện cùng frame,
ảnh tham chiếu số 7 trong sandbox và tải lại không tự phát tiếng. Có thể dùng
`NARRATED_PROJECT=/đường/dẫn/project.json` để kiểm tra snapshot có audio thật.
Fixture 3D/audio nằm riêng trong `storage/qa/narrated/`, không ghi vào preview
của dự án thực. Có thể xóa toàn bộ `storage/qa/` sau khi kiểm thử; lần chạy sau
sẽ tạo lại các file cần thiết.

CLI giữ cách dùng cũ; để chọn phong cách rõ ràng:

```bash
python3 generate_kurzge.py --script kich_ban.json --style halftone-line --output preview_halftone
python3 generate_kurzge.py --resume --output preview_halftone
```

`--resume` giữ snapshot phong cách đã lưu; truyền `--style` để đọc phiên bản
phong cách hiện tại. Cache sẽ được kiểm tra lại theo nội dung phong cách.
