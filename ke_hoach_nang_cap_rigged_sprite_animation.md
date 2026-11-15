# Kế hoạch nâng cấp `generate_preview.py`: Hoạt hình 2D vector với nhân vật tách bộ phận

## 1. Mục tiêu

Chuyển pipeline **kịch bản → kế hoạch → sinh PNG → HTML animation** hiện tại sang hệ thống **rigged / cut-out 2D animation**: nhân vật được tạo từ các lớp **đầu, thân, cánh tay trên, cẳng tay, bàn tay, đùi, cẳng chân, bàn chân**, có thể bổ sung mắt, miệng, tóc và phụ kiện. Mỗi lớp có pivot, thứ tự vẽ và animation curve riêng. Phong cách hình ảnh hướng đến hoạt hình giải thích khoa học: **flat vector 2D, hình học bo tròn, màu rực rỡ, gradient có kiểm soát, silhouette rõ, ít texture**, không sao chép thiết kế riêng của một studio.

**Phạm vi:** tài liệu thiết kế và hướng dẫn sửa chương trình; **chưa phải mã đã tích hợp hoặc đã chạy kiểm thử**. Giữ pipeline PNG và HTML, không bắt buộc SVG, MP4 hay engine bên ngoài. Có thể bổ sung chế độ sprite-sheet cũ để tương thích.

## 2. Hiện trạng xác nhận trong file nguồn

- `PLAN_PROMPT` (đầu file) yêu cầu JSON `assets`, `phases`, `tracks`, `keyframes`, `staging`, `geometry`; `style` hiện là chuỗi tự do.
- `validate_plan()` xác thực assets dạng `backgrounds`, `characters`, `objects`; các character hiện có `columns`, `rows`, `poses`, `anchor`, `sockets`.
- `image_prompt()`, `sheet_prompt()`, `request_image()`, `generate_assets()` sinh ảnh PNG qua endpoint `/generate-image`; request hiện chỉ gửi `model` và `prompt`, **chưa hỗ trợ ảnh tham chiếu**.
- `normalize_pose()` và `png_info()` kiểm tra alpha, lưới và điểm neo; chưa kiểm tra khớp xương, độ giống nhau giữa các pose.
- `STYLE` và `JAVASCRIPT` dựng mỗi track thành một `.sprite` dùng `background-position`; `actorState()` nội suy transform, hỗ trợ `attach` qua socket; `renderAt()` dùng thời gian để dựng trạng thái; có camera zoom và thời tiết.
- `layout_state()`, `layout_calibration.json`, báo cáo layout và review still cần được giữ lại và mở rộng cho rig.

**Hệ quả:** không nên chỉ thêm prompt “tách tay chân”. Cần thay đổi **schema dữ liệu, sinh asset, kiểm tra, tính toán biến đổi phân cấp, renderer HTML và kiểm tra layout** đồng bộ.

## 3. Kiến trúc đề xuất

```text
Kịch bản
  ↓
PLAN_PROMPT + ART_DIRECTION + CHARACTER_BIBLE
  ↓
plan.json (phases + tracks + rig definitions + motion clips)
  ↓
Character master PNG (mẫu thiết kế chuẩn)
  ↓
Part generation: head / torso / arms / legs / eyes / mouth ...
  ↓
Validate alpha + dimensions + pivots + seams + appearance
  ↓
Atlas PNG + rig.json + motion clips
  ↓
HTML scene renderer (hierarchical transforms, timeline, attachments)
  ↓
Preview + review still + layout report
```

**Chiến lược an toàn:** hỗ trợ song song `render_mode: "sheet"` (cũ) và `render_mode: "rig"` (mới). Nền, vật thể, phương tiện và các hiệu ứng đơn giản có thể tiếp tục dùng sprite sheet.

## 4. Quy chuẩn mỹ thuật cố định

Thêm gần `PLAN_PROMPT`:

```python
ART_DIRECTION = """
Premium 2D flat vector educational cartoon.
Clean geometric silhouettes, rounded shapes, simplified anatomy.
Vibrant controlled palette: navy, turquoise, cyan, coral,
orange, magenta, purple, warm yellow.
Strong warm/cool contrast; smooth limited gradients;
soft rim light and restrained atmospheric glow.
Consistent proportions, line weight, lighting and camera view.
Separate foreground, midground and background layers.
NO photorealism, 3D render, anime, watercolor, sketch texture,
heavy random outlines, baked shadows, text or watermarks.
Rig parts must share identical character identity and scale.
"""
```

