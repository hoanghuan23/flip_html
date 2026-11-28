# HTML preview → HyperFrames MP4

Nhánh `characer-assembly` giữ giao diện React/TypeScript, backend FastAPI và luồng
xuất video từ preview HTML có sẵn. Bố cục giao diện vẫn giữ nguyên.

Frontend đọc nhóm chủ đề và phong cách từ `config/style_config.json`, mặc định
chọn **Giáo dục & giải trí → Character Cartoon**. Luồng nhập văn
bản → tạo kịch bản đã được chuyển từ `main`, dùng chung logic cho web và CLI.
Luồng tạo ảnh preview → duyệt ảnh → tạo audio và HTML animation đã được khôi phục.
Frontend lưu bản nháp,
nhập tài liệu/ảnh, xem preview đã lưu và theo dõi/tải MP4. Metadata phong cách của
bản nháp cũ được giữ để không làm mất liên kết với preview; các ID không có trong
config không xuất hiện trong lựa chọn mới. Trong `skills/templates/` chỉ còn nguyên bộ asset `character_rig`.
Dữ liệu preview và video đã sinh trong các thư mục local không bị xóa.

## Chạy ứng dụng

Cần Python 3.10+, Node.js 22+, Chrome, FFmpeg/ffprobe để render.

```bash
python3 -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
```

Mở `http://127.0.0.1:8001`. Khi phát triển, chạy `npm run dev` trong `frontend/`;
Vite chuyển `/api` tới backend ở cổng 8001. `VIDEO_STORAGE_DIR` đổi nơi lưu dữ liệu
(mặc định `storage/`). API export sử dụng các preview có `snapshot.json` và ID
32 ký tự hex đã lưu; CLI bên dưới hỗ trợ mọi thư mục/tên preview hợp lệ.

## Từ văn bản đến kịch bản

Trong Studio, nhập văn bản hoặc nạp `.txt`/`.docx`, rồi bấm **Tạo kịch bản**.
Backend phân loại nội dung (`general_script`, `topic`, `detailed_script`,
`legacy`), sinh các cảnh, kiểm tra và sửa JSON khi cần, sau đó lưu
`storage/scripts/<id>/input.txt`, `kich_ban.json`, `job.json` và
`token_usage.json`. Giao diện theo dõi tiến độ và hiển thị các cảnh, lời đọc,
chú giải, cảnh báo và nguồn do model trả về. Nguồn này chưa được hệ thống xác
minh độc lập. Việc tạo kịch bản hoạt động độc lập với lựa chọn phong cách.

Cấu hình dịch vụ văn bản trong `.env` hoặc biến môi trường:

```dotenv
CODEX_API_URL=http://127.0.0.1:8000/generate
CODEX_API_TOKEN=your-api-key
CODEX_MODEL=your-text-model
```

Chạy cùng logic qua CLI:

```bash
python3 plant_kurzge.py --input noi_dung.txt --output storage/kich_ban.json
```

Web gọi `POST /api/scripts` với `{projectId, content}` để tạo tác vụ và
`GET /api/scripts/<id>` để đọc trạng thái/kết quả. API key chỉ dùng ở backend.
Tác vụ chưa hoàn thành khi backend dừng sẽ được đánh dấu lỗi để tạo lại;
kịch bản đã lưu vẫn được giữ. Luồng này kết thúc ở kịch bản JSON, chưa tự động
chọn hoặc ghép nhân vật theo từng cảnh.

Kiểm thử với dịch vụ AI giả lập (không tốn token):

```bash
python3 -m unittest backend.test_scripts backend.test_analysis
cd frontend
npm run build
npm run test:analysis
```

## Tạo audio thuyết minh bằng VieNeu

Module `backend/narration.py` được khôi phục từ `main`, dùng thư viện
`vieneu>=3.8.5,<4` chạy trên máy chủ. Sau khi cài `requirements.txt`, tạo audio
từ kịch bản có `voiceover` bằng CLI:

