"""Style-independent illustration cues and exact uploaded image overlays."""
import base64
import html
import json
import re
import io
from PIL import Image, ImageOps, ImageDraw, ImageFont


MENTION = re.compile(r'@image_([1-9][0-9]*)\b')
INTRO = re.compile(r'(?:khi\s+(?:nói|nhắc(?:\s+đến)?)\s+)([^,;.]+)', re.I)
DISPLAY = re.compile(r'(?:hiện|hiển thị|mở|đưa lên|thay bằng|chuyển sang).{0,32}(?:ảnh minh họa|thẻ|ảnh|@image_)', re.I)
HIDE = re.compile(r'\b(?:thu|ẩn|đóng)\s+(?:ảnh|thẻ)\b', re.I)


def _spoken_cue(label, speech):
    words = label.strip().split()
    for end in range(len(words), 0, -1):
        candidate = ' '.join(words[:end])
        match = re.search(re.escape(candidate), speech, re.I)
        if match:
            return match[0]
    return None


def attach_events(script, sources, references):
    """Resolve visual commands from detailed text; never put tokens in speech."""
    available = {item['number']: item for item in references if item['kind'] == 'illustration'}
    if not sources:
        return
    for phase, source in zip(script['phases'], sources):
        visual = source['animation']
        speech = phase.get('voiceover', '')
        events = []
        for mention in MENTION.finditer(visual):
            number = int(mention[1])
            if number not in available:
                raise ValueError(f'@image_{number} chưa có trong Ảnh minh họa.')
            clause_start = max(visual.rfind(';', 0, mention.start()), visual.rfind('.', 0, mention.start()),
                               visual.rfind('。', 0, mention.start())) + 1
            before = visual[clause_start:mention.start()]
            after = visual[mention.end():mention.end() + 100]
            if not DISPLAY.search(before + visual[mention.start():mention.end()]) and not DISPLAY.search(after):
                continue
            cues = list(INTRO.finditer(before))
            if not cues:
                cues = list(INTRO.finditer(after))
            cue = _spoken_cue(cues[-1][1], speech) if cues else None
            if not cue:
                raise ValueError(f'Không tìm được cụm lời đọc cho @image_{number} trong phase {phase["name"]}.')
            if len(re.findall(re.escape(cue), speech, re.I)) != 1:
                raise ValueError(f'Cụm lời đọc {cue!r} không duy nhất trong phase {phase["name"]}.')
            caption = re.search(r'(?:chú thích|ghi)\s+[“"]([^”"]+)[”"]', after, re.I)
            events.append({'operation': 'show' if not events else 'replace', 'number': number,
                           'cue': cue, 'caption': caption[1] if caption else cues[-1][1].strip()})
        if HIDE.search(visual):
            events.append({'operation': 'hide', 'fraction': 0.0 if HIDE.search(visual).start() < 30 else .96})
        phase['illustration_events'] = events


def validate_events(script, references):
    available = {r['number'] for r in references if r['kind'] == 'illustration'}
    for index, phase in enumerate(script['phases'], 1):
        for event in phase.get('illustration_events', []):
            op = event.get('operation')
            if op not in ('show', 'replace', 'hide'):
                raise ValueError(f'Phase {index}: thao tác ảnh không hợp lệ.')
            if op == 'hide':
                continue
            number, cue = event.get('number'), event.get('cue')
            if number not in available or not isinstance(cue, str) or cue not in phase.get('voiceover', ''):
                raise ValueError(f'Phase {index}: ảnh hoặc mốc lời đọc không hợp lệ.')


def reference_data(output, references):
    data = {}
    for item in references:
        if item['kind'] != 'illustration':
            continue
        raw = (output / item['src']).read_bytes()
        mime = {'jpg': 'jpeg', 'png': 'png', 'webp': 'webp'}[item['src'].rsplit('.', 1)[-1]]
        data[item['number']] = 'data:image/' + mime + ';base64,' + base64.b64encode(raw).decode()
    return data


def still_with_illustration(data, phase, output, manifest):
    events = phase.get('illustration_events', [])
    if not events:
        return data
    moment = .55 * phase['duration']
    shown = None
    for event in events:
        if event['operation'] == 'hide':
            at = event.get('time', event.get('fraction', 0) * phase['duration'])
        else:
            at = event.get('time', phase['duration'] * phase['voiceover'].index(event['cue']) / len(phase['voiceover']))
        if at <= moment:
            shown = None if event['operation'] == 'hide' else event
    if not shown:
        return data
    item = next((r for r in manifest if r['number'] == shown['number']), None)
    if not item:
        raise ValueError(f'Ảnh @image_{shown["number"]} không còn trong preview.')
    with Image.open(io.BytesIO(data)) as base_source, Image.open(output / item['src']) as photo_source:
        base = base_source.convert('RGB')
        width, height = base.size
        card_width, photo_height = int(width * .29), int(height * .43)
        x, y = width - card_width - int(width * .03), int(height * .06)
        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle((x-12, y-12, x+card_width+12, y+photo_height+78),
                               radius=18, fill='white', outline='#D71920', width=4)
        photo = ImageOps.fit(photo_source.convert('RGB'), (card_width, photo_height))
        base.paste(photo, (x, y))
        font = ImageFont.truetype('arial.ttf', 29) if __import__('os').name == 'nt' else ImageFont.truetype('DejaVuSans.ttf', 29)
        draw.text((x+4, y+photo_height+19), shown.get('caption', ''), fill='#222222', font=font)
        target = io.BytesIO()
        base.save(target, format='PNG')
        return target.getvalue()


def overlay_fragment(phase, references):
    """Pure time-seek overlay shared by SVG, 3D and map phase HTML."""
    events = phase.get('illustration_events', [])
    if not events:
        return ''
    used = {e['number'] for e in events if e['operation'] != 'hide'}
    images = {str(number): references[number] for number in used}
    payload = json.dumps({'events': events, 'images': images}, ensure_ascii=False).replace('<', '\\u003c')
    return ('<style id="illustration-style">#illustration-card{position:absolute;right:3%;top:7%;width:26%;'
            'padding:12px;background:#fff;border:3px solid #d71920;border-radius:20px;box-shadow:0 12px 25px #0004;'
            'z-index:40;display:none;font:700 clamp(14px,2vw,28px) system-ui;color:#202020}'
            '#illustration-card img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:10px;display:block}'
            '#illustration-card span{display:block;padding:8px 3px 2px}</style>'
            '<div id="illustration-card"><img alt=""><span></span></div>'
            '<script type="application/json" id="illustration-data">' + payload + '</script>'
            '<script>(function(){const d=JSON.parse(document.getElementById("illustration-data").textContent),'
            'card=document.getElementById("illustration-card"),photo=card.querySelector("img"),label=card.querySelector("span");'
            'function draw(t){let current=null;for(const e of d.events){const at=e.time??0;if(at>t)break;'
            'if(e.operation==="hide")current=null;else current=e}'
            'card.style.display=current?"block":"none";if(current){photo.src=d.images[current.number];'
            'label.textContent=current.caption||""}}'
            'const old=window.renderAt;window.renderAt=function(t){if(old)old(t);draw(t)};'
            'addEventListener("message",e=>{if(e.source===parent&&e.data&&Number.isFinite(e.data.t))draw(e.data.t)});'
            'draw(0)})();</script>')
