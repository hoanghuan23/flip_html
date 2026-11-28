# HTML preview → HyperFrames MP4

Nhánh `characer-assembly` giữ giao diện React/TypeScript, backend FastAPI và luồng
xuất video từ preview HTML có sẵn. Bố cục giao diện vẫn giữ nguyên.

Frontend hiện không cấu hình danh mục và phong cách. Luồng nhập văn
bản → tạo kịch bản đã được chuyển từ `main`, dùng chung logic cho web và CLI.
API đồ họa và preview mới vẫn trả thông báo chưa có cấu hình. Frontend lưu bản nháp,
nhập tài liệu/ảnh, xem preview đã lưu và theo dõi/tải MP4. Metadata phong cách của
bản nháp cũ được giữ để không làm mất liên kết với preview; không xuất hiện trong
lựa chọn mới. Trong `skills/templates/` chỉ còn nguyên bộ asset `character_rig`.
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
minh độc lập. Việc tạo kịch bản hoạt động khi danh mục phong cách đang trống.

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

## Ghép SVG bằng rig (công cụ cũ)

Config mặc định hiện có 5 preset chỉ chọn ảnh bộ phận,
không có transforms hoặc tọa độ rig. `config/character_assets.json` để trống (`{}`).
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