```bash
python3 generate_audio.py --input storage/scripts/ID_KICH_BAN/kich_ban.json --output storage/narration/ID_KICH_BAN
```

Thay `ID_KICH_BAN` bằng ID tác vụ kịch bản thực tế. Lần chạy đầu, VieNeu cần tải model.
Chọn giọng bằng `VIENEU_VOICE` trong `.env` hoặc biến môi trường; mặc định là
`Hải Đăng`. Lệnh này chỉ tạo giọng đọc, không gọi dịch vụ AI văn bản hoặc ảnh.

Output gồm `assets/audio/*.wav`, metadata JSON và `kich_ban.json` đã gắn
`phase.audio`. Thời lượng cảnh và mốc hoạt ảnh được đồng bộ theo WAV thực tế;
mốc ảnh minh họa được lấy từ ranh giới các đoạn lời đọc. Kịch bản nguồn được giữ
nguyên. Dùng `--overwrite` để tạo lại trong cùng thư mục output.

Cache mặc định là `storage/audio_cache` (hoặc dưới `VIDEO_STORAGE_DIR`), có thể
đổi bằng `--cache`. Cùng lời đọc, giọng và phiên bản VieNeu sẽ dùng lại WAV;
cache lỗi sẽ được tạo lại. Module có thể gọi trực tiếp qua
`prepare_narration(script, output, cache, on_progress)` khi nối lại luồng đồ họa.
Studio tự tạo audio ở bước dựng animation sau khi bạn xác nhận ảnh preview.
CLI trên vẫn dùng được để tạo audio riêng.

Kiểm thử audio dùng model giả và WAV cục bộ, không tải model:

```bash
python3 -m unittest backend.test_narration
```

## Cấu hình nhóm chủ đề và phong cách

Chỉnh `config/style_config.json` để thay đổi lựa chọn ở mục **Nhóm chủ đề &
phong cách đồ họa**:

- `categories`: ID, nhãn hiển thị và `allowed_styles` của từng nhóm chủ đề.
- `styles`: ID, tên, mô tả và đường dẫn tới `SKILL.md` / `style.json` của phong cách.
  Các đường dẫn tính từ thư mục gốc repository; `character-cartoon` trỏ tới
  `skills/styles/character-cartoon/`.
- `default_category`, `default_style`: lựa chọn mặc định; ID phải có trong danh sách
  tương ứng và phong cách phải được nhóm cho phép.

Frontend import trực tiếp file JSON này; chạy lại `npm run build` khi phục vụ
qua FastAPI. Bản nháp trước đây chưa chọn phong cách sẽ nhận giá trị mặc định;
các ID phong cách cũ vẫn được giữ. Config đăng ký lựa chọn và đường dẫn phong cách;
Backend đọc các đường dẫn này để đưa đúng skill và preset vào prompt sinh ảnh
và animation; không dùng cấu hình template hoặc danh mục cũ của `main`.

## Từ kịch bản đến ảnh preview và HTML animation

1. Hoàn tất **Tạo kịch bản** để có JSON đầy đủ trong `storage/scripts/<id>/`.
2. Bấm **Tạo đồ họa**. Backend tạo ảnh tĩnh lần lượt cho từng phase, hiển thị
   dần để xem/phóng to; bước này chưa tạo audio hoặc animation.
3. Duyệt đủ ảnh rồi xác nhận dựng animation. Backend dùng VieNeu tạo WAV từ
   `voiceover`, đo thời lượng và đồng bộ lại timeline, sinh thư viện PNG cùng
   SVG/CSS animation, kiểm tra từng cảnh bằng Chrome và tạo playlist HTML.
4. Xem/tua trong Studio rồi xuất MP4 bằng luồng HyperFrames hiện có.