**Sửa `analyze_script()`**: nối `ART_DIRECTION` vào prompt ở **cả lần đầu lẫn lần retry JSON**. Không để trường `plan.style` tùy ý ghi đè quy chuẩn; nên phân thành `global_style` cố định và `scene_style` mô tả khác biệt theo cảnh. Trong `image_prompt()` và prompt sinh bộ phận phải luôn sử dụng cùng art direction và character bible.

**Character bible** nên lưu: `character_id`, tỷ lệ đầu/thân, chiều cao tham chiếu, màu da/tóc/mắt, trang phục, phụ kiện, góc nhìn chuẩn, ánh sáng chuẩn, palette HEX và hình master. Một lần thay bible phải làm mất hiệu lực cache các bộ phận liên quan.

## 5. Schema mới: rig phân cấp

Ví dụ **minh họa**, không phải JSON mà `validate_plan()` hiện tại đã chấp nhận:

```json
{
  "id": "girl",
  "kind": "characters",
  "render_mode": "rig",
  "reference_view": "side",
  "reference_height_m": 1.45,
  "master_image": "assets/characters/girl/master.png",
  "parts": [
    {"id":"torso", "parent":null, "file":"girl/torso.png", "pivot":[0.5,0.52], "offset":[0,0], "z":10},
    {"id":"head", "parent":"torso", "file":"girl/head.png", "pivot":[0.5,0.86], "offset":[0,-0.35], "z":20},
    {"id":"upper_arm_l", "parent":"torso", "file":"girl/upper_arm_l.png", "pivot":[0.5,0.12], "offset":[-0.22,-0.25], "z":9},
    {"id":"forearm_l", "parent":"upper_arm_l", "file":"girl/forearm_l.png", "pivot":[0.5,0.1], "offset":[0,0.75], "z":9},
    {"id":"hand_l", "parent":"forearm_l", "file":"girl/hand_l.png", "pivot":[0.5,0.12], "offset":[0,0.85], "z":9},
    {"id":"thigh_l", "parent":"torso", "file":"girl/thigh_l.png", "pivot":[0.5,0.12], "offset":[-0.13,0.38], "z":8},
    {"id":"shin_l", "parent":"thigh_l", "file":"girl/shin_l.png", "pivot":[0.5,0.1], "offset":[0,0.85], "z":8},
    {"id":"foot_l", "parent":"shin_l", "file":"girl/foot_l.png", "pivot":[0.2,0.5], "offset":[0,0.9], "z":8}
  ],
  "sockets": {"hand_l":{"part":"hand_l", "point":[0.7,0.5]}},
  "clips": {
    "idle": {"duration":1.5,"loop":true,"channels":{"head.rotation":[[0,-2],[0.75,2],[1.5,-2]]}},
    "walk": {"duration":0.8,"loop":true,"channels":{"thigh_l.rotation":[[0,25],[0.4,-25],[0.8,25]],"thigh_r.rotation":[[0,-25],[0.4,25],[0.8,-25]]}}
  }
}
```

**Bắt buộc bổ sung phần đối xứng bên phải** (`upper_arm_r`, `forearm_r`, `hand_r`, `thigh_r`, `shin_r`, `foot_r`) vào rig thực tế. Các giá trị offset/pivot ở trên chỉ là **giá trị minh họa**, phải hiệu chỉnh theo ảnh PNG thực tế. Định nghĩa rõ `offset` theo đơn vị local của part cha và `pivot` theo tọa độ chuẩn hóa 0–1; không trộn pixel và phần trăm.

Nên bổ sung: `rest_transform`, `bind_pose`, `default_clip`, `blend_mode`, `clip_start`, `clip_speed`, `facing`, `ground_contact`, `foot_ik` (tùy chọn), `part_visibility`, `facial_expression`. **Phân biệt** `pose` toàn thân cũ với `clip` rig mới; không tái sử dụng tên trường theo cách gây nhầm lẫn.

## 6. Sinh ảnh từng bộ phận

### 6.1. Quy trình ưu tiên

