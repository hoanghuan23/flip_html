"""Dựng video preview HTML từ kịch bản JSON của analyze_text_test.py.

Mỗi phase là một SVG Flat do AI vẽ, chuyển động bằng CSS animation. Trình phát ghép
các phase theo timeline, có Play/Pause, tua và phụ đề.

python generate_preview_test.py --script kich_ban.json --output preview
python generate_preview_test.py --resume --phase 2 --redo
python generate_preview_test.py --resume
"""

import argparse
import html
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

from analyze_text_test import ROOT, request_text, validate

WIDTH, HEIGHT = 1920, 1080
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

PHASE_PROMPT = """
Bạn là họa sĩ motion graphics Flat 2D (kiểu Kurzgesagt - In a Nutshell).
Vẽ MỘT phase của video bằng SVG + CSS animation.
Chỉ trả về MỘT phần tử <svg>, không markdown, không giải thích.

KHUNG
- <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">, gốc (0,0) ở góc trên trái.
- Phase dài <<DURATION>> giây. Thời gian trong CSS là giây tuyệt đối, từ 0 đến <<DURATION>>.

PHONG CÁCH
- Flat: hình học, màu đặc, không viền đen, không gradient phức tạp, bóng đổ phẳng.
- Chỉ dùng màu trong bảng màu bên dưới (được phép đổi độ mờ).
- Nền và dòng chảy đã được chương trình vẽ sẵn, KHÔNG vẽ lại biển, cát hay dải dòng chảy.
  Dải nước xanh đậm ở giữa khung là dòng chảy; mũi tên chỉ phụ trợ, không thay dải nước.
- Giữ góc nhìn top-down ở tất cả phase. Không vẽ hình người mới. Nhân vật được lắp
  từ đúng sáu <use>: href="#swimmer-head", "#swimmer-torso", "#swimmer-arm-left",
  "#swimmer-arm-right", "#swimmer-leg-left", "#swimmer-leg-right";
  giữ nguyên kích thước, màu và tỷ lệ của từng phần. Chỉ xoay/dịch chuyển các bộ phận.
- Nội dung vẽ riêng của phase phải đặt trong <g id="artwork">. Đặt <g id="swimmer">
  ngay sau artwork, trực tiếp dưới <svg>, để nhân vật luôn nằm trên dải nước.
  Nếu vẽ cảnh báo, đặt
  TOÀN BỘ biểu tượng trong <g id="warning">. Phase thoát hiểm và nhánh cầu cứu
  không có biểu tượng cảnh báo.
- Sóng phải bị ngắt ở dải dòng chảy giữa khung; không vẽ dải bọt xuyên qua dải nước.
- Nền chuẩn: biển sâu y=0..250; nước nông y=250..795; cát bắt đầu quanh y=770.
  Dải dòng chảy xanh đậm ở x=885..1035, y=175..780. Chừa hành lang
  x=885..1035 khi vẽ bọt sóng. Nhân vật chỉ có một mẫu chung được chương trình chèn.

CHUYỂN ĐỘNG
- Chỉ dùng CSS đặt trong thẻ <style> bên trong <svg>: @keyframes + animation.
- Chỉ animate transform (translate, rotate, scale) và opacity. translate dùng đơn vị px
  (bằng đơn vị viewBox). Mỗi phần tử chuyển động cần transform-box: fill-box và
  transform-origin rõ ràng.
- Vị trí đặt ban đầu: bọc <g transform="translate(x,y)"> tĩnh bên ngoài, đặt phần tử
  animate bên trong (CSS transform sẽ ghi đè thuộc tính transform của chính phần tử đó).
- Mọi animation có animation-fill-mode: both, animation-delay và animation-duration
  theo timeline của actions. Animation không lặp phải kết thúc trước hoặc đúng giây <<DURATION>>.
  Hiệu ứng lặp (sóng, mũi tên, dòng chảy) dùng animation-iteration-count: infinite.
- Trạng thái tại t=0 đúng initial_state; tại t=<<DURATION>> đúng final_state.
  Phần tử xuất hiện giữa chừng bắt đầu với opacity 0.
- Tuyệt đối không dùng: script, JS, SMIL (<animate>, <set>), foreignObject, image,
  @import, URL ngoài, animation-play-state.
- Không tự tạo <defs>; sáu bộ phận nhân vật và nền được chương trình thêm vào SVG.
- BẮT BUỘC có <g id="swimmer"> chứa đúng một <use> cho MỖI bộ phận nói trên.
  Nhóm cha giữ vị trí; mỗi <use> có thể đặt trong <g> riêng để xoay tay/chân.
  Không vẽ circle/path/rect/polygon nhân vật bên ngoài các <use>.

CHỮ
- KHÔNG vẽ phụ đề hoặc lời bình (trình phát tự hiển thị).
- Nhãn ngắn trên hình (tối đa 3 từ) được phép, dùng <text> với
  font-family="Be Vietnam Pro, system-ui, sans-serif".

BẢNG MÀU VÀ PHONG CÁCH CHUNG
<<STYLE>>

DANH SÁCH ASSET
<<ASSETS>>

NỀN VÀ MẪU NHÂN VẬT CHUNG (chỉ tham khảo, KHÔNG trả lại trong SVG)
<<SHARED_SCENE>>

PHASE CẦN VẼ
<<PHASE>>
<<PREVIOUS>>
"""

