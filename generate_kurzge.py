"""Dựng video preview HTML từ kịch bản JSON của plant_kurzge.py.

API generate_image vẽ thư viện PNG chung; AI dàn cảnh và diễn hoạt mọi phase.
Trình phát ghép các phase theo timeline, có Play/Pause và tua, không có phụ đề.

python generate_kurzge.py --script kich_ban.json --output preview
python generate_kurzge.py --input noi_dung.txt --output preview_moi
python generate_kurzge.py --resume --phase 2 --redo
python generate_kurzge.py --resume
"""

import argparse
import html
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

from plant_kurzge import ROOT, generate_script, request_text, validate
import image_motion_ai as general

WIDTH, HEIGHT = 1920, 1080
BACKGROUND = "#153e8c"
MAX_SVG_BYTES = 250_000
MAX_ATTEMPTS = 3
ET.register_namespace("", "http://www.w3.org/2000/svg")

# SVG do AI trả về là dữ liệu không tin cậy: không script, không tài nguyên ngoài.
FORBIDDEN = re.compile(
    r"<\s*(?:script|foreignObject|iframe|object|embed|link|image|animate\w*|set)\b"
    r"|\son[a-z]+\s*=|javascript:|@import"
    r"|url\(\s*[\"']?(?!#)|href\s*=\s*[\"'](?!#)",
    re.I,
)

PHASE_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
<title><<TITLE>></title>
<style>html,body{margin:0;height:100%;background:<<BACKGROUND>>;overflow:hidden}svg{width:100%;height:100%;display:block}svg text{font-family:"Be Vietnam Pro",system-ui,sans-serif}</style>
</head><body><<SVG>>
<script>
var D=<<DURATION>>,manual=false,requestedTime=0;
function seek(t){t=Number.isFinite(t)?Math.max(0,Math.min(D,t)):0;requestedTime=t;document.getAnimations().forEach(function(a){a.pause();a.currentTime=t*1000})}
window.renderAt=function(t){manual=true;seek(t)};
window.previewReady=Promise.all([document.fonts.ready].concat(Array.from(document.querySelectorAll('svg image')).map(function(node){return new Promise(function(resolve,reject){var img=new Image();img.onload=resolve;img.onerror=function(){reject(new Error('Không tải được asset PNG'))};img.src=node.getAttribute('href')})}))).then(function(){seek(requestedTime);return true});
addEventListener("message",function(e){if(e.source===parent&&e.data&&Number.isFinite(e.data.t))seek(e.data.t)});
if(parent===window){var s=performance.now();(function f(n){if(!manual)seek(((n-s)/1000)%D);requestAnimationFrame(f)})(s)}else{seek(0)}
</script></body></html>
"""

INDEX_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><<TITLE>></title>
<style>
:root{--bg:#eef4fb;--fg:#12337a;--bar:#cfdcef;--btn:#12337a;--btnfg:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#0b1630;--fg:#dce8ff;--bar:#22345e;--btn:#4fb3e8;--btnfg:#08183a}}
body{box-sizing:border-box;min-height:100vh;margin:0;padding:16px;background:var(--bg);color:var(--fg);font-family:"Be Vietnam Pro",system-ui,sans-serif;display:flex;align-items:center;justify-content:center}
main{width:100%;max-width:960px}
.stage{position:relative;aspect-ratio:16/9;border-radius:16px;overflow:hidden;background:<<BACKGROUND>>}
.stage iframe{position:absolute;inset:0;width:100%;height:100%;border:0;visibility:hidden}
.ctl{display:flex;align-items:center;gap:12px;margin-top:12px}
button{font:inherit;font-weight:800;border:0;border-radius:999px;padding:8px 18px;background:var(--btn);color:var(--btnfg);cursor:pointer}
input[type=range]{flex:1}
output{min-width:95px;text-align:right;font-variant-numeric:tabular-nums}
button:focus-visible{outline:3px solid var(--fg);outline-offset:2px}
@media(max-width:480px){.ctl{gap:6px}button{padding:8px 12px}input[type=range]{min-width:0}output{font-size:.8rem;min-width:80px}}
</style></head><body><main>
<div class="stage" id="stage"></div>
<div class="ctl"><button id="play">Tạm dừng</button>
<input id="seek" type="range" min="0" max="<<TOTAL>>" step="0.01" value="0" aria-label="Thời gian">
<output id="clock"></output></div>
</main>
<script type="application/json" id="data"><<DATA>></script>
<script>
var phases=JSON.parse(document.getElementById("data").textContent);
var total=phases.reduce(function(s,p){return s+p.duration},0);
var stage=document.getElementById("stage"),btn=document.getElementById("play"),seek=document.getElementById("seek"),
clock=document.getElementById("clock");
var frames=phases.map(function(p){var f=document.createElement("iframe");f.setAttribute("sandbox","allow-scripts");f.src=p.src;f.title=p.title;stage.appendChild(f);return f});
var t=0,playing=!phases.some(function(p){return p.audio}),last=performance.now(),shown=-1,shownStart=0;
var audios=phases.map(function(p){if(!p.audio)return null;var a=new Audio(p.audio.src);a.preload="auto";return a});
btn.textContent=playing?"Tạm dừng":"Phát";
function playAudio(){var a=audios[shown];if(a&&playing)a.play().catch(function(){playing=false;btn.textContent="Phát"})}
function render(){
  var acc=0,i=0;
  while(i<phases.length-1&&t>=acc+phases[i].duration){acc+=phases[i].duration;i++}
  if(i!==shown){audios.forEach(function(a){if(a)a.pause()});frames.forEach(function(f,k){f.style.visibility=k===i?"visible":"hidden"});shown=i;shownStart=acc;if(audios[i])audios[i].currentTime=Math.min(t-acc,phases[i].audio.duration);playAudio()}
  var w=frames[i].contentWindow;if(w)w.postMessage({t:Math.min(t-acc,phases[i].duration)},"*");
  seek.value=t;clock.textContent=t.toFixed(1)+" / "+total.toFixed(1)+" s";
}
function tick(now){var dt=(now-last)/1000;last=now;if(playing){var a=audios[shown];t=a&&!a.ended?shownStart+a.currentTime:t+dt;if(t>=total){t=total;playing=false;audios.forEach(function(a){if(a)a.pause()});btn.textContent="Phát"}}render();requestAnimationFrame(tick)}
btn.onclick=function(){if(t>=total)window.renderAt(0);playing=!playing;btn.textContent=playing?"Tạm dừng":"Phát";if(playing)playAudio();else audios.forEach(function(a){if(a)a.pause()})};
window.renderAt=function(value){t=Math.max(0,Math.min(total,value));render();var a=audios[shown];if(a)a.currentTime=Math.min(t-shownStart,phases[shown].audio.duration)};
seek.oninput=function(){window.renderAt(parseFloat(seek.value));last=performance.now()};
frames.forEach(function(f){f.addEventListener("load",render)});
render();
requestAnimationFrame(tick);
</script></body></html>
"""