1. Sinh **master character** (tư thế trung tính, góc nhìn đã chọn, không nền).
2. Sinh hoặc tách các bộ phận từ master; mỗi phần phải giữ cùng màu, độ dày nét, độ sáng và tỷ lệ.
3. Tạo PNG trong suốt cho từng phần, giữ **vùng chồng lấn tại khớp** để tránh hở khe khi xoay.
4. Đo alpha bbox, xác định pivot (vai, khuỷu, cổ tay, cổ, hông, gối, mắt cá), ghi vào `rig.json`.
5. Ghép atlas để giảm số request ảnh trong HTML; vẫn lưu file part gốc để debug.
6. Kiểm tra nhân vật ở bind pose, idle, walk, wave, bend trước khi chấp nhận.

**Lưu ý:** `request_image()` hiện chưa gửi ảnh tham chiếu. Muốn sinh nhiều part nhất quán bằng ảnh master, cần nâng cấp hợp đồng `GenerateRequest` và `/generate-image` ở `codex_server`, ví dụ nhận danh sách ảnh tham chiếu dưới dạng base64 hoặc đường dẫn an toàn do server quản lý. Phải kiểm tra khả năng thực tế của backend trước khi thiết kế payload; không tự thêm field vào request đang cấm field phụ. Nếu backend không hỗ trợ reference image, lựa chọn đáng tin cậy hơn là **tách bộ phận từ một master** bằng công cụ biên tập/segmentation có kiểm duyệt thủ công, thay vì sinh độc lập hoàn toàn.

### 6.2. Prompt bộ phận

```python
RIG_PART_RULES = """
Produce ONE isolated character body part as transparent PNG.
Match the supplied character master exactly: identity, proportions,
colors, line weight, light direction and perspective.
Keep intentional overlap at joints for cut-out animation.
Do not draw adjacent parts, cast shadow, scenery or labels.
No baked motion blur. Preserve smooth anti-aliased edges.
Use the specified view and rest-pose orientation.
"""
```

### 6.3. Phần cần sửa trong Python

- `image_prompt()`: phân nhánh `background`, `sheet`, `rig_master`, `rig_part`.
- `sheet_prompt()`: chỉ áp dụng cho asset cũ; thêm `rig_part_prompt()`.
- `generate_assets()`: thêm `generate_rig_assets()`, lưu master/parts/atlas/rig metadata.
- `asset_recipe()` và `PIPELINE_VERSION`: cập nhật fingerprint gồm art direction, character bible, master hash, part definition và phiên bản normalize.
- `read_png()` / `png_info()`: giữ kiểm tra PNG, alpha; thêm `rig_part_info()` thay vì áp quy tắc “chân ở đáy frame” lên mọi bộ phận.
- `normalize_pose()`: giữ cho sheet cũ; **không** tự căn giữa từng part rig vì sẽ phá pivot. Thay bằng `normalize_rig_part()` bảo toàn pivot và tỷ lệ gốc.

## 7. Validator rig mới

Thêm `validate_rig()` và gọi từ `validate_plan()`:

- Part ID duy nhất; `parent` tồn tại hoặc `null`; có đúng một root; không có chu trình.
- Pivot nằm trong [0,1], offset hữu hạn, kích thước hợp lệ, z là số hợp lệ.
- Mỗi socket trỏ tới part tồn tại; tọa độ socket nằm trong frame part.
- Mọi `clip.channels` trỏ tới part/thuộc tính được hỗ trợ; thời gian keyframe tăng, nằm trong clip duration.
- Chỉ cho phép thuộc tính có định nghĩa: `rotation`, `x`, `y`, `scale_x`, `scale_y`, `opacity`, `visible`.
- Part PNG phải trong suốt, không rỗng, không bị cắt; alpha noise được lọc có kiểm soát.
- Rest pose phải khớp với master trong sai số chấp nhận được; có kiểm tra seam ở vai/cổ/khuỷu/gối.
- Rig phải có kích thước thực tế phù hợp `geometry.size_m` và `pixels_per_meter` của shot.
- Khi có attach, socket của rig phải được tính bằng transform thế giới của **part tương ứng**, không còn dựa vào `parent.pose` như sprite sheet cũ.

Tạo báo cáo `rig_review/`: ảnh ghép rest pose, 4–8 mốc của từng clip, bản đồ pivot/socket, danh sách lỗi và cảnh báo. Không tuyên bố đã đạt nhất quán mỹ thuật chỉ vì kiểm tra PNG hợp lệ.