Luồng giữ đúng các phase đã chốt, dùng lựa chọn hiện tại trong
`config/style_config.json` (mặc định `education_entertainment` / `character-cartoon`).
JSON kịch bản nguồn được giữ nguyên; bản đã đồng bộ audio nằm trong
`storage/previews/<graphics_id>/kich_ban.json`. Ảnh đã duyệt được gửi làm tham
chiếu khi sinh các asset của animation; nhân vật dùng lại cùng PNG hoàn chỉnh.
Đây là các bước AI riêng: ảnh preview là key visual để duyệt, HTML được dựng
từ các asset để có chuyển động và có thể khác cách dàn cảnh tĩnh.

Cấu hình ảnh dùng chung `.env` với dịch vụ văn bản:

```dotenv
IMAGE_API_BASE_URL=http://127.0.0.1:8000/generate-image
IMAGE_API_KEY=your-image-api-key
IMAGE_MODEL=your-image-model
IMAGE_QUALITY=medium
VIENEU_VOICE=Hải Đăng
```

Nếu bỏ các biến ảnh, backend suy ra `/generate-image` từ `CODEX_API_URL` và
dùng `CODEX_API_TOKEN`, `CODEX_MODEL`. `CODEX_IMAGE_API_URL` được hỗ trợ như tên
cũ của URL ảnh. Server ảnh nhận `{prompt, model, reference_images?}` và trả
`{success: true, data: [{b64_json: "..."}]}` với PNG thật. `reference_images`
là các PNG data URL; ghép preset nhân vật cần server hỗ trợ **5 ảnh** tham chiếu.
Mọi ảnh được giữ nguyên byte; backend không tự xóa nền. Sprite phải có alpha
trong suốt thật; ảnh không hợp lệ làm tác vụ báo lỗi để kiểm tra lại.

Các API chính:

- `POST /api/graphics` với `{projectId, scriptId, categoryId, styleId, previewOnly: true}`.
  `POST /api/previews` là alias, nhận cùng payload từ kịch bản đã lưu.
- `GET /api/graphics/<id>` theo dõi tiến độ, ảnh đã có và trạng thái
  `awaiting_confirmation`.
- `POST /api/graphics/<id>/confirm` chỉ bắt đầu animation sau khi đủ ảnh hợp lệ.
- `GET /api/previews/<id>` trả snapshot khi toàn bộ cảnh và audio đã được xác minh.

Tác vụ đang chạy không bị tạo trùng. Khi lỗi, có thể thử lại để dùng cache ảnh,
WAV và các phase hợp lệ; snapshot chưa hoàn thành không được công bố. Khi server
khởi động lại, tác vụ đang chạy được đánh dấu lỗi, ảnh đang chờ duyệt vẫn được giữ.

CLI dùng chung phần dựng HTML và VieNeu, bỏ qua bước duyệt ảnh của Studio:

```bash
python3 generate_kurzge.py --script storage/kich_ban.json --output storage/previews/demo --style character-cartoon
python3 generate_kurzge.py --output storage/previews/demo --resume
```

## Render preview HTML

`render_hyperframes.py` chỉ dùng thư viện chuẩn Python; giữ runtime và audio
đã có trong preview. Cài `npm ci` trong `frontend/` để có GSAP cục bộ.

```bash
python3 render_hyperframes.py --input storage/previews/xeko_muoi --output videos/xeko_muoi.mp4
python3 render_hyperframes.py --input storage/previews/road_trip --output videos/road_trip.mp4 --prepare-only
python3 render_hyperframes.py --input preview/phase_2.html preview/phase_1.html --output videos/selected.mp4
```

Đầu vào là thư mục preview, playlist `index.html` hoặc từng phase HTML có
`window.renderAt(time)`. Script hỗ trợ SVG, PNG/sprite, Three.js và bản đồ đã dựng.
Project HyperFrames mặc định nằm cạnh MP4 với hậu tố `_hyperframes`; project và
MP4 phải nằm ngoài thư mục nguồn. Preview gốc được giữ nguyên.

Mặc định chạy `npx --yes hyperframes@0.9.33` (lần đầu cần mạng). Có thể dùng
`--hyperframes-command hyperframes` nếu đã cài CLI, hoặc đặt `HYPERFRAMES_COMMAND`
cho backend. Script kiểm tra project, chụp giữa cảnh, render và xác minh MP4.
Dùng `--quality draft --fps 24` để thử nhanh, `--overwrite` để ghi đè MP4.

