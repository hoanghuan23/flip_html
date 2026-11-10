# Video Mario với HyperFrames

`index.html` ghép 28 trạng thái từ `mario/mario_01` đến `mario/mario_28` theo thứ tự. Từ cảnh 08, ảnh chạy lặp lại bắt đầu bằng `run_0.png`; Mario tiến 30 px mỗi cảnh đến khi ra khỏi mép phải nền. Mỗi trạng thái kéo dài 0,1 giây; video dài 2,8 giây, kích thước 800 × 450, 30 fps, không có âm thanh.

Từ thư mục `mario_video`, chạy:

```powershell
npm.cmd install
npm.cmd run lint
npm.cmd run render
```

HyperFrames cần Node.js 22+ và Chrome hoặc Edge. Script `render.ps1` tự thêm FFmpeg và FFprobe cục bộ vào `PATH`. File xuất ra là `mario_video/mario.mp4`. Nếu muốn video dài hơn, chỉnh `data-duration` và `data-start` của từng clip trong `index.html`, rồi cập nhật mốc `timeline.set` cho bằng tổng thời lượng.
