# KỊCH BẢN VIDEO

Tổng thời lượng: **42 giây**

Canvas chuẩn: **1920×1080 px**  
Hệ tọa độ: gốc `(0,0)` tại góc trên bên trái.  
Phong cách: hoạt hình 2D giáo dục, màu sắc dễ phân biệt giữa bờ biển, sóng và dòng chảy.  
Lưu ý: tọa độ, kích thước và tốc độ là giá trị dự kiến, cần hiệu chỉnh sau khi sinh asset.

## 1. Danh sách asset dùng chung

### Background

| ID | Tên | Mô tả | Mục đích sử dụng |
|---|---|---|---|
| BG-01 | Bãi biển toàn cảnh | Bờ cát, mặt biển, đường chân trời, sóng vỗ | Phase 1, Phase 5 |
| BG-02 | Sơ đồ nhìn từ trên xuống | Bờ biển nằm ngang, vùng nước nông và vùng biển ngoài khơi | Phase 2 |
| BG-03 | Mặt cắt bờ biển | Góc nhìn nghiêng thể hiện bờ, vùng nước gần bờ và ngoài khơi | Phase 3, Phase 4 |

### Character

| ID | Tên | Mô tả | Mục đích sử dụng |
|---|---|---|---|
| CH-01 | Người bơi | Nhân vật hoạt hình nhìn từ trên xuống, trang phục màu nổi bật | Minh họa tác động của dòng chảy ở Phase 3, Phase 4 |
| CH-02 | Ngư dân trên bờ | Nhân vật nhỏ đứng gần bờ, có thể cầm vật dụng biển | Tạo ngữ cảnh thuật ngữ dân gian ở Phase 5 |

### Object

| ID | Tên | Mô tả | Mục đích sử dụng |
|---|---|---|---|
| OBJ-01 | Dải sóng hướng vào bờ | Các lớp sóng màu xanh-trắng chuyển động về phía bờ | Tạo chuyển động nền ở các phase |
| OBJ-02 | Dải dòng rip current | Dải nước hẹp, màu xanh đậm, có mũi tên hướng ra khơi | Đối tượng chính trong Phase 2–5 |
| OBJ-03 | Đường bờ biển | Dải cát phân cách bờ và mặt nước | Dùng chung cho toàn video |
| OBJ-04 | Phao đánh dấu dòng chảy | Phao nhỏ màu cam hoặc vàng | Đánh dấu vùng dòng chảy ở Phase 3, Phase 4 |
| OBJ-05 | Thuyền ngoài khơi | Silhouette thuyền nhỏ ở xa bờ | Tạo cảm giác hướng “ra ngoài khơi” |
| OBJ-06 | Nhãn thông tin | Các nhãn: “BỜ”, “NGOÀI KHƠI”, “DÒNG CHẢY MẠNH”, “HẸP”, “HƯỚNG RA KHƠI” | Minh họa khái niệm và tổng kết |

### Sprite

| ID | Tên | Pose/frame cần tạo | Mục đích sử dụng |
|---|---|---|---|
| SP-01 | Người bơi cơ bản | Nằm ngang, tay xuôi, chân duỗi | Trạng thái nghỉ và chuyển động chậm |
| SP-02 | Người bơi quạt tay | Tay luân phiên, chân đạp nước | Minh họa người bơi cố gắng giữ vị trí |
| SP-03 | Người bơi bị dòng đẩy | Thân nghiêng nhẹ, tay chân lệch hướng dòng nước | Minh họa chuyển động theo dòng rip current |
| SP-04 | Ngư dân đứng | Đứng yên, quay mặt ra biển, tay chỉ về phía nước | Minh họa tên gọi dân gian |
| SP-05 | Sóng lặp | 4–6 frame sóng tiến vào bờ | Tạo chuyển động nền liên tục |
| SP-06 | Dòng chảy lặp | 6–8 frame dải nước co giãn và các mũi tên di chuyển | Tạo cảm giác dòng nước mạnh, liên tục |