## Thư viện nhân vật AI hoàn chỉnh

`skills/templates/character_rig/GENERATED/` lưu PNG nhân vật hoàn chỉnh do AI
trả về, tách khỏi ảnh đầu, thân, tay và chân nguồn. `config/character_assets.json`
lưu mỗi nhân vật theo ID trong `generated_characters`, gồm đường dẫn ảnh,
SHA-256, kích thước PNG, preset nguồn, thông tin lần tạo và vị trí các khớp.
Nhân vật hoàn chỉnh được tự lưu khi backend sinh asset nhân vật. Backend kiểm
tra thư viện trước khi gọi AI; cùng thiết kế, pose, preset, ảnh nguồn và phong
cách sẽ dùng lại PNG. Các thay đổi những đầu vào này tạo ID cache khác.

Nhập kết quả AI và JSON thông số khớp:

```bash
python3 character_library.py add front_happy_v1 --image ketqua/character.png --metadata ketqua/joints.json
python3 character_library.py list
python3 character_library.py get front_happy_v1
```

Ví dụ **cấu trúc** `joints.json` dưới đây dùng ảnh 1024×1536; cần thay kích thước
và toàn bộ tọa độ bằng số đo thực tế trên PNG được AI trả về:

```json
{
  "preset_id": "front_happy",
  "view": "front",
  "image_size": [1024, 1536],
  "coordinate_space": "image_pixels_top_left",
  "joints": {
    "neck": [512, 600],
    "shoulder_L": [380, 690],
    "shoulder_R": [644, 690],
    "hip_L": [460, 1100],
    "hip_R": [564, 1100]
  },
  "generation": {"provider": "codex", "model": "your-image-model"}
}
```

Tọa độ `[x, y]` tính bằng pixel trên **PNG hoàn chỉnh gốc**: gốc ở góc trên trái,
trục x sang phải, trục y hướng xuống. Không dùng tọa độ của từng ảnh bộ phận hoặc
ảnh preview đã co giãn. Tên `_L`/`_R` theo bên trái/phải của người xem. Có thể
thêm các khớp khuỷu tay, cổ tay, đầu gối và cổ chân theo cùng quy ước.

`GeneratedCharacterLibrary.save(id, png_bytes, metadata)` là điểm lưu kết quả
cho luồng AI sau này. `get_or_create(id, generate)` đọc và kiểm tra ảnh đã lưu
trước; callback AI chỉ chạy khi ID chưa có và phải trả `(png_bytes, metadata)`.
Ảnh và thông số đã lưu dùng được sau khi khởi động lại, không cần ảnh bộ phận
nguồn hoặc dịch vụ AI. Nếu PNG bị sửa/mất, thư viện báo lỗi để kiểm tra lại.

Mỗi ID đại diện cho một bộ biểu cảm, trang phục và tư thế cụ thể. Khi thay đổi,
dùng ID mới hoặc `add ... --overwrite` để cập nhật ảnh cùng thông số khớp.
Ảnh cũ được giữ nguyên; catalog được cập nhật nguyên tử và giữ các phần cấu hình
khác. Backend dùng công cụ này để lưu PNG hoàn chỉnh và tái sử dụng giữa các tác vụ.

Nếu API ảnh trả thêm `character_metadata` (ở cấp response hoặc trong `data[0]`)
theo cấu trúc `joints.json` ở trên, backend tự ghi các tọa độ đó cùng PNG,
với `rig_status: "ready"`. Nếu server chỉ trả PNG, ảnh vẫn được lưu và dùng lại
dưới dạng sprite tĩnh, với `joints: {}`, `rig_status: "pending"`. Trạng thái này
nghĩa là chưa có số đo khớp; backend không tự đặt tọa độ giả. Có thể bổ sung
metadata thực tế bằng lệnh `add ... --overwrite` với cùng ID và cùng PNG đã lưu.

