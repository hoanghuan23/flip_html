
const mario = document.getElementById("mario");

const duration = 5;
const frameDuration = 0.1;
const startX = -100;
const endX = 800;
const runFrames = Array.from({ length: 6 }, (_, index) => {
  const image = new Image();
  image.src = `../../characters/run_${index}.png`;
  return image;
});
// Transparent space below each pose at the 85px display size.
const footInsets = [13, 6, 11];
let currentFrame = -1;
let startTime;

// Xác định vị trí nhân vật theo thời gian
function renderAt(time) {
  const currentTime = Math.max(0, Math.min(time, duration));

  const progress = currentTime / duration;

  // Mario di chuyển từ x = -100 đến x = 800
  const x = startX + progress * (endX - startX);

  mario.style.transform = `translateX(${x}px)`;

  // Đổi ảnh mỗi 0,1 giây, lặp lại sau run_5.
  const frameIndex = Math.floor(currentTime / frameDuration + 1e-9) % runFrames.length;
  if (frameIndex !== currentFrame) {
    mario.src = runFrames[frameIndex].src;
    mario.style.setProperty("--foot-inset", `${footInsets[frameIndex % footInsets.length]}px`);
    currentFrame = frameIndex;
  }
}

// Tự chạy animation khi mở trang.
function animate(timestamp) {
  if (startTime === undefined) startTime = timestamp;

  const elapsed = (timestamp - startTime) / 1000;
  renderAt(elapsed);

  if (elapsed < duration) {
    requestAnimationFrame(animate);
  }
}

// Cho phép HyperFrames gọi trực tiếp
window.renderAt = renderAt;

renderAt(0);
requestAnimationFrame(animate);
