// Cùng chuyển động 5 giây như mario_animation/script.js, nhưng thời gian do HyperFrames điều khiển.
const mario = document.getElementById("mario");
const duration = 5;
const frameDuration = 0.1;
const runFrames = Array.from({ length: 6 }, (_, index) => {
  const image = new Image();
  image.src = `assets/run_${index}.png`;
  return image;
});
const footInsets = [13, 6, 11];
let currentFrame = -1;

function renderAt(time) {
  const currentTime = Math.max(0, Math.min(time, duration));
  mario.style.transform = `translateX(${(currentTime / duration) * 800}px)`;

  const frameIndex = Math.floor(currentTime / frameDuration + 1e-9) % runFrames.length;
  if (frameIndex !== currentFrame) {
    mario.src = runFrames[frameIndex].src;
    mario.style.setProperty("--foot-inset", `${footInsets[frameIndex % footInsets.length]}px`);
    currentFrame = frameIndex;
  }
}

renderAt(0);

const clock = { time: 0 };
const timeline = gsap.timeline({ paused: true });
timeline.to(clock, {
  time: duration,
  duration,
  ease: "none",
  onUpdate: () => renderAt(clock.time),
}, 0);
window.__timelines = window.__timelines || {};
window.__timelines["mario-animation"] = timeline;