---

## 2. Danh sách phase

### Phase 1 — Mở đầu: Biển nhìn từ bờ

Thời lượng: **6 giây**

#### A. Kịch bản nội dung

- **Bối cảnh:** Một bãi biển nhìn từ góc nghiêng rộng. Bờ cát ở tiền cảnh, biển và đường chân trời ở phía xa.
- **Nhân vật:** Chưa xuất hiện nhân vật chính.
- **Diễn biến theo thời gian:**
  - `0–2 giây:` Toàn cảnh biển, các lớp sóng liên tục tiến vào bờ.
  - `2–4 giây:` Một vùng nước hẹp, màu xanh đậm dần nổi bật giữa các vùng sóng.
  - `4–6 giây:` Tiêu đề xuất hiện: **“Dòng chảy xa bờ”**. Một mũi tên mờ hướng từ bờ ra biển.
- **Âm thanh:** Tiếng sóng biển nhẹ, nhạc nền giáo dục chậm. Khi tiêu đề xuất hiện có âm thanh nhấn nhẹ.
- **Trạng thái đầu:** Toàn cảnh biển bình thường, chưa xác định dòng chảy.
- **Trạng thái cuối:** Dòng chảy hẹp đã được đánh dấu, chuẩn bị chuyển sang sơ đồ giải thích.

#### B. Kịch bản kỹ thuật

- **Camera:**
  - Góc nhìn nghiêng từ trên bờ hướng ra biển.
  - Vị trí camera khoảng `(960, 540)`, khung hình toàn cảnh.
  - Camera cố định; zoom kỹ thuật số nhẹ từ `100%` lên `106%` trong 6 giây.
- **Asset sử dụng:** `BG-01`, `OBJ-01`, `OBJ-02`, `OBJ-03`, `OBJ-06`, `SP-05`.
- **Vị trí và hướng di chuyển:**
  - Đường bờ nằm quanh `y=760`.
  - Sóng di chuyển từ `y=560` về `y=760`, hướng vào bờ.
  - Dải dòng chảy bắt đầu quanh `x=980, y=730`, kéo ra phía `x=1040, y=360`.
  - Dòng chảy có tỷ lệ hiển thị ban đầu khoảng `35%`, tăng lên `60%`.
- **Sprite pose cần thiết:**
  - `SP-05`: lặp liên tục để tạo sóng.
  - `SP-06`: bắt đầu ở độ mờ thấp, sau đó tăng dần.
- **Timeline animation:**
  - `0–2 giây:` Chạy nền sóng và giữ camera toàn cảnh.
  - `2–4 giây:` Dải dòng chảy `OBJ-02` fade-in và scale từ `0.8` lên `1.0`.
  - `4–6 giây:` Nhãn tiêu đề fade-in; mũi tên dòng chảy chuyển động từ bờ ra ngoài khơi.
- **Phương pháp animation:**
  - CSS `transform: translate()` cho sóng và mũi tên.
  - CSS `scale()` và `opacity` để xuất hiện dòng chảy.
  - Sprite animation cho `SP-05`, `SP-06`.
  - JavaScript điều khiển mốc xuất hiện tiêu đề và chuyển phase.
- **Trạng thái kỹ thuật đầu/cuối:**
  - **Đầu:** `OBJ-02` ẩn hoặc chỉ hiển thị mờ.
  - **Cuối:** Dải dòng chảy và hướng ra khơi được xác định tại trung tâm khung hình; camera sẵn sàng chuyển sang sơ đồ nhìn từ trên xuống.

---

### Phase 2 — Cấu trúc dòng chảy

Thời lượng: **9 giây**

#### A. Kịch bản nội dung