# Cùng một hình học, cùng một mẫu nhân vật được gắn vào mọi SVG sau khi AI vẽ.
# Nền phủ kín canvas nên cả khe giữa sóng và cát cũng không lộ màu đen của iframe.
SWIMMER_PARTS = ("head", "torso", "arm-left", "arm-right", "leg-left", "leg-right")


def palette_color(script, key, fallback):
    palette = script.get("style", {}).get("palette", {})
    value = next((value for name, value in palette.items() if key in name.lower()), fallback)
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"Màu palette cho '{key}' phải là mã #RRGGBB.")
    return value


def shared_scene(script):
    deep = palette_color(script, "sâu", "#1769AA")
    shallow = palette_color(script, "nông", "#5CC8E8")
    sand = palette_color(script, "cát", "#F4D35E")
    person = palette_color(script, "nhân vật", "#FF6B6B")
    face = palette_color(script, "chữ", "#17324D")
    return f'''<g id="shared-scene">
  <rect id="full-background" x="0" y="0" width="1920" height="1080" fill="{deep}"/>
  <path id="shallow-water" d="M0 250 H1920 V795 H0 Z" fill="{shallow}"/>
  <path id="shore" d="M0 770 Q480 750 960 770 T1920 770 V1080 H0 Z" fill="{sand}"/>
</g>
<defs id="shared-character">
  <g id="swimmer-head"><circle cx="0" cy="-43" r="29" fill="{person}"/><circle cx="-9" cy="-48" r="3" fill="{face}"/><circle cx="9" cy="-48" r="3" fill="{face}"/></g>
  <g id="swimmer-torso"><ellipse cx="0" cy="28" rx="34" ry="55" fill="{person}"/></g>
  <g id="swimmer-arm-left"><rect x="-51" y="-8" width="18" height="85" rx="9" fill="{person}"/></g>
  <g id="swimmer-arm-right"><rect x="33" y="-8" width="18" height="85" rx="9" fill="{person}"/></g>
  <g id="swimmer-leg-left"><rect x="-23" y="73" width="18" height="75" rx="9" fill="{person}"/></g>
  <g id="swimmer-leg-right"><rect x="5" y="73" width="18" height="75" rx="9" fill="{person}"/></g>
</defs>'''


def current_overlay(script):
    deep = palette_color(script, "sâu", "#1769AA")
    return ET.fromstring(
        f'<path xmlns="http://www.w3.org/2000/svg" id="rip-current" '
        f'd="M885 780 C905 620 905 480 905 330 L925 175 H995 L1015 330 '
        f'C1015 480 1015 620 1035 780 Z" fill="{deep}"/>')

