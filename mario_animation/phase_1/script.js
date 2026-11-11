const scene = document.querySelector(".scene");
const character = document.getElementById("character");
const mario = document.getElementById("mario");
const timeline = document.getElementById("timeline");
const timeLabel = document.getElementById("time");
const playButton = document.getElementById("play");
const statusLabel = document.getElementById("status");

// Coordinates use an 800 × 450 stage; CSS percentages scale the whole scene together.
const stageWidth = 800;
const stageHeight = 450;
const duration = 5;
const runFrameDuration = 0.1;
const jumpHalfWidth = 98;
const jumpHeight = 122;
const preparationDuration = 0.1;
const landingDuration = 0.1;
const recoveryDuration = 0.1;

// Alpha bounds measured from the original 532 × 469 images.
// Each pose keeps its visible centre and feet at the same animation anchor.
function pose(name, left, right, bottom) {
  return {
    src: `../../characters/${name}.png`,
    center: (left + right) / 2,
    bottom,
  };
}

const runPoses = [
  pose("run_0", 100, 433, 418),
  pose("run_1", 159, 399, 462),
  pose("run_2", 145, 433, 432),
  pose("run_3", 100, 433, 418),
  pose("run_4", 159, 399, 462),
  pose("run_5", 145, 433, 432),
];
const jumpPoses = [
  pose("jump_0_crouch", 214, 421, 461),
  pose("jump_1_takeoff", 198, 437, 462),
  pose("jump_2_rise", 196, 424, 441),
  pose("jump_3_apex", 163, 421, 404),
  pose("jump_4_fall", 194, 434, 462),
  pose("jump_5_land", 238, 490, 461),
  pose("jump_6_recover", 211, 413, 461),
];

let jumps = [];
let currentTime = 0;
let currentPose = null;
let playing = false;
let startTime = 0;
let animationFrame = null;

function measureObstacles() {
  const bounds = scene.getBoundingClientRect();
  jumps = Array.from(scene.querySelectorAll(".obstacle"), (obstacle) => {
    const box = obstacle.getBoundingClientRect();
    const center = ((box.left - bounds.left + box.width / 2) / bounds.width) * stageWidth;
    return {
      start: ((center - jumpHalfWidth) / stageWidth) * duration,
      end: ((center + jumpHalfWidth) / stageWidth) * duration,
    };
  });
}

function renderAt(time) {
  currentTime = Math.max(0, Math.min(Number(time) || 0, duration));
  const progress = currentTime / duration;
  const x = progress * stageWidth;
  let height = 0;
  let selectedPose = runPoses[Math.floor(currentTime / runFrameDuration + 1e-9) % runPoses.length];
  let action = "chạy";

  for (const jump of jumps) {
    if (currentTime < jump.start - preparationDuration ||
        currentTime >= jump.end + landingDuration + recoveryDuration) continue;

    action = "nhảy";
    if (currentTime < jump.start) {
      selectedPose = jumpPoses[0];
    } else if (currentTime < jump.end) {
      const progress = (currentTime - jump.start) / (jump.end - jump.start);
      // A parabola puts the feet safely above the crate during the entire crossing.
      height = 4 * jumpHeight * progress * (1 - progress);
      const poseIndex = progress < 0.14 ? 1 : progress < 0.4 ? 2 : progress < 0.6 ? 3 : 4;
      selectedPose = jumpPoses[poseIndex];
    } else if (currentTime < jump.end + landingDuration) {
      selectedPose = jumpPoses[5];
    } else {
      selectedPose = jumpPoses[6];
    }
    break;
  }

  character.style.left = `${(x / stageWidth) * 100}%`;
  character.style.bottom = `calc(var(--ground-height) + ${(height / stageHeight) * 100}%)`;

  if (selectedPose !== currentPose) {
    mario.src = selectedPose.src;
    mario.style.transform = `translate(${-selectedPose.center / 532 * 100}%, ${(469 - selectedPose.bottom) / 469 * 100}%)`;
    mario.alt = `Nhân vật đang ${action}`;
    currentPose = selectedPose;
  }

  timeline.value = currentTime;
  timeLabel.textContent = currentTime.toFixed(2) + "s";
}

function pause() {
  playing = false;
  cancelAnimationFrame(animationFrame);
  animationFrame = null;
  playButton.textContent = "Play";
}

function animate(timestamp) {
  if (!playing) return;
  renderAt((timestamp - startTime) / 1000);
  if (currentTime >= duration) {
    pause();
    return;
  }
  animationFrame = requestAnimationFrame(animate);
}

function play() {
  if (playing) return;
  if (currentTime >= duration) renderAt(0);
  playing = true;
  playButton.textContent = "Pause";
  startTime = performance.now() - currentTime * 1000;
  animationFrame = requestAnimationFrame(animate);
}

playButton.addEventListener("click", () => playing ? pause() : play());
timeline.addEventListener("input", () => {
  pause();
  renderAt(timeline.value);
});

new ResizeObserver(() => {
  measureObstacles();
  renderAt(currentTime);
}).observe(scene);

// Deterministic seeking for previewing or capturing any point in the animation.
window.renderAt = renderAt;
measureObstacles();
renderAt(0);

// Preload every pose and scene image before starting to avoid flashes mid-jump.
const sources = [
  ...runPoses.map((frame) => frame.src),
  ...jumpPoses.map((frame) => frame.src),
  ...Array.from(scene.querySelectorAll(".obstacle"), (image) => image.src),
  "../../environment/background_1.png",
];
Promise.all(sources.map((src) => {
  const image = new Image();
  image.src = src;
  return image.decode();
})).then(() => {
  playButton.disabled = false;
  timeline.disabled = false;
  pause();
}).catch(() => {
  playButton.textContent = "Chưa tải được ảnh";
  statusLabel.textContent = "Không tải được ảnh hoạt ảnh. Hãy kiểm tra thư mục characters và environment rồi tải lại trang.";
});