- **Bối cảnh:** Sơ đồ nhìn từ trên xuống. Bờ biển nằm ở phía dưới, biển ngoài khơi ở phía trên.
- **Nhân vật:** Không có.
- **Diễn biến theo thời gian:**
  - `0–3 giây:` Các lớp sóng từ ngoài khơi tiến vào bờ theo nhiều dải song song.
  - `3–6 giây:` Nước dồn gần bờ và tập trung vào một lối hẹp.
  - `6–9 giây:` Dòng nước mạnh thoát thẳng ra ngoài khơi qua lối hẹp đó.
- **Âm thanh:** Nhạc nền tiếp tục; âm thanh “whoosh” nhẹ khi mũi tên dòng chảy hướng ra khơi.
- **Trạng thái đầu:** Mặt biển có các lớp sóng thông thường.
- **Trạng thái cuối:** Một dòng nước hẹp, liên tục, đi từ bờ ra ngoài khơi đã được minh họa rõ.

#### B. Kịch bản kỹ thuật

- **Camera:**
  - Chuyển sang góc nhìn top-down.
  - Camera bắt đầu ở `(960,540)`, zoom từ `110%` về `100%` để mở rộng toàn bộ sơ đồ.
  - Camera cố định sau khi hoàn tất chuyển cảnh.
- **Asset sử dụng:** `BG-02`, `OBJ-01`, `OBJ-02`, `OBJ-03`, `OBJ-06`, `SP-05`, `SP-06`.
- **Vị trí và hướng di chuyển:**
  - Đường bờ chạy ngang tại `y=820`.
  - Sóng đi từ phía trên `(y=180)` xuống phía bờ `(y=820)`.
  - Dòng chảy bắt đầu tại vùng nước gần bờ `(x=900–1030, y=750)`, kết thúc hướng ra ngoài khơi `(x=960, y=170)`.
  - Dải dòng chảy rộng khoảng `120–180 px`, hẹp hơn nhiều so với vùng biển xung quanh.
- **Sprite pose cần thiết:**
  - `SP-05`: sóng tiến vào bờ.
  - `SP-06`: các mũi tên và dải nước chuyển động ngược hướng sóng.
- **Timeline animation:**
  - `0–2 giây:` Crossfade từ `BG-01` sang `BG-02`.
  - `2–4 giây:` Các dải sóng chuyển động đồng thời về phía bờ.
  - `4–6 giây:` Hiệu ứng nước dồn nhẹ quanh khu vực `x=960, y=730`.
  - `6–9 giây:` Mũi tên trong `OBJ-02` chạy liên tục từ `y=760` lên `y=180`; nhãn “HƯỚNG RA NGOÀI KHƠI” xuất hiện.
- **Phương pháp animation:**
  - CSS `translateY()` cho các lớp sóng.
  - CSS `translateY()` ngược chiều cho mũi tên dòng chảy.
  - CSS `scaleX()` để nhấn mạnh độ hẹp của dòng.
  - JavaScript đồng bộ chuyển động sóng, dòng nước và nhãn.
- **Trạng thái kỹ thuật đầu/cuối:**
  - **Đầu:** Camera top-down, chỉ có sóng hướng vào bờ.
  - **Cuối:** `OBJ-02` nằm cố định giữa sơ đồ, hướng từ bờ ra khơi; các asset được giữ nguyên cho Phase 3.

---

### Phase 3 — Dòng nước mạnh và hẹp

Thời lượng: **10 giây**

#### A. Kịch bản nội dung

- **Bối cảnh:** Mặt cắt nghiêng của bờ biển, cho phép nhìn thấy vùng nước gần bờ và dòng chảy hướng ra xa.
- **Nhân vật:** `CH-01` — người bơi, dùng làm đối tượng tham chiếu chuyển động.
- **Diễn biến theo thời gian:**
  - `0–3 giây:` Người bơi xuất hiện gần bờ, đang ở vùng nước tương đối nông.
  - `3–6 giây:` Các lớp sóng vẫn hướng vào bờ, trong khi người bơi bắt đầu bị kéo lệch ra ngoài.
  - `6–10 giây:` Người bơi di chuyển theo dải dòng hẹp; dải nước và mũi tên tăng tốc để thể hiện dòng chảy mạnh.
