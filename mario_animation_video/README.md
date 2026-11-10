# Mario Animation với HyperFrames

Project này chuyển animation trong `../mario_animation` thành video 5 giây, 800 × 450, 30 fps. Một ảnh Mario được đổi tư thế mỗi 0,1 giây và di chuyển từ trái sang phải theo thời gian. HyperFrames điều khiển GSAP timeline; trang xem thử cũ vẫn có thanh thời gian và nút Play riêng.

Chạy trong thư mục `mario_animation_video`:

```powershell
npm.cmd install
npm.cmd run lint
npm.cmd run render
```

Kết quả là `mario-animation.mp4`. Yêu cầu Node.js 22+ và Chrome hoặc Edge. FFmpeg và FFprobe được cài cục bộ qua npm.