def clean_svg(raw, *, require_animation=True):
    """Trích và kiểm tra SVG; ném ValueError kèm lý do để yêu cầu AI sửa."""
    raw = re.sub(r"^```(?:svg|xml|html)?\s*|\s*```$", "", raw.strip())
    match = re.search(r"<svg\b.*</svg>", raw, re.S | re.I)
    if not match:
        raise ValueError("Không tìm thấy thẻ <svg>.")
    svg = match.group(0)
    if len(svg.encode("utf-8")) > MAX_SVG_BYTES:
        raise ValueError(f"SVG quá lớn (tối đa {MAX_SVG_BYTES} byte); đơn giản hóa hình.")
    bad = FORBIDDEN.search(svg)
    if bad:
        raise ValueError(f"SVG chứa phần tử/thuộc tính không được phép: {bad.group(0).strip()}")
    if require_animation and "@keyframes" not in svg:
        raise ValueError("SVG chưa có animation CSS (@keyframes).")
    head = re.match(r"<svg\b[^>]*>", svg).group(0)
    fixed = head
    if "xmlns=" not in fixed:
        fixed = fixed.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if "viewBox" not in fixed:
        fixed = fixed.replace("<svg", f'<svg viewBox="0 0 {WIDTH} {HEIGHT}"', 1)
    svg = fixed + svg[len(head):]
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as error:
        raise ValueError(f"SVG không phải XML hợp lệ: {error}") from error
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Gốc phải là SVG namespace chuẩn.")
    return ET.tostring(root, encoding="unicode")


def select_renderer(script, requested="auto"):
    if requested not in {"auto", "ai"}:
        raise ValueError("Chỉ hỗ trợ renderer auto hoặc ai (cùng dùng generate_image).")
    return "image"


