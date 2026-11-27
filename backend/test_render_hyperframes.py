import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import render_hyperframes as render


class RenderHyperframesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def svg_preview(self):
        root = self.root / "preview svg"
        root.mkdir()
        entries = []
        for i, duration in enumerate((1.25, 2.5), 1):
            src = f"phase_{i}.html"
            (root / src).write_text(
                '<html><head></head><body><svg viewBox="0 0 1920 1080"></svg>'
                f'<script>var D={duration};window.renderAt=function(t){{}};</script></body></html>',
                encoding="utf-8")
            entries.append({"src": src, "duration": duration, "title": f"Cảnh {i}"})
        (root / "index.html").write_text(
            '<script type="application/json" id="data">' + json.dumps(entries) + '</script>',
            encoding="utf-8")
        return root

    def png_preview(self):
        root = self.root / "preview_png"
        phase = root / "phase_1"
        phase.mkdir(parents=True)
        data = {"phase": {"duration": 3, "title": "PNG"}, "assets": []}
        (phase / "index.html").write_text(
            '<html><head></head><body><main><div id="stage"></div><button>Play</button></main>'
            '<script type="application/json" id="scene-data">' + json.dumps(data) +
            '</script><script src="script.js"></script></body></html>', encoding="utf-8")
        (phase / "script.js").write_text("window.renderAt=function(t){};", encoding="utf-8")
        (phase / "style.css").write_text(".stage{aspect-ratio:16/9}", encoding="utf-8")
        (root / "scene_plan.json").write_text(json.dumps({"phases": [data["phase"]]}), encoding="utf-8")
        assets = root / "assets"
        assets.mkdir()
        (assets / "sprite.png").write_bytes(b"fixture asset")
        (root / ".env").write_text("PRIVATE=do-not-copy", encoding="utf-8")
        return root

    def test_playlist_and_selected_phases_keep_requested_order(self):
        root = self.svg_preview()
        all_scenes = render.collect_scenes([root / "index.html"])
        self.assertEqual([s.duration for s in all_scenes], [1.25, 2.5])
        selected = render.collect_scenes([root / "phase_2.html", root / "phase_1.html"])
        self.assertEqual([s.duration for s in selected], [2.5, 1.25])

    def test_missing_phase_fails_instead_of_silently_shortening_video(self):
        root = self.svg_preview()
        (root / "phase_2.html").unlink()
        with self.assertRaisesRegex(render.PreviewError, "Thiếu phase"):
            render.collect_scenes([root])

    def test_rejects_playlist_path_traversal(self):
        root = self.svg_preview()
        (root / "index.html").write_text(
            '<script type="application/json" id="data">'
            '[{"src":"../outside.html","duration":1}]</script>', encoding="utf-8")
        with self.assertRaisesRegex(render.PreviewError, "ngoài thư mục"):
            render.collect_scenes([root])

    def test_mixed_project_copies_assets_and_hides_png_controls_without_changing_source(self):
        svg = self.svg_preview()
        png = self.png_preview()
        original = (png / "phase_1/index.html").read_bytes()
        scenes = render.collect_scenes([svg, png])
        project = self.root / "movie"
        manifest = render.prepare_project(scenes, project, 30)
        self.assertEqual(manifest["duration"], 6.75)
        self.assertEqual([s["start"] for s in manifest["scenes"]], [0, 1.25, 3.75])
        self.assertEqual((png / "phase_1/index.html").read_bytes(), original)
        copied = project / "assets/previews/source-002"
        self.assertEqual((copied / "assets/sprite.png").read_bytes(), b"fixture asset")
        self.assertIn("hyperframes-export", (copied / "phase_1/index.html").read_text())
        self.assertFalse((copied / ".env").exists())
        scene_html = (project / "compositions/scene-003.html").read_text()
        self.assertIn("registerFrameSource", scene_html)
        self.assertIn("previewReady", scene_html)
        self.assertIn("win.renderAt(time)", scene_html)
        # Rebuild an owned project without deleting unrelated review files.
        (project / "review.md").write_text("keep", encoding="utf-8")
        render.prepare_project(scenes, project, 24)
        self.assertEqual((project / "review.md").read_text(), "keep")

    def test_refuses_writing_project_into_input_or_unrelated_directory(self):
        root = self.svg_preview()
        scenes = render.collect_scenes([root])
        with self.assertRaises(render.PreviewError):
            render.prepare_project(scenes, root / "movie", 30)
        other = self.root / "other"
        other.mkdir()
        (other / "index.html").write_text("user work", encoding="utf-8")
        with self.assertRaises(render.PreviewError):
            render.prepare_project(scenes, other, 30)
        self.assertEqual((other / "index.html").read_text(), "user work")

    def test_html_stage_exports_full_frame_and_preserves_voiceover(self):
        root = self.root / "html_preview"
        root.mkdir()
        original = (
            '<html><head></head><body><main class="shell"><header>Title</header>'
            '<section><div class="stage"><div class="scene-caption">Caption</div></div>'
            '<nav>Controls</nav></section><div class="audio-direct">'
            '<audio controls src="voice.wav"></audio></div></main>'
            '<script>window.renderAt=function(t){};</script></body></html>')
        (root / "phase_1.html").write_text(original, encoding="utf-8")
        (root / "voice.wav").write_bytes(b"fixture audio")
        (root / "kich_ban.json").write_text(json.dumps({"phases": [{
            "duration": 3, "audio": {"src": "voice.wav", "duration": 2.5}}]}))
        scenes = render.collect_scenes([root])
        project = self.root / "html_movie"
        manifest = render.prepare_project(scenes, project, 30)
        copied = (project / "assets/previews/source-001/phase_1.html").read_text()
        self.assertIn('audio{display:none!important}', copied)
        self.assertIn('.stage{position:absolute!important;inset:0!important;', copied)
        self.assertIn(':not(:has(.stage))', copied)
        self.assertIn('<div class="scene-caption">Caption</div>', copied)
        self.assertEqual(manifest['audio'], 'voiceover')
        self.assertIn('id="scene-001-voiceover"', (project / 'index.html').read_text())
        self.assertEqual((project / 'assets/previews/source-001/voice.wav').read_bytes(), b'fixture audio')
        self.assertEqual((root / "phase_1.html").read_text(), original)

    def test_svg_without_stage_only_hides_audio_ui(self):
        original = ('<html><head></head><body><svg viewBox="0 0 1920 1080">'
                    '<g class="artwork"></g></svg><audio controls></audio></body></html>')
        exported = render.export_source(original)
        self.assertIn('audio{display:none!important}', exported)
        self.assertNotIn('position:absolute', exported)
        self.assertIn('<g class="artwork"></g>', exported)

    @unittest.skipUnless(shutil.which("node"), "Node is needed to exercise map scheduling")
    def test_map_export_loads_with_a_frozen_hyperframes_clock(self):
        original = ('<html><head><script src="maplibre.js"></script></head><body>'
                    '<script type="application/json" id="map-data">{}</script>'
                    '<script>const map=new maplibregl.Map({container:"map"});</script>'
                    '</body></html>')
        exported = render.export_source(original)
        self.assertLess(exported.index('id="hyperframes-map-scheduling"'),
                        exported.index('src="maplibre.js"'))
        self.assertIn('new maplibregl.Map({fadeDuration:0,', exported)
        script = exported.split('<script id="hyperframes-map-scheduling">', 1)[1].split('</script>', 1)[0]
        harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const window = {__HF_VIRTUAL_TIME__:{}};
