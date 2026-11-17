#!/usr/bin/env python3
"""Ghép preview SVG/PNG hiện có thành một project HyperFrames và video MP4.

python3 render_hyperframes.py --input preview_samset --output videos/samset.mp4
python3 render_hyperframes.py --input preview_samset/phase_2.html \
    preview/phase_1/index.html --output videos/selected.mp4

Chỉ dùng thư viện chuẩn Python. Render cần Node.js >=22, HyperFrames >=0.9.33,
Chrome và FFmpeg. Không gọi AI, không sinh lại asset, không thêm âm thanh.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit


HYPERFRAMES_VERSION = "0.9.33"
MARKER = "flip_html.render_hyperframes.v1"


class PreviewError(ValueError):
    pass


class MetadataParser(HTMLParser):
    """Đọc JSON nhúng mà không chạy JavaScript của preview."""

    def __init__(self, source: str):
        super().__init__()
        self.blocks: dict[str, str] = {}
        self.block: str | None = None
        self.size: tuple[int, int] | None = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") == "application/json":
            self.block = attrs.get("id", "")
            self.blocks[self.block] = ""
        if tag == "svg" and self.size is None:
            values = attrs.get("viewbox", "").replace(",", " ").split()
            if len(values) == 4:
                try:
                    self.size = (int(float(values[2])), int(float(values[3])))
                except (ValueError, OverflowError):
                    pass

    def handle_data(self, data):
        if self.block is not None:
            self.blocks[self.block] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.block = None

    def data(self, key):
        try:
            return json.loads(self.blocks[key]) if key in self.blocks else None
        except json.JSONDecodeError as exc:
            raise PreviewError(f"JSON nhúng #{key} không hợp lệ: {exc}") from exc


@dataclass(frozen=True)
class Scene:
    path: Path
    preview_root: Path
    duration: float
    title: str
    size: tuple[int, int]
    kind: str


def positive(value, label: str) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise PreviewError(f"{label} phải là số dương: {value!r}") from exc
    if isinstance(value, bool) or not math.isfinite(result) or result <= 0:
        raise PreviewError(f"{label} phải là số dương hữu hạn: {value!r}")
    return result


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreviewError(f"Không đọc được {path}: {exc}") from exc


def local_path(root: Path, src: str) -> Path:
    parts = urlsplit(src)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise PreviewError(f"Preview phải là đường dẫn nội bộ: {src}")
    path = (root / unquote(parts.path)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise PreviewError(f"Preview nằm ngoài thư mục đầu vào: {src}")
    return path


def read_scene(path: Path, entry=None) -> Scene:
    if not path.is_file():
        raise PreviewError(f"Thiếu phase: {path}. Hãy sinh preview phase này trước.")
    source = path.read_text(encoding="utf-8")
    if not re.search(r"window\.renderAt\s*=", source):
        # PNG giữ renderAt trong script.js, SVG giữ inline trong HTML.
        script = path.parent / "script.js"
        if not script.is_file() or "window.renderAt" not in script.read_text(encoding="utf-8"):
            raise PreviewError(f"{path} không có window.renderAt(time).")
    meta = MetadataParser(source)
    data = meta.data("scene-data")
    is_png = isinstance(data, dict) and isinstance(data.get("phase"), dict)
    root = path.parent.parent if is_png else path.parent
    phase = data["phase"] if is_png else entry
    if not phase:
        match = re.fullmatch(r"phase_(\d+)\.html", path.name)
        script_path = root / "kich_ban.json"
        if match and script_path.is_file():
            phases = load_json(script_path).get("phases", [])
            index = int(match[1]) - 1
            if 0 <= index < len(phases):
                phase = phases[index]
        if not phase:
            duration = re.search(r"\b(?:var|let|const)\s+D\s*=\s*([\d.]+)", source)
            if duration:
                phase = {"duration": duration[1]}
    if not phase:
        raise PreviewError(f"Không tìm được thời lượng cho {path}.")
    duration = positive(phase.get("duration"), f"Thời lượng {path}")
    size = meta.size or (1920, 1080)
    if min(size) <= 0:
        raise PreviewError(f"Kích thước không hợp lệ trong {path}: {size}")
    return Scene(path, root, duration, str(phase.get("title", path.stem)),
                 size, "png" if is_png else "svg")


def collect_scenes(inputs: list[Path]) -> list[Scene]:
    scenes = []
    for given in inputs:
        path = given.expanduser().resolve()
        if not path.exists():
            raise PreviewError(f"Không tìm thấy đầu vào: {path}")
        # index.html của thư mục preview là playlist, index trong phase là scene.
        index = path / "index.html" if path.is_dir() else path
        entries = None
        if index.is_file() and index.name == "index.html":
            entries = MetadataParser(index.read_text(encoding="utf-8")).data("data")
        if isinstance(entries, list) and entries:
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("src"), str):
                    raise PreviewError(f"Playlist không hợp lệ: {index}")
                scenes.append(read_scene(local_path(index.parent, entry["src"]), entry))
        elif path.is_dir() and (path / "scene_plan.json").is_file():
            plan = load_json(path / "scene_plan.json")
            for i, phase in enumerate(plan.get("phases", []), 1):
                scenes.append(read_scene(path / f"phase_{i}" / "index.html", phase))
        elif path.is_dir() and (path / "kich_ban.json").is_file():
            script = load_json(path / "kich_ban.json")
            for i, phase in enumerate(script.get("phases", []), 1):
                scenes.append(read_scene(path / f"phase_{i}.html", phase))
        elif index.is_file():
            scenes.append(read_scene(index))
        else:
            raise PreviewError(f"{path} không phải thư mục preview hoặc file phase HTML.")
    if not scenes:
        raise PreviewError("Không có phase nào trong các preview đã chọn.")
    return scenes


def number(value: float) -> str:
    return format(value, ".12g")


def script_json(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def scene_html(scene: Scene, scene_id: str, src: str, fps: int) -> str:
    # Source iframe giữ nguyên runtime SVG/PNG; frame source chờ tải xong ảnh
    # và gọi renderAt trực tiếp, đồng bộ, trước khi HyperFrames chụp mỗi frame.
    return f'''<template>
  <style>
    #root {{ position:absolute; inset:0; background:#000; overflow:hidden; }}
    iframe {{ position:absolute; border:0; width:100%; height:100%; }}
  </style>
  <div id="root" data-composition-id="{scene_id}" data-width="{scene.size[0]}" data-height="{scene.size[1]}">
    <iframe id="{scene_id}-preview" class="clip" data-start="0" data-duration="{number(scene.duration)}"
      data-track-index="1" title="{escape(scene.title, quote=True)}"></iframe>
  </div>
  <script>
    (() => {{
      const iframe = document.getElementById("{scene_id}-preview");
      const duration = {number(scene.duration)};
      const ready = new Promise((resolve, reject) => {{
        iframe.addEventListener("error", () => reject(new Error("Không tải được preview")), {{once:true}});
        iframe.addEventListener("load", async () => {{
          try {{
            const win = iframe.contentWindow;
            if (typeof win.renderAt !== "function") throw new Error("Preview thiếu renderAt(time)");
            if (win.previewReady && await win.previewReady === false) throw new Error("Preview không tải được asset PNG");
            await win.document.fonts.ready;
            for (const img of win.document.images) {{
              if (!img.complete) await img.decode();
              if (!img.naturalWidth) throw new Error("Ảnh bị thiếu: " + img.getAttribute("src"));
            }}
            win.renderAt(0);
            resolve();
          }} catch (error) {{ reject(error); }}
        }}, {{once:true}});
        iframe.src = {script_json(src)};
      }});
      window.__hf = window.__hf || {{}};
      window.__hf.buildReady = window.__hf.buildReady || {{}};
      window.__hf.buildReady["{scene_id}"] = ready;
      window.__hyperframes.registerFrameSource({{
        element: iframe,
        ready,
        sourceRange: {{start:0, duration, fps:{fps}}},
        render(time) {{ iframe.contentWindow.renderAt(time); }}
      }});
      const clock = {{time:0}};
      const tl = gsap.timeline({{paused:true}});
      tl.to(clock, {{time:duration, duration, ease:"none"}}, 0);
      window.__timelines["{scene_id}"] = tl;
    }})();
  </script>
</template>
'''


PNG_EXPORT_STYLE = """<style id="hyperframes-export">
html,body{margin:0!important;padding:0!important;width:100%;height:100%;overflow:hidden!important;background:#000!important}
main{margin:0!important;padding:0!important;max-width:none!important;width:100%;height:100%}
main>:not(#stage){display:none!important}
#stage{position:absolute!important;left:50%;top:50%;transform:translate(-50%,-50%);width:min(100vw,177.77777778vh)!important;height:auto!important;aspect-ratio:16/9;border-radius:0!important}
</style>"""


def prepare_project(scenes: list[Scene], project: Path, fps: int) -> dict:
    project = project.resolve()
    for scene in scenes:
        if project.is_relative_to(scene.preview_root) or scene.preview_root.is_relative_to(project):
            raise PreviewError("Project HyperFrames phải nằm ngoài các thư mục preview đầu vào.")
    manifest_path = project / "preview_manifest.json"
    if project.exists() and any(project.iterdir()):
        if not manifest_path.is_file() or load_json(manifest_path).get("generator") != MARKER:
            raise PreviewError(f"Thư mục {project} đã có dữ liệu khác. Chọn --project-dir mới.")
    project.mkdir(parents=True, exist_ok=True)
    (project / "compositions").mkdir(exist_ok=True)
    roots = {}
    rows, hosts = [], []
    start = 0.0
    for i, scene in enumerate(scenes, 1):
        scene_id = f"scene-{i:03d}"
        if scene.preview_root not in roots:
            dest = project / "assets" / "previews" / f"source-{len(roots) + 1:03d}"
            dest.mkdir(parents=True, exist_ok=True)
            # Chỉ sao chép media và file runtime, không chép .env hay prompt API.
            if (scene.preview_root / "assets").is_dir():
                shutil.copytree(scene.preview_root / "assets", dest / "assets", dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns(".source", "*.meta.json", "*.txt"))
            for pattern in ("*.css", "*.js"):
                for item in scene.preview_root.glob(pattern):
                    shutil.copy2(item, dest / item.name)
            roots[scene.preview_root] = dest
        dest = roots[scene.preview_root]
        relative = scene.path.relative_to(scene.preview_root)
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if scene.kind == "png":
            for pattern in ("*.css", "*.js"):
                for item in scene.path.parent.glob(pattern):
                    shutil.copy2(item, target.parent / item.name)
        source = scene.path.read_text(encoding="utf-8")
        if scene.kind == "png":
            source = source.replace("</head>", PNG_EXPORT_STYLE + "</head>")
        target.write_text(source, encoding="utf-8")
        src = quote(target.relative_to(project).as_posix(), safe="/")
        (project / "compositions" / f"{scene_id}.html").write_text(
            scene_html(scene, scene_id, src, fps), encoding="utf-8")
        hosts.append(f'''    <div id="{scene_id}" class="clip" data-composition-id="{scene_id}"
      data-composition-src="compositions/{scene_id}.html" data-start="{number(start)}"
      data-duration="{number(scene.duration)}" data-track-index="1" data-track-kind="graphics"
      data-width="{scene.size[0]}" data-height="{scene.size[1]}"></div>''')
        rows.append({"id": scene_id, "source": str(scene.path), "title": scene.title,
                     "start": start, "duration": scene.duration, "kind": scene.kind})
        start = math.fsum([start, scene.duration])
    width, height = scenes[0].size
    html = f'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><title>Preview video</title>
<style>html,body{{margin:0;background:#000}}#root{{position:relative;width:{width}px;height:{height}px;overflow:hidden}}</style>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
</head><body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{number(start)}"
    data-width="{width}" data-height="{height}" data-fps="{fps}">
{chr(10).join(hosts)}
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{paused:true}});
    tl.to({{time:0}}, {{time:{number(start)},duration:{number(start)},ease:"none"}}, 0);
    window.__timelines.main = tl;
  </script>
</body></html>
'''
    (project / "index.html").write_text(html, encoding="utf-8")
    manifest = {"generator": MARKER, "hyperframes_version": HYPERFRAMES_VERSION,
                "duration": start, "fps": fps, "width": width, "height": height,
                "audio": "silent", "scenes": rows}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def run(command: list[str], cwd: Path):
    print("+ " + shlex.join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def verify_video(output: Path, duration: float, fps: int):
    if not output.is_file() or output.stat().st_size == 0:
        raise PreviewError(f"HyperFrames chưa tạo video hợp lệ: {output}")
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "json", str(output)], check=True, capture_output=True, text=True)
    actual = positive(json.loads(result.stdout)["format"]["duration"], "Thời lượng video")
    if abs(actual - duration) > 2 / fps + 0.01:
        raise PreviewError(f"Thời lượng MP4 {actual}s khác timeline {duration}s.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", "-i", type=Path, nargs="+", required=True,
                        help="Thư mục preview, playlist index.html hoặc từng phase; ghép đúng thứ tự nhập.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Video MP4 đầu ra.")
    parser.add_argument("--project-dir", type=Path, help="Mặc định: <output_stem>_hyperframes cạnh MP4.")
    parser.add_argument("--prepare-only", action="store_true", help="Chỉ tạo project, không cần Node/Chrome/FFmpeg.")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--quality", choices=("draft", "looks", "delivery"), default="delivery")
    parser.add_argument("--overwrite", action="store_true", help="Cho phép ghi đè MP4 đã có.")
    parser.add_argument("--hyperframes-command", default=f"npx --yes hyperframes@{HYPERFRAMES_VERSION}",
                        help="Lệnh CLI thay thế, ví dụ 'hyperframes' nếu đã cài local.")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.fps <= 240:
            raise PreviewError("--fps phải nằm trong khoảng 1–240.")
        output = args.output.expanduser().resolve()
        if output.suffix.lower() != ".mp4":
            raise PreviewError("--output phải có đuôi .mp4.")
        if output.exists() and not args.overwrite and not args.prepare_only:
            raise PreviewError(f"{output} đã tồn tại; dùng --overwrite để ghi đè.")
        scenes = collect_scenes(args.input)
        if any(output.is_relative_to(s.preview_root) for s in scenes):
            raise PreviewError("MP4 đầu ra phải nằm ngoài thư mục preview gốc.")
        project = (args.project_dir or output.with_name(output.stem + "_hyperframes")).expanduser().resolve()
        if not args.prepare_only:
            for tool in ("node", "ffmpeg", "ffprobe"):
                if not shutil.which(tool):
                    raise PreviewError(f"Thiếu {tool}. Cài Node.js >=22, Chrome và FFmpeg trước khi render.")
        manifest = prepare_project(scenes, project, args.fps)
        print(f"Project: {project}\n{len(scenes)} phase · {manifest['duration']:g}s · {args.fps} fps", flush=True)
        if args.prepare_only:
            print("Đã tạo project. Bỏ --prepare-only để kiểm tra và xuất MP4.")
            return 0
        command = shlex.split(args.hyperframes_command)
        if not command:
            raise PreviewError("--hyperframes-command không được rỗng.")
        run(command + ["check", "--json"], project)
        midpoints = ",".join(number(s["start"] + s["duration"] / 2) for s in manifest["scenes"])
        run(command + ["snapshot", "--at", midpoints], project)
        output.parent.mkdir(parents=True, exist_ok=True)
        run(command + ["render", "--fps", str(args.fps), "--quality", args.quality,
                       "--output", str(output)], project)
        verify_video(output, manifest["duration"], args.fps)
        print(f"Video hoàn chỉnh: {output}")
        return 0
    except (PreviewError, OSError, subprocess.CalledProcessError, KeyError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