- **Âm thanh:** Tiếng sóng rõ hơn; thêm âm thanh nước chuyển động mạnh nhưng không gây hoảng sợ.
- **Trạng thái đầu:** Người bơi ở gần bờ, đứng yên tương đối so với mặt nước.
- **Trạng thái cuối:** Người bơi ở xa bờ hơn, nằm trong vùng dòng chảy; dòng chảy được gắn nhãn “MẠNH” và “HẸP”.

#### B. Kịch bản kỹ thuật

- **Camera:**
  - Góc nhìn nghiêng cắt lớp, camera ở khoảng `(960,540)`.
  - Camera cố định trong 10 giây.
  - Zoom nhẹ từ `100%` lên `108%` trong đoạn cuối để nhấn mạnh dòng nước.
- **Asset sử dụng:** `BG-03`, `OBJ-01`, `OBJ-02`, `OBJ-03`, `OBJ-04`, `OBJ-06`, `CH-01`, `SP-01`, `SP-02`, `SP-03`, `SP-05`, `SP-06`.
- **Vị trí và hướng di chuyển:**
  - Bờ biển nằm tại vùng `y=760`.
  - `CH-01` bắt đầu tại `(780,690)`, tỷ lệ hiển thị khoảng `55%`.
  - Nhân vật kết thúc tại `(960,430)`, hướng đầu về phía ngoài khơi.
  - `OBJ-04` đặt gần mép dòng tại `(1030,650)`, trôi nhẹ theo dòng.
  - Dòng chảy đi từ `(920,720)` đến `(1000,300)`.
- **Sprite pose cần thiết:**
  - `SP-01`: người bơi ổn định ở đầu phase.
  - `SP-02`: quạt tay trong lúc cố giữ vị trí.
  - `SP-03`: thân người bị đẩy theo hướng dòng chảy.
  - `SP-06`: dải dòng nước chuyển động mạnh, cần nhiều frame hơn các asset khác.
- **Timeline animation:**
  - `0–2 giây:` `CH-01` fade-in tại gần bờ với `SP-01`.
  - `2–4 giây:` Chuyển sang `SP-02`; sóng tiến vào bờ đồng thời.
  - `4–7 giây:` CSS `translateX()` và `translateY()` đưa người bơi từ `(780,690)` đến `(860,570)`.
  - `7–9 giây:` Chuyển sang `SP-03`; nhân vật tiếp tục đi theo dòng đến `(960,430)`.
  - `9–10 giây:` Nhãn “MẠNH” và “HẸP” xuất hiện, dải dòng chảy pulse nhẹ.
- **Phương pháp animation:**
  - CSS `transform: translate()` cho chuyển động của nhân vật, phao và dòng nước.
  - Sprite animation cho toàn bộ thay đổi tư thế của `CH-01`.
  - CSS `scale()` và `filter` nhẹ để tăng độ tương phản của dòng chảy.
  - JavaScript điều khiển chuyển pose theo thời gian và khóa trạng thái nhân vật ở cuối phase.
- **Trạng thái kỹ thuật đầu/cuối:**
  - **Đầu:** `CH-01` ở gần bờ, dùng `SP-01`; dòng chảy hiển thị ở cường độ thấp.
  - **Cuối:** `CH-01` ở giữa dải dòng, dùng `SP-03`; `OBJ-02` hiển thị rõ với cường độ cao. Tọa độ nhân vật được kế thừa sang Phase 4.

---

### Phase 4 — Hướng chảy thẳng ra ngoài khơi

Thời lượng: **9 giây**

#### A. Kịch bản nội dung