```bash
python3 -m unittest backend.test_character_library backend.test_character_pipeline
```

## Ghép SVG bằng rig (công cụ cũ)

Config mặc định hiện có 5 preset chỉ chọn ảnh bộ phận,
không có transforms hoặc tọa độ rig. Trong `config/character_assets.json`,
`assets` và `rig_profiles` của công cụ ghép cũ hiện để trống; `generated_characters`
dành riêng cho ảnh nhân vật hoàn chỉnh và thông số khớp.
Các lệnh ghép SVG bên dưới chỉ dùng khi cung cấp lại catalog assets và preset
có cấu hình rig tương ứng qua `--assets` và `--presets`. Gallery đã xuất vẫn mở được.
Phần dưới mô tả bộ rig cũ, không phải config mặc định hiện tại.

`assemble_character.py` ghép bộ nhân vật áo đỏ `DEFAULT`, góc chính diện. Chạy:

```bash
python3 assemble_character.py --check
python3 assemble_character.py --gallery --output storage/character_rig/index.html
python3 assemble_character.py --preset front_happy --output storage/character_rig/happy.svg
```

Mở `storage/character_rig/index.html` trực tiếp trong trình duyệt để so sánh 5 preset.
JSON config hiển thị trực tiếp dưới mỗi ảnh, kèm tên preset; không cần bấm mở.
HTML/SVG nhúng ảnh PNG nên không cần server hoặc mạng. Gallery nhúng mỗi PNG một
lần trong thư viện SVG dùng chung; nhân vật hiển thị tĩnh ngay cả khi trình xem
chặn JavaScript. Script chỉ bổ sung kiểm tra tải ảnh: nếu ảnh
lỗi, ô nhân vật báo tên file thay vì hiển thị thiếu bộ phận. Có thể đợi
`window.characterPreviewReady` khi chụp bằng trình duyệt; kết quả `false` cho biết
ít nhất một nhân vật không tải đủ ảnh. Dùng `--overwrite` khi xuất
lại file đã có, `--debug` để hiện các điểm nối và `--list` để liệt kê preset.
Đây là công cụ ghép riêng, chưa nối vào giao diện Studio hoặc API tạo preview.

- `config/character_presets.json`: chọn ảnh đầu, suit, tay trái/phải và chân cho
  từng tư thế. Mỗi preset khai báo đầy đủ `parts`, không kế thừa ngầm.
- `config/character_assets.json`: đăng ký ảnh được hỗ trợ, đường dẫn gốc/hiển thị,
  điểm nối, tâm xoay, tỉ lệ và trang phục tương thích; `rig_profiles` lưu canvas,
  vị trí khớp và thứ tự các lớp từ sau ra trước.

Ví dụ phần chọn ảnh cho nhân vật chính diện, cười mở miệng, hai tay buông:

```json
{
  "view": "front",
  "rig_profile": "front_default",
  "parts": {
    "head": "HEAD/variant_happy_open.png",
    "shoulder_L": "JOINT/DEFAULT/shoulder_L.png",
    "shoulder_R": "JOINT/DEFAULT/shoulder_R.png",
    "suit": "SUIT/DEFAULT/torso_front.png",
    "arm_L": "HAND/07_ARM/down_L.png",
    "arm_R": "HAND/07_ARM/down_R.png",
    "legs_pair": "LEG/01_PAIRS/stand_front.png"
  }
}
```

`SUIT/DEFAULT/torso_front.png` là **suit mặc định và ảnh tham chiếu thiết kế**.
`source` và `reference_source` cùng trỏ tới ảnh này; không phụ thuộc bộ ảnh
`SUIT/DEFAULT` và bản thân áo cũ đã xóa. Bản v2 không có mẩu tay áo ngắn;
`render_source` cũng trỏ tới file này. Các ảnh đầu, tay, chân được giữ nguyên;
tay đã gồm tay áo đỏ và bàn tay, chân đã gồm quần. `generation` lưu công cụ và
profile đã căn. Ảnh v2 có thể dùng làm tham chiếu để tạo biến thể tiếp theo.

