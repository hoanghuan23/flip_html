## Giao diện tạo video và xuất MP4

Giao diện React + TypeScript và API FastAPI mới nằm trong `frontend/` và
`backend/`. Có nhập TXT/DOCX, AI sinh kịch bản đầy đủ, chọn phong cách và tạo
PNG/HTML animation thật để xem, phát/dừng và tua. Mục 3 xuất toàn bộ phase
thành MP4, theo dõi tiến trình, xem video và tải file. Các nút sửa/xóa/chat/tạo lại
phase hiện chưa cho thao tác. Xem [hướng dẫn cài đặt, chạy và kiểm thử](frontend/README.md).

Đầu vào có phần **“Mô tả:” / “Thuyết minh:”** hỗ trợ giọng đọc ElevenLabs,
giữ nguyên lời người dùng và đồng bộ thời lượng cảnh theo audio thực tế.
Phong cách **3D Motion Infographic** dùng mesh Three.js, camera và ảnh tham
chiếu đánh số trong khung thông tin; preview và MP4 có cùng giọng đọc.
Xem cấu hình và cách sử dụng trong [hướng dẫn frontend](frontend/README.md).

Web và CLI dùng chung phân loại `general_script` / `topic` / `detailed_script` / `legacy`.
Kịch bản tổng quát (case 1) có bối cảnh, diễn biến/các bước và kết quả mong muốn:
AI tự chia cảnh, viết `voiceover` tiếng Việt cho mỗi cảnh và ước tính thời lượng
theo lời đọc, hoạt ảnh, chú giải. `narration` chỉ là ghi chú ngắn, không thay lời đọc.
Chủ đề được nghiên cứu rồi viết lời đọc và hoạt ảnh; kịch bản đã chia phase giữ
nguyên số cảnh, thứ tự, tên và audio. JSON bổ sung chú giải riêng, nguồn/cảnh báo
và thời lượng dự kiến. Chỉ nhận văn bản; ảnh trong bản nháp không gửi qua API.
Xem mẫu input và hợp đồng dữ liệu trong [phân tích văn bản](frontend/README.md#phân-tích-văn-bản-chủ-đề-kịch-bản-chi-tiết-và-input-cũ).

Kịch bản và đồ họa chạy qua tác vụ nền riêng. Mục 2 hiển thị ảnh tĩnh từng phase
ngay khi AI sinh xong; bấm ảnh để xem lớn. Khi đủ ảnh, bấm **Xác nhận và tạo hoàn chỉnh**
để bắt đầu tạo audio/animation ở mục 3. Snapshot animation chỉ công bố khi đủ mọi
phase. Phong cách đã chọn được đưa vào cả sinh ảnh và diễn hoạt. CLI Python bên
dưới giữ cách sử dụng hiện có; thêm `--style <id>` để chỉ định phong cách.

Luồng kịch bản → AI phân tích → Scene Plan → PNG nền/sprite sheet → JavaScript sprite animation → HTML Preview được giữ trong **2 file**:

- `analyze_text.py`: sinh và in kịch bản AI. Sửa `NOI_DUNG` hoặc dùng `--input noi_dung.txt`.
- `generate_preview.py`: đọc kịch bản đã lưu, phân tích timeline, gọi `codex_server` sinh PNG và dựng HTML. Cần Pillow để kiểm tra, chuẩn hóa và ghép PNG; `--plan-only` chỉ cần thư viện chuẩn.

Luồng chính dùng `plant_kurzge.py`, `generate_kurzge.py` và `image_motion_ai.py`:
API `generate_image` (`/generate-image`) vẽ thư viện PNG, SVG/CSS dàn cảnh và diễn hoạt. AI tự chọn số phase, thời lượng từng phase và
`total_duration` theo nội dung và chuyển động. Không còn `--duration`, thời lượng
mặc định hoặc giới hạn chữ theo tốc độ đọc. Trong kịch bản cũ không có `voiceover`,
`narration` là chữ giải thích ngắn trên màn hình. Kịch bản có `voiceover` được
chốt lại thời lượng sau TTS ở luồng web. Tổng duration phải khớp `total_duration`,
và mọi action phải nằm trong phase tương ứng.

Prompt sinh kịch bản yêu cầu AI lập mốc diễn biến trước rồi mới chọn duration,
tính thời gian đọc chữ song song với chuyển động và chỉ giữ kết quả thêm một
nhịp ngắn khi cần. AI tự rà khoảng chờ trước, giữa và sau actions; hiệu ứng lặp
không mang thông tin mới không được dùng để kéo dài phase. Quy tắc này áp dụng
khi sinh kịch bản mới; các JSON và preview đã lưu giữ thời lượng cũ.

Prompt chung phân trách nhiệm theo ba bước. Kịch bản xác định nhận diện từng
đối tượng, tỷ lệ không gian, điểm tựa/điểm nối và tác động cần nhìn thấy trong
các trường hiện có. Prompt ảnh nhận cùng mô tả thiết kế, pose gốc, toàn bộ bộ
pose và bối cảnh các asset để giữ màu từng bộ phận, cấu tạo, số lượng và tỷ lệ.
Prompt dàn cảnh kiểm tra silhouette trên cả đường đi, điểm tiếp xúc và vùng
chữ; dựng hiệu ứng hành động có nguồn/đích và thời điểm bật/tắt, kể cả khi cần
lớp SVG phụ cạnh PNG. Các quy tắc áp dụng cho mọi chủ đề, không cố định trang
phục, màu, nhân vật hay tỷ lệ của một video mẫu.

Các pose PNG hiện được gọi sinh riêng; pose gốc trong prompt là mô tả văn bản,
không phải ảnh tham chiếu được gửi kèm API. Prompt giúp hướng dẫn sự nhất quán,
chưa bảo đảm các ảnh sẽ khớp hoàn toàn; vẫn cần xem ảnh ở đầu/giữa/cuối cảnh,
lúc đổi pose và lúc tương tác. Kiểm tra kỹ thuật không thay thế việc xem hình.

Xuất các preview đã có thành video bằng **`render_hyperframes.py`** (một file,
chỉ dùng thư viện chuẩn Python). Đầu vào là thư mục preview, `index.html` của
playlist hoặc từng phase HTML; hỗ trợ cả SVG `phase_N.html` và PNG/sprite
`phase_N/index.html`. Nhiều đầu vào được ghép đúng thứ tự truyền vào:

```bash
# Xuất toàn bộ phase của một preview:
python3 render_hyperframes.py --input preview_samset --output videos/samset.mp4
# Ghép nhiều preview thành một video:
python3 render_hyperframes.py --input preview_samset preview_conbao --output videos/tong_hop.mp4
# Chỉ chọn các phase cần xuất, theo thứ tự mong muốn:
python3 render_hyperframes.py --input preview_samset/phase_2.html preview_samset/phase_4.html --output videos/chon_loc.mp4
# Chỉ tạo project HTML để xem/sửa trước, chưa cần công cụ render:
python3 render_hyperframes.py --input preview_samset --output videos/samset.mp4 --prepare-only
```

Render cần **Node.js >=22, Chrome và FFmpeg/ffprobe**. Mặc định script chạy
`npx --yes hyperframes@0.9.33` (lần đầu cần mạng để tải CLI). Có thể cài một lần
bằng `npm install -g hyperframes@0.9.33` rồi thêm
`--hyperframes-command hyperframes`. Script không cần khóa API AI.

Project được giữ ở `videos/samset_hyperframes/`, gồm `index.html`,
`compositions/`, bản sao asset/runtime và `preview_manifest.json` ghi nguồn,
thứ tự và thời lượng. Dùng `--project-dir` để chọn nơi khác; project và MP4 phải
nằm ngoài thư mục preview đầu vào. Có thể mở để chỉnh trong HyperFrames desktop app
hoặc chạy `npx hyperframes@0.9.33 preview videos/samset_hyperframes`.

Script kiểm tra project, lưu ảnh các điểm giữa cảnh, render rồi xác nhận thời
lượng MP4 bằng ffprobe. Mặc định 30 fps, chất lượng `delivery`; có thể dùng
`--quality draft --fps 15` để thử nhanh. Dùng `--overwrite` nếu MP4 đã tồn tại.
Phase thiếu hoặc không có `renderAt(time)` sẽ báo lỗi, không âm thầm bỏ cảnh.
Video giữ animation và chữ đã có trong SVG, chỉ lấy vùng stage của PNG/sprite,
không đưa nút điều khiển vào video, giữ audio đã có trong metadata và không sửa
preview gốc. Kích thước canvas lấy từ cảnh đầu tiên (PNG mặc định 1920×1080).
Các cảnh được nối bằng cut; không sinh lại hình hoặc thay đổi kịch bản.

Chạy từ nội dung đến preview bằng một lệnh (cần API văn bản):

```bash
python3 generate_kurzge.py --input noi_dung.txt --output preview_moi
# Kịch bản được lưu ngay vào preview_moi/kich_ban.json để tiếp tục khi cần:
python3 generate_kurzge.py --resume --output preview_moi
# Hoặc chỉ sinh JSON trước; bỏ --input để dùng NOI_DUNG trong plant_kurzge.py:
python3 plant_kurzge.py --input noi_dung.txt --output kich_ban_moi.json
python3 generate_kurzge.py --script kich_ban_moi.json --output preview_khac
```

Lệnh chạy giữ nguyên, mặc định sinh ảnh cho **toàn bộ phase**:

```bash
python3 generate_kurzge.py --script conbao_hinhthanh.json --output preview_conbao_hinhthanh
```

`--renderer auto` và `--renderer ai` đều dùng cùng luồng chính qua `/generate-image`
cho toàn bộ phase. Nền, nhân vật, đồ vật,
ký hiệu và từng pose được sinh thành PNG riêng. API nhận đúng `prompt`, `model`
và header `x-api-key`, dùng cấu hình `IMAGE_API_*`/`IMAGE_MODEL` (hoặc cấu hình
Codex hiện có). Cần Pillow để kiểm tra PNG và alpha thật của asset nền trong suốt.
Không tự xóa nền, không chuyển sang vẽ SVG khi API ảnh lỗi.

Ảnh gốc lưu trong `assets/`, cache theo prompt/model/cấu hình tại `image_cache/`.
`assets.svg` ghép thư viện PNG bằng data URI để mở HTML trực tiếp, kể cả trong
iframe sandbox. AI văn bản chỉ dàn cảnh bằng `<use>` và CSS animation; không nhận
base64 ảnh và không vẽ lại chủ thể. Các pose dùng chung kích thước, gốc local và
được crossfade tại mốc morph. Vị trí, camera, thời lượng và `branch_from` lấy từ JSON;
diễn hoạt dùng toàn bộ canvas, không chèn dải phụ đề hoặc tiêu đề/lời dẫn phía dưới.
`caption` và `narration` được giữ trong dữ liệu kịch bản để tham khảo, không tự
hiển thị trong cảnh hoặc dưới trình phát. Nhãn ngắn gắn với đối tượng vẫn có thể
xuất hiện khi nội dung yêu cầu; giọng thuyết minh tiếp tục phát nếu có audio.

`assets.meta.json` và fingerprint trên từng phase kiểm tra cache theo kịch bản,
thư viện và phiên bản renderer. Lặp lại cùng lệnh với cùng JSON trong output sẽ
tự tiếp tục: preview SVG cũ được dựng lại bằng thư viện ảnh mới, phase hợp lệ được
giữ lại. Output chứa kịch bản khác vẫn được bảo vệ. Đổi caption không gọi lại API
ảnh. Prompt ảnh và dàn cảnh được lưu trong `prompts/`.

Ví dụ đầu vào khác chủ đề nằm ở `examples/ball_conveyor.txt`:

```bash
python3 generate_kurzge.py --input examples/ball_conveyor.txt --output preview_bang_chuyen
```

```bash
python3 generate_kurzge.py --script kich_ban_moi.json --output preview_ai
# Mở preview_ai/index.html; tiếp tục từ JSON đã lưu, dùng cache hợp lệ:
python3 generate_kurzge.py --resume --output preview_ai
# Có thể chỉ dựng một phase:
python3 generate_kurzge.py --resume --output preview_ai --phase 2
```

Sinh preview mới cần API ảnh và API văn bản; sau khi sinh, preview chạy offline. SVG dùng CSS animation,
có thể mở từng `phase_N.html` hoặc dùng trình phát với Play/Pause và thanh tua.
`--resume` dùng kịch bản đã lưu, không gọi lại bước phân tích. Renderer AI dùng
cache hợp lệ.
`--plan-only` xuất prompt ảnh cho mọi asset/pose và prompt dàn cảnh, không gọi API. Font dùng Be Vietnam Pro nếu máy
có sẵn, nếu không dùng system-ui; preview không tải font mạng.

```bash
python3 -m pip install -r requirements.txt
python3 analyze_text.py --output kich_ban.md
python3 generate_preview.py --script kich_ban.md --plan-only
```

Kết quả phân tích nằm ở `preview/kich_ban.md`, `scene_plan.json` và `image_prompts.json`.
AI giữ nội dung, số phase, thứ tự và thời lượng kịch bản. Kế hoạch được kiểm tra timeline,
pose, socket, chu trình track cha/con và trạng thái nối phase; nếu sai, AI sửa một lần.
`image_prompts.json` lưu prompt ảnh, kích thước sheet, lưới, thứ tự pose và điểm neo.

Adapter được viết theo `../codex_server/server.py`: `GenerateRequest`, `GenerateImageRequest` và `generate_image()`.
API văn bản `/generate` và API ảnh `/generate-image` là hai route riêng, cùng nhận JSON
`{"prompt":"...","model":"..."}` và header `x-api-key`. Không gửi thêm trường vì server dùng
`extra="forbid"`. `request_text()` chỉ dùng cho kịch bản và Scene Plan, không dùng để vẽ ảnh.

Cấu hình `.env` theo `.env.example`, giữ nguyên token hiện có:

```dotenv
CODEX_API_URL=http://127.0.0.1:8000/generate
CODEX_API_TOKEN=your-codex-server-token
CODEX_MODEL=gpt-5.6-luna
IMAGE_API_BASE_URL=http://127.0.0.1:8000/generate-image
IMAGE_API_KEY=your-codex-server-token
IMAGE_MODEL=gpt-5.6-luna
IMAGE_QUALITY=medium
IMAGE_BACKGROUND_SIZE=1536x1024
```

`IMAGE_API_BASE_URL` là **URL endpoint đầy đủ**, được gọi nguyên trạng; chương trình không nối
`/images/generations` hay `/images/edits`. `IMAGE_API_KEY` là token xác thực của `codex_server`,
không phải OpenAI API key. `IMAGE_MODEL` là model **Codex CLI**, truyền nguyên giá trị cho server;
không có danh sách bắt buộc model `gpt-image-*`, không tự đổi model và không gọi trực tiếp OpenAI Images API.
Thiếu cấu hình ảnh thì dừng trước khi gọi AI, không quay lại SVG.

Server chạy Codex CLI đã đăng nhập với `image_generation` và trả
`{"success":true,"result":"data:image/png;base64,...","mime_type":"image/png","session_id":"..."}`.
Client nhận PNG/JPEG/WebP/GIF bitmap, chuẩn hóa thành PNG rồi kiểm tra dữ liệu thực; sprite phải có alpha.
Client chờ tối đa 660 giây cho mỗi ảnh. Lỗi API được báo cùng HTTP status; dùng `--resume` để tiếp tục.

Server hiện **chưa có input ảnh tham chiếu, tham số size/quality/background hoặc edit API**.
Kích thước, độ chi tiết và nền trong suốt chỉ được yêu cầu trong prompt, rồi kiểm tra sau khi nhận ảnh.
`IMAGE_QUALITY` là hướng dẫn trong prompt; `IMAGE_BACKGROUND_SIZE` là kích thước nền đề nghị.
`IMAGE_SPRITE_SIZE` cũ không dùng: kích thước sprite sheet lấy từ `asset.size` trong Scene Plan.
Model ảnh nội bộ do công cụ của Codex chọn, không được server trả về; metadata chỉ xác định được model CLI.

Chạy **Phase 1 trước**:

```bash
python3 generate_preview.py --resume --phase 1
# Xem ảnh/sheet, tua Phase 1 và hiệu chỉnh điểm cầm; sau đó mới chạy các phase còn lại:
python3 generate_preview.py --resume
# Dựng lại HTML từ cache PNG, không gọi API và không cần IMAGE_API_KEY:
python3 generate_preview.py --resume --html-only --phase 1
```

`--phase 1` chỉ sinh nền và asset Phase 1 dùng. Mỗi nhân vật sinh **một sprite sheet** chứa đầy đủ
pose cho mọi phase, để các pose được tạo trong cùng một ảnh và tái sử dụng nguyên sheet giữa các phase.
Client không giả vờ gửi ảnh tham chiếu vào endpoint chỉ nhận text. Nếu API không sinh đúng lưới/alpha,
chương trình từ chối dùng ảnh, lưu PNG nguồn để xem và báo lỗi; không tự chuyển sang SVG hoặc âm thầm
sinh các pose độc lập rồi khẳng định cùng ngoại hình. Nếu cần chuyển sang sinh từng pose với ảnh tham chiếu,
server cần bổ sung hợp đồng nhận ảnh trước; chương trình này không sửa server.

Python kiểm tra lưới PNG nguồn, cắt từng ô và ghép lại theo thứ tự `poses` từ trái sang phải, trên xuống dưới.
Mỗi ô dùng cùng hệ số resize theo canvas; không phóng lớn riêng tư thế cúi. Nội dung được dịch về trục giữa
và điểm chân/đáy `anchor`, giữ nguyên tỷ lệ ảnh. Nguồn có thể có kích thước và tỷ lệ khác sheet cuối;
ranh giới ô được làm tròn theo lưới và từng pose được kiểm tra riêng. Nền được resize/crop theo tâm để khớp kích thước plan.

Trước khi dùng asset: giải mã PNG tĩnh, kiểm tra kích thước, alpha thực, frame không rỗng,
nội dung không chạm biên ở sheet cuối, số ô, kích thước ô, thứ tự chỉ số pose, điểm chân/đáy và ô thừa trong suốt.
Pixel alpha dưới 8/255 được coi là nhiễu gần vô hình khi xác định biên và kiểm tra ô thừa trong PNG nguồn;
chuẩn hóa loại nhiễu này, giữ alpha của phần còn lại. Ô thừa trong sheet cuối luôn hoàn toàn trong suốt.
**Các kiểm tra kỹ thuật không chứng minh chất lượng đồ họa.** Chương trình chưa nhận diện được đúng pose,
cùng tỷ lệ cơ thể, ngoại hình/màu sắc, bàn tay hay việc nền không lẫn nhân vật/vật thể tách riêng.
Tên pose được gán theo vị trí ô yêu cầu; cần xem ảnh để xác nhận AI thật sự vẽ đúng thứ tự đó.
Tua trực tiếp các mốc nhặt/mở/khép/đi bộ. Metadata ghi `visual_review: required`; HTML cũng nêu giới hạn.

Mỗi `phase_N` giữ `index.html`, `style.css`, `script.js`, `window.renderAt(time)`, Play/Pause,
thanh tua, timeline và keyframes. `width` là % chiều rộng stage; chiều cao theo tỷ lệ ô ảnh.
`anchor: [0.5, 0.94]` trên asset là điểm chân/đáy chuẩn hóa trong frame; x/y của track đặt điểm đó lên stage.
`scale`, `rotation`, `flip` điều khiển toàn sprite; thay đổi hình dáng phải dùng pose PNG thật.
Có thể hiệu chỉnh kích thước/vị trí trình bày bằng `track.layout`, ví dụ `{"width":34,"offset":[3.9,-10.8]}` (width và offset theo % stage). Các mốc x/y, pose, time gốc được giữ nguyên; hiệu chỉnh này không làm mất cache ảnh.

Vật cầm gắn theo socket từng pose của nhân vật. Ví dụ phần bổ sung vào asset cô bé
(phải có tọa độ cho tất cả pose thực tế):

```json
{"anchor": [0.5, 0.94], "sockets": {"hand": {
  "stand": [0.65, 0.5], "walk_1": [0.66, 0.52], "walk_2": [0.64, 0.51]
}}}
```

Trên keyframe chiếc ô lúc cầm:

```json
{"time": 4.2, "x": 30, "y": 56, "pose": "open",
 "attach": {"track": "girl", "socket": "hand", "anchor": [0.5, 0.8], "offset": [0, 0]}}
```

`attach.anchor` là điểm cầm trên frame vật thể, có thể khác theo pose đóng/mở. Socket và anchor dùng tọa độ
0–1 trong frame PNG cuối; `offset` theo kích thước frame cha. Vật theo vị trí socket cùng biến đổi
xoay/lật/tỷ lệ và opacity của cha. Khi cùng track/socket, anchor/offset được nội suy; khi đổi attachment, vị trí được nối tới đúng điểm cầm
ở keyframe đích để tránh nhảy tại lúc nhặt/thả. `attach: null` khi ô còn trên đất; x/y chỉ có tác dụng khi không attach.
Đặt thời điểm gắn/tháo và điểm cầm khớp ảnh để tránh nhảy vị trí.
Để hiệu chỉnh trên PNG đã có, có thể đặt cùng cấu trúc `sockets` trên track nhân vật. `track.sockets` ghi đè socket của asset, không đổi prompt/cache ảnh; giữ cùng cấu hình giữa các phase.
Plan cũ vẫn đọc được và giữ timeline, **không tự suy ra socket/attach** từ tên vật; cần bổ sung trường
vào plan cũ sau khi đối chiếu PNG. Đồ vật cố định dùng `scene_bound: true`, được vắng mặt khi đổi nền.
Nhân vật/vật cầm đã ra hoàn toàn ngoài khung ở cuối phase được đặt lại x/y khi chuyển sang nền khác;
pose, attachment và ngoại hình vẫn phải liên tục. Nếu còn trong khung hoặc giữ cùng nền thì không được đổi vị trí.

Cache dùng `id.png`, `id.png.meta.json`; PNG nguồn giữ trong `assets/<kind>/.source/`.
Ảnh nguồn bị từ chối vẫn giữ để xem, nhưng không có metadata hợp lệ nên không được dùng lại.
Fingerprint gồm phiên bản pipeline, URL, model CLI, cấu hình/prompt, style, asset/lưới/thứ tự pose/anchor/socket
và cách chuẩn hóa; không lưu khóa API. Metadata chứa SHA-256 file và từng frame cuối.
Resume chỉ dùng file khi fingerprint, hash, metadata và PNG thực tế đều khớp.
Sheet cuối hỏng có thể ghép lại từ PNG nguồn còn hợp lệ; asset đã hoàn tất không bị sinh lại.
`--html-only` từ chối cache sai/thiếu. SVG và metadata cũ được giữ nguyên, không dùng làm cache PNG.

Dùng `--output thu_muc_khac` để thử nghiệm riêng và truyền cùng `--output` khi resume.
Mở `preview/index.html` trên trình duyệt. Xuất MP4 là bước riêng bằng
`render_hyperframes.py` sau khi đã xem và chốt preview.

Phase 2 đã hiệu chỉnh theo `bug_phase2.md`: cô bé vào từ mép trái, mèo chờ sát bồn cây,
bạn nhỏ đứng sẵn dưới mái hiên rồi bước sang phải để nhập nhóm. Tán ô nằm sau nhân vật;
socket tay cầm và điểm neo được hiệu chỉnh để thấy rõ mặt. Khi đi, cô bé luân phiên
hai dáng bước với dáng chân khép đã có trong sheet; các mốc đường đi liên tiếp giữ
nhịp đổi frame, không khởi động lại từ ảnh đầu. Đoạn 19–21 giây dùng chu kỳ bước
thay cho ảnh đứng mời. Cả nhóm và ô khuất hoàn toàn sang phải trước giây 25;
Phase 3 đặt lại vị trí trên nền mới sau khi đã ra hết khung.
Plan trước sửa giữ ở `preview/scene_plan.before_phase2_bugs.json` và
`preview/scene_plan.before_phase2_walk_exit.json`.
Nền sửa bằng công cụ `image_gen` tích hợp, lưu tại `preview/assets/backgrounds/school_road_rain.png`;
prompt thực tế nằm trong `school_road_rain.phase2.prompt.txt` cùng thư mục, metadata ghi provenance.
Dùng `python3 generate_preview.py --resume --html-only` để dựng lại từ plan và PNG đã sửa.

Kiểm tra offline (PNG fixture và mock theo hợp đồng codex_server):

```bash
python3 -m unittest discover -s tests -v
```

Luồng mới: **kịch bản → plan có dàn cảnh → sinh PNG → đo PNG/hiệu chỉnh → kiểm tra
hình học → HTML và ảnh đối chiếu**. Plan mới thiếu hợp đồng dàn cảnh bị trả lại AI
sửa trước khi gọi API ảnh. Plan cũ vẫn đọc được, nhưng preview ghi rõ chưa hiệu chỉnh
nếu chưa có `staging` và `geometry`.

Mỗi phase có `staging` xác định `shot`, góc nhìn `view`, chuyển cảnh `cut/continuous`,
`pixels_per_meter`, đa giác mặt đất `ground`, tâm camera `focus` và các mốc `camera.zoom`.
Mỗi track có `geometry` khai báo `reference_pose`, trục đo `width/height`, `size_m`,
vùng tiếp đất, góc sprite hỗ trợ, các `baked_poses` đã vẽ nghiêng/ngã,
`motion: constant/free` và `exit: left/right` nếu phải ra hết khung.
Một camera cut được bố trí lại tọa độ/tỷ lệ/lớp; cảnh continuous phải giữ nền và hệ
tọa độ, nối zoom. Camera lùi biến đổi chung cả nền và mọi sprite, không đổi sang nền khác.
Pose đã vẽ ngã không được xoay thêm. Chuyển động constant bị từ chối nếu vận tốc các đoạn khác nhau.
`role` kiểm tra khoảng kích thước người lớn/ô tô/xe máy; `forward` và
`locomotion_poses` kiểm tra hướng bước so với đường đi, tránh đi lùi ngoài ý định.

Sau khi có ảnh, chương trình đọc alpha PNG thật, đo phần hình nhìn thấy ở reference_pose
và tính `layout.width` từ kích thước mét × tỷ lệ chung của shot. Không kéo riêng mỗi pose
cho vừa ô. `scene_plan.json` giữ plan được soạn; `scene_plan.calibrated.json` là plan thực
sự được nhúng vào HTML. `layout_report.json` lưu SHA-256 đầu vào, số đo, trạng thái và lỗi;
`layout_review/phase_N/` chứa ảnh ghép các mốc, dùng cùng phép biến đổi với JavaScript.
Kiểm tra điểm tiếp đất tại keyframes và mỗi khoảng 0,1 giây; kiểm tra toàn bộ khung của
sprite/attachment khi phải ra khỏi cảnh. Có lỗi thì dừng, giữ HTML cũ để tránh ghi đè
bằng kết quả sai; xem lỗi và ảnh trong báo cáo.

Vùng mặt đất AI dự kiến **không được coi là đã đo đúng theo ảnh**. Sau khi đối chiếu PNG
nền, lưu `layout_calibration.json` dạng:

```json
{"version":1,"backgrounds":{"street":{
  "sha256":"SHA-256 đầy đủ của PNG nền đã xem",
  "view":"side",
  "ground":{"road":[[0,79],[100,79],[100,100],[0,100]]}
}}}
```

Thiếu dữ liệu đo nền thì vẫn có bản nháp và ảnh đối chiếu, trạng thái
`needs_background_review`; không báo là đã kiểm tra hình ảnh. Nền đổi SHA-256 thì dữ liệu
đo cũ bị từ chối. **Bước này kiểm tra hình học, không tự nhận diện mặt đường bằng AI,
không xác minh giải phẫu hoặc việc AI vẽ đúng tên pose.** Giới hạn này hiển thị trong preview.

Bộ giao thông `preview_1/` đã áp dụng bước đo và sửa đủ bốn phase. Phase 1 giữ tư thế
ngồi gắn yên, xe chạy đều `x = -12 + 26t`, đèn vàng từ giây 2 và xe ra hết khung trước
giây 4,75. Phase 2–4 dùng chung nền `bg_accident` và camera ngang phù hợp với sprite
hiện có, thay cho nền overhead không khớp góc xe/người. Hiện trường và hai người hỗ trợ
được bố trí riêng trên đường; xe đã vẽ đổ không xoay thêm. Phase 4 lùi camera ở giây 6–7.
Plan trước sửa giữ ở `preview_1/scene_plan.before_staging_fixes.json`.
Nền chung Phase 2–4 đã thay bằng mặt đường thông suốt hai mép, vỉa hè ở phía xa;
prompt thực tế ở `preview_1/assets/backgrounds/bg_accident.road_open.prompt.txt`.
Ảnh được tạo bằng công cụ `image_gen`, metadata ghi provenance riêng và SHA-256 mới;
giữ nguyên sprite người/xe. Xe máy vào ngang ở y=76%, ô tô vào từ x=124%, y=65%
rồi tiến xuống vùng va chạm. Bản nền/plan trước thay giữ ở
`preview_1/review/background_before_road_open/`. Báo cáo trình duyệt và ảnh desktop/mobile
ở `preview_1/review/staging/`.

```bash
python3 generate_preview.py --resume --html-only --output preview_1
```

Các lệnh dự án video có sẵn:

```bash
cd mario_animation_video
npm run render

npx hyperframes preview

npx hyperframes init <tên-dự-án>

npm run ai:generate: chỉ cập nhật cấu hình từ prompt, chưa render.
npm run render: render bằng cấu hình hiện có, không đọc prompt mới.
npm run ai:render: cập nhật cấu hình mới từ prompt và render
```