- **Bối cảnh:** Tiếp tục mặt cắt bờ biển, nhưng khung hình mở rộng để thấy rõ hướng từ bờ ra biển.
- **Nhân vật:** `CH-01` tiếp tục xuất hiện trong dòng chảy.
- **Diễn biến theo thời gian:**
  - `0–3 giây:` Giữ hình người bơi trong dòng nước, các mũi tên chạy về phía ngoài khơi.
  - `3–6 giây:` Camera lùi nhẹ, cho thấy dòng chảy hẹp nằm giữa các vùng nước có sóng hướng vào bờ.
  - `6–9 giây:` Nhãn đầy đủ xuất hiện: **“DÒNG NƯỚC MẠNH, HẸP, CHẢY TỪ BỜ RA NGOÀI KHƠI”**.
- **Âm thanh:** Tiếng sóng và tiếng nước chảy; nhạc nền nâng nhẹ khi câu định nghĩa xuất hiện.
- **Trạng thái đầu:** Người bơi và dòng chảy đang ở giữa cảnh.
- **Trạng thái cuối:** Toàn bộ cơ chế dòng rip current được nhìn thấy trong một khung hình.

#### B. Kịch bản kỹ thuật

- **Camera:**
  - Góc nhìn nghiêng rộng hơn, vẫn quan sát từ bờ ra biển.
  - Camera chuyển động lùi nhẹ từ vị trí `(960,540)` lên mức zoom `92%`.
  - Hướng chuyển động camera: lùi ra sau và hơi nâng góc nhìn.
- **Asset sử dụng:** `BG-03`, `OBJ-01`, `OBJ-02`, `OBJ-03`, `OBJ-04`, `OBJ-05`, `OBJ-06`, `CH-01`, `SP-03`, `SP-05`, `SP-06`.
- **Vị trí và hướng di chuyển:**
  - Giữ `CH-01` bắt đầu tại `(960,430)`.
  - Nhân vật trôi thêm đến `(1040,300)`, tỷ lệ giảm từ `55%` xuống `45%` để tạo cảm giác đi xa bờ.
  - `OBJ-05` xuất hiện ở `(1480,220)` để làm mốc ngoài khơi.
  - Các mũi tên trong `OBJ-02` đi cùng một hướng từ dưới lên trên.
- **Sprite pose cần thiết:**
  - `SP-03` tiếp tục lặp.
  - `SP-05` chạy ngược chiều dòng chảy ở các vùng bên ngoài.
  - `SP-06` chạy nhanh hơn Phase 3 để nhấn mạnh sức mạnh của dòng.
- **Timeline animation:**
  - `0–3 giây:` Tiếp tục chuyển động của `CH-01` và `SP-06`.
  - `3–6 giây:` Camera zoom-out; `OBJ-05` fade-in ở xa.
  - `6–8 giây:` Các nhãn “MẠNH”, “HẸP”, “RA KHƠI” lần lượt xuất hiện.
  - `8–9 giây:` Toàn bộ nhãn và mũi tên giữ ổn định để người xem đọc.
- **Phương pháp animation:**
  - CSS `transform: scale()` cho camera giả lập.
  - CSS `translate()` cho nhân vật, phao và mũi tên.
  - Sprite animation cho `SP-03`, `SP-05`, `SP-06`.
  - JavaScript quản lý thứ tự xuất hiện của nhãn và thời điểm chuyển phase.
- **Trạng thái kỹ thuật đầu/cuối:**
  - **Đầu:** Nhân vật đang ở giữa dòng chảy, các mũi tên chuyển động liên tục.
  - **Cuối:** Camera đã mở rộng, toàn bộ hướng dòng từ bờ ra khơi nằm trong khung; thông tin sẵn sàng chuyển sang phần tổng kết.

---

### Phase 5 — Tổng kết khái niệm

Thời lượng: **8 giây**

#### A. Kịch bản nội dung