window.performance = Object.create({now:() => 1});
window.performance.now = () => 0;
let frames = 0;
window.requestAnimationFrame = () => {}; // HyperFrames queues until first seek.
window.__HF_VIRTUAL_TIME__.originalRequestAnimationFrame = callback => { frames++; callback(0); };
vm.runInNewContext(script, {window});
window.requestAnimationFrame(() => {});
assert.equal(frames, 1); // MapLibre can initialize before the first capture.
assert.equal(window.performance.now(), 1); // Style transitions use the native clock.
vm.runInNewContext(script, {window:{}}); // Normal browser needs no adapter.
'''
        result = subprocess.run(["node", "-e", harness], input=json.dumps(script),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_duration_and_empty_input(self):
        for value in (0, -1, float("nan"), float("inf"), True, None):
            with self.subTest(value=value), self.assertRaises(render.PreviewError):
                render.positive(value, "duration")
        with self.assertRaises(render.PreviewError):
            render.collect_scenes([])

    def test_prepare_only_cli_needs_no_external_tools(self):
        root = self.svg_preview()
        with contextlib.redirect_stdout(io.StringIO()):
            result = render.main(["--input", str(root), "--output", str(self.root / "out.mp4"),
                                  "--prepare-only"])
        self.assertEqual(result, 0)
        self.assertTrue((self.root / "out_hyperframes/index.html").is_file())
        self.assertFalse((self.root / "out.mp4").exists())

    @unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the frame bridge")
    def test_frame_bridge_waits_for_map_and_checks_images_after_each_seek(self):
        scene = render.collect_scenes([self.svg_preview()])[0]
        html = render.scene_html(scene, "scene-001", "phase_1.html", 30)
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        harness = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const tick = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  const map = new EventEmitter();
  let source = '', decoded = 0, repaints = 0, load, bridge;
  map.triggerRepaint = () => { repaints++; };
  const img = {complete:true, naturalWidth:0, currentSrc:'',
    getAttribute:name => name === 'src' ? source : null,
    decode:async () => { decoded++; img.complete=true; img.naturalWidth=100; }};
  const win = {mapInstance:map, previewReady:Promise.resolve(true),
    document:{fonts:{ready:Promise.resolve()}, images:[img]},
    renderAt:time => {
      if (time === 1) { source='ok.jpg'; img.complete=false; img.naturalWidth=0; }
      if (time === 2) { source='missing.jpg'; img.complete=true; img.naturalWidth=0; }
    }};
  const iframe = {contentWindow:win, addEventListener:(type,fn) => { if(type==='load') load=fn; }};
  const window = {__timelines:{}, __hyperframes:{registerFrameSource:value => { bridge=value; }}};
  vm.runInNewContext(script, {window, setTimeout, clearTimeout,
    document:{getElementById:() => iframe}, gsap:{timeline:() => ({to:() => {}})}});
  let ready = false;
  bridge.ready.then(() => { ready=true; });
  const loaded = load();
  await tick();
  assert.equal(ready, false);
  assert.equal(repaints, 1);
  map.emit('idle');
  await loaded;
  await bridge.ready;
  assert.equal(ready, true); // Empty initial image is a valid placeholder.
  let finished = false;
  const rendered = bridge.render(1).then(() => { finished=true; });
  await tick();
  assert.equal(finished, false); // Capture must wait for the new map tiles.
  assert.equal(decoded, 0);
  map.emit('idle');
  await rendered;
  assert.equal(decoded, 1); // Decode the image that appeared during the seek.
  const broken = bridge.render(2);
  const rejected = assert.rejects(broken, /Ảnh bị thiếu: missing.jpg/);
  map.emit('idle');
  await rejected;
  const mapError = bridge.render(3);
  const failedMap = assert.rejects(mapError, /tile failed/);
  map.emit('error', {error:new Error('tile failed')});
  await failedMap;
  assert.equal(map.listenerCount('idle'), 0);
  assert.equal(map.listenerCount('error'), 0);
})().catch(error => { console.error(error); process.exitCode=1; });
'''
        result = subprocess.run(["node", "-e", harness], input=json.dumps(script),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
