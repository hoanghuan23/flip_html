
const mario = document.getElementById("mario");
const timeline = document.getElementById("timeline");
const timeLabel = document.getElementById("time");
const playButton = document.getElementById("play");

const duration = 5;
const frameDuration = 0.1;
const runFrames = Array.from({ length: 6 }, (_, index) => {
  const image = new Image();
  image.src = `../run_${index}.png`;
  return image;
});
let currentFrame = -1;
let currentTime = 0;
let playing = false;
let startTime = 0;

// Xác định vị trí nhân vật theo thời gian
function renderAt(time) {
  currentTime = Math.max(0, Math.min(time, duration));

  const progress = currentTime / duration;

  // Mario di chuyển từ x = 0 đến x = 700
  const x = progress * 800;

  mario.style.transform = `translateX(${x}px)`;

  // Đổi ảnh mỗi 0,05 giây, lặp lại sau run_5.
  const frameIndex = Math.floor(currentTime / frameDuration + 1e-9) % runFrames.length;
  if (frameIndex !== currentFrame) {
    mario.src = runFrames[frameIndex].src;
    currentFrame = frameIndex;
  }

  timeline.value = currentTime;
  timeLabel.textContent = currentTime.toFixed(2) + "s";
}

// Điều khiển bằng thanh thời gian
timeline.addEventListener("input", () => {
  playing = false;
  playButton.textContent = "Play";
  renderAt(Number(timeline.value));
});

// Chạy animation
function animate(timestamp) {
  if (!playing) return;

  const elapsed = (timestamp - startTime) / 1000;
  renderAt(elapsed);

  if (elapsed < duration) {
    requestAnimationFrame(animate);
  } else {
    playing = false;
    playButton.textContent = "Play";
  }
}

playButton.addEventListener("click", () => {
  if (playing) {
    playing = false;
    playButton.textContent = "Play";
    return;
  }

  if (currentTime >= duration) renderAt(0);

  playing = true;
  playButton.textContent = "Pause";
  startTime = performance.now() - currentTime * 1000;
  requestAnimationFrame(animate);
});

// Cho phép HyperFrames gọi trực tiếp
window.renderAt = renderAt;

renderAt(0);