Thư mục `skills/templates/character_rig/JOINT/DEFAULT` chứa khớp vai trái/phải
riêng, kèm nguồn SVG và PNG trong suốt. Preset chọn ảnh bằng `shoulder_L` và
`shoulder_R`. `parent_slot` trong config asset gắn mỗi khớp với tay tương ứng:
khớp kế thừa socket, offset, rotation và hệ số scale của tay, rồi áp dụng
`transforms` riêng nếu có. Hai lớp khớp được vẽ phía sau tay và thân áo để lấp
khoảng hở ở vai. Các slot khớp là tùy chọn; khi bỏ khớp khỏi `parts`, cũng bỏ
slot đó khỏi `layer_order`. `--debug` hiển thị tâm xoay tại vị trí đã biến đổi.
Khớp mở một đầu để nối liền tay áo, có tỉ lệ riêng cho tay buông/co/giơ. Khi giơ
tay, khớp quay thêm 180°; `clip_rect: [x, y, width, height]` dùng tọa độ PNG gốc
để ẩn phần viền kín ở gốc tay và mép ảnh thừa. PNG nguồn không bị sửa.

Ảnh suit được tạo bằng công cụ imagegen và căn chỉnh trước; CLI chỉ đọc ảnh đã có,
không tự gọi AI. Khi tạo lại suit hoặc đổi bộ phận/thay tư thế ngoài bộ đã căn,
cần kiểm tra lại tỉ lệ, vai, cổ và hông; cập nhật `render_source` và thông số ghép.
Bộ ảnh đã chốt có thể tái sử dụng mà không sinh lại trong mỗi lần xuất.

`attach_point` và `pivot` dùng tọa độ pixel của `render_source`;
`scale` đổi pixel ảnh sang đơn vị canvas. `sockets` là tọa độ trên canvas chung
360×440. Trong profile này, `L/R` theo tên file và được đặt bên trái/phải của
người xem, không phải quy ước giải phẫu. Mỗi preset có thể ghi đè `layer_order`
hoặc thêm `transforms` cho từng slot với `offset: [x, y]`, `rotation` (độ) và
`scale` (hệ số nhân). Ví dụ `front_raise` xoay tay quanh khớp vai.

Hiện có 45 asset đã đăng ký, bao gồm toàn bộ 35 ảnh trong `HEAD`: 34 head chính
diện và `back.png` có `view: back`. Có thể đổi `parts.head` sang bất kỳ head chính
diện nào rồi xuất lại gallery; `back.png` cần rig và suit cùng góc quay lưng.
Các lựa chọn trong 5 preset hiện tại được giữ nguyên. Các ảnh tay/chân/trang phục
khác ngoài danh mục vẫn cần đăng ký/căn chỉnh. Khi thêm ảnh hoặc bộ đồ mới, cần khai báo đúng slot,
góc nhìn, `compatible_suits`, điểm nối và tỉ lệ trước khi dùng trong preset.
Chân có thể dùng `legs_pair` hoặc cả `leg_L` và `leg_R` nếu profile có đủ sockets;
không dùng đồng thời hai kiểu. Bộ kiểm tra báo lỗi khi thiếu ảnh, sai bên tay,
trộn trang phục/góc nhìn hoặc khai báo lớp trùng.

## Kiểm thử

```bash
python3 -m unittest discover -s backend -p 'test_*.py' -v
cd frontend
npm test
npm run build
npm run test:exports
npm run test:characters
```

Test trình duyệt dùng fixture preview và giả lập job render; cần backend đang chạy tại `http://127.0.0.1:8001`, hoặc đặt
`STUDIO_URL`. `CHROME_PATH` đổi đường dẫn Chrome (mặc định `/usr/bin/google-chrome`).
Riêng `test:characters` tự xuất gallery vào thư mục tạm, không cần backend;
kiểm tra ảnh đầu neutral đã được vẽ sau khi cuộn xuống và tình huống ảnh head bị lỗi.