def write_phase(output, index, phase, svg, script, *, background=BACKGROUND):
    (output / f"phase_{index}.svg").write_text(svg + "\n", encoding="utf-8")
    title = html.escape(f"Phase {index} - {phase.get('name', '')}")
    page = (PHASE_HTML.replace("<<TITLE>>", title).replace("<<SVG>>", svg)
            .replace("<<BACKGROUND>>", background)
            .replace("<<DURATION>>", f"{phase['duration']:g}"))
    if phase.get('audio'):
        data = json.dumps({'phase': phase, 'renderer': general.VERSION}, ensure_ascii=False).replace('<', '\\u003c')
        page = page.replace('</head>', '<script type="application/json" id="scene-data">' + data + '</script></head>')
    (output / f"phase_{index}.html").write_text(page, encoding="utf-8")


def write_index(script, output, fingerprint=None):
    entries = []
    for index, phase in enumerate(script["phases"], 1):
        page_path = output / f"phase_{index}.html"
        if page_path.is_file():
            page_source = page_path.read_text(encoding="utf-8")
            if fingerprint and f'data-fingerprint="{fingerprint}"' not in page_source:
                continue
            entries.append({"src": f"phase_{index}.html", "title": phase.get("name", f"Phase {index}"),
                            "duration": phase["duration"],
                            **({'audio': phase['audio']} if phase.get('audio') else {})})
    if not entries:
        return None
    data = json.dumps(entries, ensure_ascii=False).replace("<", "\\u003c")
    total = sum(e["duration"] for e in entries)
    page = (INDEX_HTML.replace("<<TITLE>>", html.escape(script.get("title", "Video preview")))
            .replace("<<TOTAL>>", f"{total:g}").replace("<<DATA>>", data)
            .replace("<<BACKGROUND>>", BACKGROUND))
    path = output / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def build_preview(script, output, request, *, style_context=None, on_progress=None,
                  resume=True, redo=False, phase_number=None, plan_only=False, renderer="auto"):
    """Shared CLI/web pipeline. Never generates a new screenplay."""
    errors = validate(script)
    if errors:
        raise ValueError("Kịch bản không hợp lệ: " + "; ".join(errors))
    output.mkdir(parents=True, exist_ok=True)
    if style_context and style_context['id'] == '3d-motion-infographic':
        from three_motion import ScenePlan, build_preview as build_three
        if phase_number is not None:
            raise ValueError('Style 3D hiện dựng toàn bộ cảnh; hãy bỏ --phase.')
        if plan_only:
            (output / 'prompts').mkdir(exist_ok=True)
            (output / 'prompts' / 'scene_schema.json').write_text(
                json.dumps(ScenePlan.model_json_schema(), ensure_ascii=False, indent=2), encoding='utf-8')
            (output / 'render_config.json').write_text(json.dumps(style_context, ensure_ascii=False), encoding='utf-8')
            return
        if any(p.get('voiceover') and not p.get('audio') for p in script['phases']):
            from backend.narration import prepare_narration
            prepare_narration(script, output, output.parent / 'audio_cache', on_progress)
            (output / 'kich_ban.json').write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')
        references = json.loads((output / 'references.json').read_text()) if (output / 'references.json').exists() else []
        return build_three(script, output, request, style_context=style_context, references=references,
                           on_progress=on_progress, redo=redo or not resume)
    phases = script['phases']
    background = BACKGROUND
    if style_context is not None:
        from render_style import caption_colors
        background = caption_colors(style_context)[0]
        (output / 'render_config.json').write_text(
            json.dumps(style_context, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    selected = [phase_number] if phase_number else range(1, len(phases) + 1)
    renderer = select_renderer(script, renderer)
    print(f"  Renderer: {renderer}.", flush=True)
    ai = general.Renderer(script, output, request, clean_svg, style_context=style_context, on_progress=on_progress).prepare() if not plan_only else None
    if plan_only:
        general.write_asset_prompts(script, output, style_context)
    if on_progress:
        on_progress('phases', 0, len(selected))
    for done, index in enumerate(selected, 1):
        phase = phases[index - 1]
        svg_path = output / f"phase_{index}.svg"
        reference_index = phase.get("branch_from") or index - 1
        previous = output / f"phase_{reference_index}.svg"
        previous_svg = previous.read_text(encoding="utf-8") if index > 1 and previous.is_file() else None
        if plan_only:
            prompts = output / "prompts"
            prompts.mkdir(exist_ok=True)
            prompt = general.phase_prompt(script, index, general.prompt_library(script), previous_svg, style_context=style_context)
            (prompts / f"phase_{index}.txt").write_text(prompt, encoding="utf-8")
            print(f"  Phase {index}: đã lưu prompt.", flush=True)
            continue
        if resume and not redo and svg_path.is_file():
            try:
                cached = svg_path.read_text(encoding="utf-8")
                if f'data-fingerprint="{ai.fingerprint}"' not in cached:
                    raise ValueError("Cache khác kịch bản/thư viện/phiên bản đồ họa.")
                svg = ai.clean_phase(cached, index)
                write_phase(output, index, phase, svg, script, background=background)
                print(f"  Phase {index}: dùng bản đã vẽ.", flush=True)
                if on_progress:
                    on_progress('phases', done, len(selected))
                continue
            except (ValueError, ET.ParseError):
                print(f"  Phase {index}: bản cũ không hợp lệ, vẽ lại.", flush=True)
        print(f"  Phase {index}: {phase.get('name', '')} ({phase['duration']:g}s) - đang vẽ…", flush=True)
        if previous_svg and f'data-fingerprint="{ai.fingerprint}"' not in previous_svg:
            previous_svg = None
        write_phase(output, index, phase, ai.render(index, previous_svg), script, background=background)
        if on_progress:
            on_progress('phases', done, len(selected))

    if plan_only:
        print(f"Đã lưu kịch bản và prompt tại {output}.")
        return
    index_path = write_index(script, output, ai.fingerprint if ai else None)
    print(f"Mở {index_path} để Play/Pause và tua." if index_path else "Chưa có phase nào được dựng.")

    return ai.fingerprint if ai else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--script", type=Path, help="File kịch bản JSON đã lưu từ plant_kurzge.py.")
    sources.add_argument("--input", type=Path,
                         help="File nội dung: gọi AI sinh kịch bản và tự chọn thời lượng, sau đó dựng preview.")
    parser.add_argument("--renderer", choices=("auto", "ai"), default="auto",
                        help="auto/ai: sinh PNG qua generate_image và diễn hoạt toàn bộ phase.")
    parser.add_argument("--style", help="ID phong cách trong skills/styles/; bỏ qua để giữ cách chạy hiện có.")
    parser.add_argument("--plan-only", action="store_true", help="Chỉ lưu prompt ảnh và dàn cảnh, chưa gọi API.")
    sources.add_argument("--resume", action="store_true", help="Tiếp tục: dùng kịch bản và các phase đã vẽ trong output.")
    parser.add_argument("--redo", action="store_true", help="Vẽ lại cả phase đã có (dùng với --phase).")
    parser.add_argument("--phase", type=int, help="Chỉ dựng phase này (đánh số từ 1); bỏ qua để dựng tất cả.")
    parser.add_argument("--output", type=Path, default=ROOT / "preview")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if args.phase is not None and args.phase < 1:
        parser.error("--phase phải từ 1 trở lên.")
    script_path = output / "kich_ban.json"
    if output.exists() and any(output.iterdir()) and not args.resume:
        # Repeating the same command can migrate an SVG preview and reuse image cache.
        try:
            same_script = args.script is not None and json.loads(args.script.read_text(encoding="utf-8")) == json.loads(script_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            same_script = False
        if not same_script:
            parser.error(f"{output} đã có dữ liệu khác. Dùng --resume hoặc chọn --output khác.")
        args.resume = True
        print("Đã có cùng kịch bản trong output; tiếp tục và kiểm tra cache…", flush=True)
    source = script_path if args.resume else (args.input or args.script)
    if not source.is_file():
        parser.error(f"Không tìm thấy file: {source}.")
    content = source.read_text(encoding="utf-8")
    if args.input:
        print("Đang phân tích nội dung; AI tự quyết định thời lượng kịch bản…", flush=True)
        script = generate_script(content)
    else:
        script = json.loads(content)
    errors = validate(script)
    if errors:
        raise ValueError("Kịch bản không hợp lệ:\n- " + "\n- ".join(errors))
    phases = script["phases"]
    if args.phase is not None and args.phase > len(phases):
        parser.error(f"Kịch bản chỉ có {len(phases)} phase.")
    output.mkdir(parents=True, exist_ok=True)
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{script.get('title', '')}: {len(phases)} phase, {sum(p['duration'] for p in phases):g} giây.", flush=True)

    from render_style import load_render_style
    config_path = output / 'render_config.json'
    style_context = (load_render_style(args.style) if args.style else
                     json.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else None)
    build_preview(script, output, request_text, style_context=style_context,
                  resume=args.resume, redo=args.redo, phase_number=args.phase,
                  plan_only=args.plan_only, renderer=args.renderer)


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"API trả HTTP {error.code}. Kiểm tra URL, khóa, model; chạy --resume để tiếp tục.")
    except (URLError, TimeoutError, ValueError, OSError) as error:
        raise SystemExit(f"Lỗi: {error}")