## 8. HTML renderer: phân cấp bộ phận

### 8.1. DOM

```html
<div class="actor-rig" data-actor="girl">
  <div class="rig-part" data-part="torso"></div>
  <div class="rig-part" data-part="head"></div>
  <div class="rig-part" data-part="upper_arm_l"></div>
  <!-- Các part còn lại được tạo từ rig.json -->
</div>
```

Có thể dựng DOM lồng nhau theo `parent`, hoặc giữ các part phẳng và tính ma trận thế giới cho từng part. **Khuyến nghị:** tính ma trận 2D bằng JavaScript, dùng cùng phép toán với Python layout checker; DOM phẳng giúp dễ kiểm soát z-order và debug. Cần định nghĩa thứ tự ma trận nhất quán: `world_part = world_actor × parent_chain × translate(offset) × rotate(angle) × scale × translate(-pivot_px)`.

### 8.2. Pseudocode renderer

```javascript
function sampleChannel(keys, time, easing = 'linear') {
  // Tìm hai keyframe kề nhau, nội suy theo easing;
  // với clip loop: dùng time modulo clip.duration.
}
function computePartWorld(partId, rig, sampledClip, cache) {
  // 1. Lấy transform local từ rest + animation.
  // 2. Nhân với transform world của parent (đệ quy có cache).
  // 3. Trả ma trận và điểm socket ở hệ tọa độ world.
}
function renderRig(actor, absoluteTime) {
  // Dùng thời gian tuyệt đối của phase, không cộng dồn góc qua frame.
  // Sample clip, tính world matrix từng part, cập nhật CSS transform.
}
```

**Quan trọng:** `renderAt(t)` phải xác định hoàn toàn trạng thái tại thời điểm `t`. Khi tua từ 8 giây về 2 giây, nhân vật phải đúng pose, không phụ thuộc frame trước. Đây là yêu cầu để giữ tính năng scrub timeline và xuất ảnh review.

### 8.3. Easing và motion

```javascript
function easeInOutCubic(t) {
  return t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;
}
```

- Áp easing cho cử chỉ, quay đầu, giơ tay, cúi người.
- Giữ `linear` cho `geometry.motion="constant"` để không phá vận tốc.
- Chu kỳ walk phải đồng bộ vận tốc di chuyển và chiều dài bước; nếu không sẽ bị **trượt chân**.
- Thêm `idle` (thở, chớp mắt), `walk`, `run`, `wave`, `look`, `bend`, `pick_up` và các clip chuyển tiếp.
- Cân nhắc IK hai đoạn cho tay/chân ở giai đoạn sau; MVP dùng FK (forward kinematics) là đủ.
- Bóng tiếp đất nên là layer riêng, không bake vào PNG part.
- Parallax phải tác động đến các lớp nền theo cùng camera coordinate system; không phá camera zoom hiện tại.

## 9. Attachment, camera, continuity

Giữ track cấp **actor** trong `phases[].tracks` và `geometry` hiện có. Khi rig được bật:

- `actorState()` tiếp tục xác định vị trí, scale, rotation, flip, opacity của actor root.
- `renderRig()` tính transform từng part tương đối actor root.
- `attach` vật cầm trỏ tới socket thuộc `part` (ví dụ bàn tay), không trỏ tới pose sheet.
- Xe và người ngồi trên xe có thể giữ attach cấp actor, nhưng socket ghế cần đúng thế giới tọa độ.
- Camera cut giữ identity/rig/clip state và cho phép bố trí lại tọa độ shot theo quy tắc cũ.
- Camera continuous giữ shot, nền và hệ tọa độ; zoom áp cho cả background, rig và vật thể.
- `check_continuity()` cần kiểm tra clip/phase và trạng thái animation tại ranh giới, tránh nhảy khớp khi đổi phase.
- Python `layout_state()` và `endpoint_outside_stage()` phải tính **bounding box hợp nhất của toàn bộ part sau biến đổi**, không dùng kích thước một ô sprite sheet.

## 10. Lộ trình triển khai

### Giai đoạn A — Khóa phong cách
- Thêm `ART_DIRECTION`, character bible và palette.
- Đưa vào prompt lập kế hoạch và prompt ảnh, bao gồm retry.
- Kiểm thử 1 nền và 1 master character.