PHASE_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title><<TITLE>></title>
<style>html,body{margin:0;height:100%;background:<<BACKGROUND>>;overflow:hidden}svg{width:100%;height:100%;display:block}</style>
</head><body><<SVG>>
<script>
var D=<<DURATION>>;
function seek(t){document.getAnimations().forEach(function(a){a.pause();a.currentTime=t*1000})}
addEventListener("message",function(e){if(e.data&&typeof e.data.t==="number")seek(e.data.t)});
if(parent===window){var s=performance.now();(function f(n){seek(((n-s)/1000)%D);requestAnimationFrame(f)})(s)}else{seek(0)}
</script></body></html>
"""

INDEX_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><<TITLE>></title>
<style>
:root{--bg:#eef4fb;--fg:#12337a;--bar:#cfdcef;--btn:#12337a;--btnfg:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#0b1630;--fg:#dce8ff;--bar:#22345e;--btn:#4fb3e8;--btnfg:#08183a}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font-family:"Be Vietnam Pro",system-ui,sans-serif;display:flex;justify-content:center}
main{width:100%;max-width:960px}
h1{font-size:1.2rem;margin:0 0 10px}
.stage{position:relative;aspect-ratio:16/9;border-radius:16px;overflow:hidden;background:<<BACKGROUND>>}
.stage iframe{position:absolute;inset:0;width:100%;height:100%;border:0;visibility:hidden}
.ctl{display:flex;align-items:center;gap:12px;margin-top:12px}
button{font:inherit;font-weight:800;border:0;border-radius:999px;padding:8px 18px;background:var(--btn);color:var(--btnfg);cursor:pointer}
input[type=range]{flex:1}
output{min-width:110px;text-align:right;font-variant-numeric:tabular-nums}
#cap{font-weight:800;font-size:1.15rem;margin:12px 0 4px;min-height:1.5em}
#nar{opacity:.8;min-height:3em;margin:0}
</style></head><body><main>
<h1><<TITLE>></h1>
<div class="stage" id="stage"></div>
<div class="ctl"><button id="play">Tạm dừng</button>
<input id="seek" type="range" min="0" max="<<TOTAL>>" step="0.01" value="0" aria-label="Thời gian">
<output id="clock"></output></div>
<p id="cap"></p><p id="nar"></p>
</main>
<script type="application/json" id="data"><<DATA>></script>
<script>
var phases=JSON.parse(document.getElementById("data").textContent);
var total=phases.reduce(function(s,p){return s+p.duration},0);
var stage=document.getElementById("stage"),btn=document.getElementById("play"),seek=document.getElementById("seek"),
clock=document.getElementById("clock"),cap=document.getElementById("cap"),nar=document.getElementById("nar");
var frames=phases.map(function(p){var f=document.createElement("iframe");f.setAttribute("sandbox","allow-scripts");f.src=p.src;f.title=p.title;stage.appendChild(f);return f});
var t=0,playing=true,last=performance.now(),shown=-1;
function render(){
  var acc=0,i=0;
  while(i<phases.length-1&&t>=acc+phases[i].duration){acc+=phases[i].duration;i++}
  if(i!==shown){frames.forEach(function(f,k){f.style.visibility=k===i?"visible":"hidden"});cap.textContent=phases[i].caption;nar.textContent=phases[i].narration;shown=i}
  var w=frames[i].contentWindow;if(w)w.postMessage({t:Math.min(t-acc,phases[i].duration)},"*");
  seek.value=t;clock.textContent=t.toFixed(1)+" / "+total.toFixed(1)+" s";
}
function tick(now){var dt=(now-last)/1000;last=now;if(playing){t+=dt;if(t>=total)t=0}render();requestAnimationFrame(tick)}
btn.onclick=function(){playing=!playing;btn.textContent=playing?"Tạm dừng":"Phát"};
seek.oninput=function(){t=parseFloat(seek.value);render()};
requestAnimationFrame(tick);
</script></body></html>
"""


def clean_svg(raw, script=None, index=None):
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
    if "@keyframes" not in svg:
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
    if script is not None:
        ns = {"s": "http://www.w3.org/2000/svg"}
        artwork = root.find("s:g[@id='artwork']", ns)
        if artwork is None:
            raise ValueError("Thiếu <g id='artwork'> chứa nét vẽ riêng của phase.")
        swimmer = root.find("s:g[@id='swimmer']", ns)
        if swimmer is None:
            raise ValueError("Thiếu <g id='swimmer'> trực tiếp dưới SVG.")
        uses = [e.get("href") or e.get("{http://www.w3.org/1999/xlink}href")
                for e in swimmer.iter() if e.tag.endswith("}use")]
        expected = [f"#swimmer-{part}" for part in SWIMMER_PARTS]
        if sorted(uses) != sorted(expected):
            raise ValueError("Nhân vật phải dùng đúng sáu <use> của mẫu chung, mỗi bộ phận một lần.")
        if any(e.tag.rsplit("}", 1)[-1] not in {"g", "use"} for e in swimmer.iter()):
            raise ValueError("Nhân vật chứa hình vẽ mới; chỉ dùng <g> và <use> từ mẫu chung.")
        for element in list(root):
            if element.get("id") in {"shared-scene", "shared-character", "rip-current"}:
                root.remove(element)
        for element in root:
            tag = element.tag.rsplit("}", 1)[-1]
            if tag not in {"style", "g", "title", "desc"}:
                raise ValueError("Chỉ đặt style, artwork và swimmer trực tiếp dưới SVG.")
            if tag == "g" and element.get("id") not in {"artwork", "swimmer"}:
                raise ValueError("Không vẽ thêm nền/nhân vật ở ngoài artwork.")
        person_color = palette_color(script, "nhân vật", "#FF6B6B").lower()
        warning_color = palette_color(script, "cảnh báo", "#F4A261").lower()
        for element in artwork.iter():
            if element.get("id") in {"shared-scene", "shared-character", "rip-current", "swimmer"}:
                raise ValueError("Artwork dùng trùng ID của nền hoặc nhân vật chung.")
            if element.get("fill", "").lower() == person_color:
                raise ValueError("Không vẽ nhân vật mới trong artwork; dùng sáu bộ phận chung.")
            if element.tag.rsplit("}", 1)[-1] == "rect":
                if element.get("width") in {"1920", "100%"} and element.get("height") in {"1080", "100%"}:
                    raise ValueError("Không vẽ nền phủ khung trong artwork; nền dùng chung đã có.")
        if index is not None and index >= len(script["phases"]) - 1:
            if artwork.find(".//s:g[@id='warning']", ns) is not None:
                raise ValueError("Phase thoát hiểm/cầu cứu không được giữ biểu tượng cảnh báo.")
            if any(element.get("fill", "").lower() == warning_color for element in artwork.iter()):
                raise ValueError("Phase thoát hiểm/cầu cứu còn dùng màu biểu tượng cảnh báo.")
        scene = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{shared_scene(script)}</svg>')
        # Chèn nền trước artwork; defs của nhân vật được dùng chung cho mọi phase.
        for element in reversed(list(scene)):
            root.insert(0, element)
        root.insert(list(root).index(swimmer), current_overlay(script))
        svg = ET.tostring(root, encoding="unicode")
    return svg