- **Bối cảnh:** Quay lại toàn cảnh bãi biển, kết hợp một sơ đồ nhỏ dòng chảy ở trung tâm.
- **Nhân vật:** `CH-02` đứng trên bờ, chỉ về vùng dòng chảy; `CH-01` có thể giữ ở kích thước nhỏ ngoài khơi.
- **Diễn biến theo thời gian:**
  - `0–2 giây:` Camera trở lại toàn cảnh bãi biển.
  - `2–5 giây:` `CH-02` xuất hiện trên bờ; sơ đồ dòng chảy được đặt nổi bật trên mặt biển.
  - `5–8 giây:` Hiện câu kết: **“Dòng chảy xa bờ là dòng nước mạnh, hẹp, chảy từ bờ biển thẳng ra ngoài khơi.”**
  - Có thể bổ sung dòng chữ nhỏ: **“Ngư dân thường gọi là dòng xoáy hoặc ao xoáy.”**
- **Âm thanh:** Nhạc nền kết thúc nhẹ; tiếng sóng giảm dần.
- **Trạng thái đầu:** Toàn cảnh sẵn sàng tổng kết, các nhãn Phase 4 vẫn còn mờ.
- **Trạng thái cuối:** Câu định nghĩa hiển thị đầy đủ; hình ảnh giữ ổn định trong 1 giây cuối.

#### B. Kịch bản kỹ thuật

- **Camera:**
  - Chuyển từ góc nghiêng về toàn cảnh bờ biển.
  - Camera cố định sau khi hoàn tất chuyển cảnh.
  - Vị trí khung hình khoảng `(960,540)`, zoom `100%`.
- **Asset sử dụng:** `BG-01`, `OBJ-01`, `OBJ-02`, `OBJ-03`, `OBJ-06`, `CH-01`, `CH-02`, `SP-04`, `SP-05`, `SP-06`.
- **Vị trí và hướng di chuyển:**
  - `CH-02` xuất hiện tại `(420,735)`, tỷ lệ `45%`, hướng mặt về biển.
  - `CH-01` giữ ở vùng `(1030,350)` với tỷ lệ `35%`.
  - `OBJ-02` đặt giữa khung hình, hướng từ `(960,720)` đến `(1000,350)`.
  - Các nhãn tổng kết nằm tại vùng `(960,150–250)`.
- **Sprite pose cần thiết:**
  - `SP-04`: ngư dân đứng yên, tay chỉ về dòng chảy.
  - `SP-05`: sóng chạy chậm.
  - `SP-06`: dòng chảy lặp ở tốc độ vừa phải.
- **Timeline animation:**
  - `0–2 giây:` Crossfade từ `BG-03` về `BG-01`; giảm tốc độ dòng chảy.
  - `2–4 giây:` `CH-02` fade-in và chuyển sang pose chỉ về biển.
  - `4–6 giây:` Câu định nghĩa xuất hiện từng dòng, theo thứ tự “mạnh” → “hẹp” → “từ bờ ra ngoài khơi”.
  - `6–7 giây:` Hiện chú thích “dòng xoáy / ao xoáy”.
  - `7–8 giây:` Giữ hình, giảm âm lượng và fade-out nhẹ.
- **Phương pháp animation:**
  - CSS `opacity` và `transform` cho chuyển cảnh và xuất hiện nhân vật.
  - Sprite animation cho `SP-04`, `SP-05`, `SP-06`.
  - JavaScript điều khiển thứ tự hiển thị câu định nghĩa và kết thúc video.
- **Trạng thái kỹ thuật đầu/cuối:**
  - **Đầu:** Các asset từ Phase 4 được thu nhỏ và chuyển về bố cục toàn cảnh.
  - **Cuối:** `OBJ-02` vẫn chỉ rõ hướng từ bờ ra khơi; câu định nghĩa hiển thị đầy đủ; video kết thúc ở trạng thái ổn định.

---

## Kiểm tra tổng thời lượng

| Phase | Thời lượng |
|---|---:|
| Phase 1 | 6 giây |
| Phase 2 | 9 giây |
| Phase 3 | 10 giây |
| Phase 4 | 9 giây |
| Phase 5 | 8 giây |
| **Tổng cộng** | **42 giây** |