### Giai đoạn B — Rig MVP
- Bổ sung `render_mode`, `parts`, `parent`, `pivot`, `offset`, `z`, `clips`.
- Thêm validator rig và asset pipeline cho master/parts.
- Dựng 1 nhân vật tối thiểu: torso, head, hai tay, hai chân (có thể bắt đầu bằng các khối đơn giản trước khi sinh ảnh thật).
- Xây HTML renderer phân cấp; giữ sheet renderer cũ.

### Giai đoạn C — Chuyển động và tương tác
- Thêm clips idle/walk/wave/bend; easing theo channel.
- Socket ở bàn tay, attach đạo cụ; kiểm tra nhặt và thả không giật.
- Đồng bộ walk cycle với dịch chuyển; bóng tiếp đất.

### Giai đoạn D — Chất lượng và kiểm thử
- Contact sheet rest/animation, kiểm tra alpha/pivot/seam.
- So sánh render Python với HTML tại các timestamp cố định.
- Kiểm tra continuity giữa phase, camera cut, camera zoom, vật cầm, đối tượng ra khỏi khung.
- Chạy thử một kịch bản ngắn trước khi mở rộng.

## 11. Tiêu chí nghiệm thu

1. Một nhân vật giữ nguyên thiết kế, màu sắc và tỷ lệ ở mọi clip.
2. Đầu/tay/chân xoay quanh khớp đúng, không tách rời hoặc lộ khe lớn.
3. Idle, walk, wave, bend hoạt động và tua timeline tới thời điểm bất kỳ vẫn đúng.
4. Đi bộ không trượt chân rõ rệt; dừng/chuyển động không giật.
5. Vật gắn vào bàn tay di chuyển theo tay, không nhảy khi đổi clip.
6. Zoom/cut và ranh giới phase không làm nhân vật biến mất hay đổi tỷ lệ bất thường.
7. Bản cũ `render_mode="sheet"` vẫn chạy.
8. Có báo cáo lỗi kỹ thuật và ảnh review; kiểm tra mỹ thuật vẫn có bước duyệt hình.

## 12. Những điểm cần tránh

- Không đổi tất cả asset sang rig: nền và nhiều vật thể vẫn nên dùng PNG/sheet.
- Không dùng `normalize_pose()` của sheet để căn từng part độc lập.
- Không tin rằng prompt thuần chữ bảo đảm mọi part giống master.
- Không dùng CSS transition phụ thuộc frame trước cho timeline có chức năng tua.
- Không thêm easing cho chuyển động vận tốc không đổi.
- Không để HTML và Python dùng hai công thức pivot/transform khác nhau.
- Không thay thế kiểm tra mỹ thuật bằng kiểm tra alpha hoặc kích thước PNG.

## 13. Danh sách hàm cần sửa/thêm

| Vị trí | Thay đổi |
|---|---|
| `PLAN_PROMPT` | Thêm schema rig và clip, khóa art direction |
| `analyze_script()` | Áp quy chuẩn ở lần gọi đầu và retry |
| `validate_plan()` | Phân nhánh sheet/rig, gọi `validate_rig()` |
| `image_prompt()` | Hỗ trợ master/part prompts |
| `sheet_prompt()` | Giữ cho chế độ cũ |
| `request_image()` | Chỉ mở rộng reference-image sau khi server hỗ trợ |
| `generate_assets()` | Thêm sinh rig assets, atlas, metadata |
| `normalize_pose()` | Chỉ dùng sheet; tạo `normalize_rig_part()` |
| `png_info()` | Thêm kiểm tra riêng cho part và rig |
| `asset_recipe()` | Cache hash gồm character bible/master/rig |
| `layout_state()` | Tính world transforms và bbox của rig |
| `check_continuity()` | Kiểm tra trạng thái clip và socket giữa phase |
| `STYLE` | CSS actor-rig, rig-part, shadow layers |
| `JAVASCRIPT` | `sampleClip()`, `computePartWorld()`, `renderRig()` |
| `renderAt()` | Phân nhánh sheet/rig theo `render_mode` |

---

**Khuyến nghị triển khai:** làm MVP với **một nhân vật, một góc nhìn, ba clip (idle/walk/wave)** trước. Sau khi rig, pivot, attach và scrub ổn định mới bổ sung biểu cảm khuôn mặt, IK, nhiều góc nhìn và parallax nâng cao.