def phase_prompt(script, index, previous_svg=None):
    phase = script["phases"][index - 1]
    spec = {k: phase.get(k) for k in
            ("id", "name", "duration", "caption", "narration", "camera",
             "initial_state", "final_state", "actions")}
    previous = ""
    if index > 1:
        branch = phase.get("branch_from")
        before = script["phases"][(branch or index - 1) - 1]
        if branch:
            previous = (f"\nĐÂY LÀ NHÁNH KHÁC từ cuối phase {branch}, KHÔNG tiếp sau phase {index - 1}. "
                        "Mở bằng tình huống 'nếu chưa thoát được' và chỉ sau đó nổi/vẫy tay/kêu cứu.\n")
        else:
            previous = "\nNối liên tục từ cuối phase trước.\n"
        previous += f"Trạng thái tham chiếu: {before.get('final_state', '')}\n"
        if previous_svg:
            previous += "SVG tham chiếu (chỉ tham khảo vị trí/timeline, dùng mẫu nhân vật chung):\n" + previous_svg[:12000] + "\n"
    return (PHASE_PROMPT
            .replace("<<DURATION>>", f"{phase['duration']:g}")
            .replace("<<STYLE>>", json.dumps(script.get("style", {}), ensure_ascii=False, indent=1))
            .replace("<<ASSETS>>", json.dumps(script.get("assets", []), ensure_ascii=False, indent=1))
            .replace("<<SHARED_SCENE>>", shared_scene(script))
            .replace("<<PHASE>>", json.dumps(spec, ensure_ascii=False, indent=1))
            .replace("<<PREVIOUS>>", previous))


def generate_phase(script, index, previous_svg=None):
    prompt = phase_prompt(script, index, previous_svg)
    error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        feedback = f"\n\nLẦN TRƯỚC BỊ LỖI: {error}\nTrả lại SVG đầy đủ đã sửa." if error else ""
        raw = request_text(prompt + feedback)
        try:
            return clean_svg(raw, script, index)
        except ValueError as problem:
            error = str(problem)
            print(f"  Lần {attempt}: {error}", flush=True)
    raise ValueError(f"Phase {index} không đạt kiểm tra SVG: {error}")


def write_phase(output, index, phase, svg, script):
    (output / f"phase_{index}.svg").write_text(svg + "\n", encoding="utf-8")
    title = html.escape(f"Phase {index} - {phase.get('name', '')}")
    page = (PHASE_HTML.replace("<<TITLE>>", title).replace("<<SVG>>", svg)
            .replace("<<BACKGROUND>>", palette_color(script, "sâu", "#1769AA"))
            .replace("<<DURATION>>", f"{phase['duration']:g}"))
    (output / f"phase_{index}.html").write_text(page, encoding="utf-8")


def write_index(script, output):
    entries = []
    for index, phase in enumerate(script["phases"], 1):
        if (output / f"phase_{index}.html").is_file():
            caption = phase.get("caption", "")
            if phase.get("branch_from"):
                caption = "Tình huống khác: " + caption
            entries.append({"src": f"phase_{index}.html", "title": phase.get("name", f"Phase {index}"),
                            "duration": phase["duration"], "caption": caption,
                            "narration": phase.get("narration", "")})
    if not entries:
        return None
    data = json.dumps(entries, ensure_ascii=False).replace("<", "\\u003c")
    total = sum(e["duration"] for e in entries)
    page = (INDEX_HTML.replace("<<TITLE>>", html.escape(script.get("title", "Video preview")))
            .replace("<<TOTAL>>", f"{total:g}").replace("<<DATA>>", data)
            .replace("<<BACKGROUND>>", palette_color(script, "sâu", "#1769AA")))
    path = output / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=Path, help="File kịch bản JSON đã lưu từ analyze_text.py.")
    parser.add_argument("--plan-only", action="store_true", help="Chỉ lưu prompt từng phase, chưa gọi AI vẽ.")
    parser.add_argument("--resume", action="store_true", help="Tiếp tục: dùng kịch bản và các phase đã vẽ trong output.")
    parser.add_argument("--redo", action="store_true", help="Vẽ lại cả phase đã có (dùng với --phase).")
    parser.add_argument("--phase", type=int, help="Chỉ dựng phase này (đánh số từ 1); bỏ qua để dựng tất cả.")
    parser.add_argument("--output", type=Path, default=ROOT / "preview")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if args.resume and args.script:
        parser.error("--resume dùng kịch bản đã lưu trong output, không đi cùng --script.")
    if not args.resume and not args.script:
        parser.error("Cần --script kich_ban.json hoặc --resume.")
    if args.phase is not None and args.phase < 1:
        parser.error("--phase phải từ 1 trở lên.")
    if output.exists() and any(output.iterdir()) and not args.resume:
        parser.error(f"{output} đã có dữ liệu. Dùng --resume hoặc chọn --output khác.")
    script_path = output / "kich_ban.json"
    source = script_path if args.resume else args.script
    if not source.is_file():
        parser.error(f"Không tìm thấy kịch bản: {source}.")
    script = json.loads(source.read_text(encoding="utf-8"))
    errors = validate(script, script.get("total_duration", 0))
    if errors:
        raise ValueError("Kịch bản không hợp lệ:\n- " + "\n- ".join(errors))
    phases = script["phases"]
    if args.phase is not None and args.phase > len(phases):
        parser.error(f"Kịch bản chỉ có {len(phases)} phase.")
    output.mkdir(parents=True, exist_ok=True)
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{script.get('title', '')}: {len(phases)} phase, {sum(p['duration'] for p in phases):g} giây.", flush=True)

    selected = [args.phase] if args.phase else range(1, len(phases) + 1)
    for index in selected:
        phase = phases[index - 1]
        svg_path = output / f"phase_{index}.svg"
        reference_index = phase.get("branch_from") or index - 1
        previous = output / f"phase_{reference_index}.svg"
        previous_svg = previous.read_text(encoding="utf-8") if index > 1 and previous.is_file() else None
        if args.plan_only:
            prompts = output / "prompts"
            prompts.mkdir(exist_ok=True)
            (prompts / f"phase_{index}.txt").write_text(phase_prompt(script, index, previous_svg), encoding="utf-8")
            print(f"  Phase {index}: đã lưu prompt.", flush=True)
            continue
        if args.resume and not args.redo and svg_path.is_file():
            try:
                svg = clean_svg(svg_path.read_text(encoding="utf-8"), script, index)
                write_phase(output, index, phase, svg, script)
                print(f"  Phase {index}: dùng bản đã vẽ.", flush=True)
                continue
            except ValueError:
                print(f"  Phase {index}: bản cũ không hợp lệ, vẽ lại.", flush=True)
        print(f"  Phase {index}: {phase.get('name', '')} ({phase['duration']:g}s) - đang vẽ…", flush=True)
        write_phase(output, index, phase, generate_phase(script, index, previous_svg), script)

    if args.plan_only:
        print(f"Đã lưu kịch bản và prompt tại {output}.")
        return
    index_path = write_index(script, output)
    print(f"Mở {index_path} để Play/Pause và tua." if index_path else "Chưa có phase nào được dựng.")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"API trả HTTP {error.code}. Kiểm tra URL, khóa, model; chạy --resume để tiếp tục.")
    except (URLError, TimeoutError, ValueError, OSError) as error:
        raise SystemExit(f"Lỗi: {error}")
