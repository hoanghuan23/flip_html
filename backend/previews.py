"""Controlled, seekable illustration templates shared by browser and exporter."""
from html import escape
import hashlib
import json
from pathlib import Path
from .models import PreviewRequest

PALETTES = {
    'detailed-vector': ('#d7f0ef', '#2b9c9f', '#dc647b', '#ffffff', '#20383f'),
    'outlined-cartoon': ('#fff2d4', '#78ccc4', '#ffce64', '#fffaf0', '#343539'),
    'cartoon': ('#f4ede3', '#237c83', '#ffd18c', '#ffffff', '#233d47'),
    'dark': ('#111b35', '#4233a7', '#a9a2ff', '#d7ddfa', '#f0f0ff'),
    'watercolor': ('#edf5ee', '#81aab4', '#ecd7a8', '#ffffff', '#385e62'),
    'pixel': ('#242740', '#5262a5', '#f8be72', '#c8dcf5', '#f4f2ff'),
    'sketch': ('#f2eadc', '#a59b83', '#d0b78a', '#f8f4eb', '#443f34'),
    'flat': ('#ffffff', '#93D7D5', '#FEC600', '#CDC6EF', '#011B5C'),
    'flat-with-black': ('#ffffff', '#171717', '#f26b4f', '#f4d76c', '#171717'),
    'halftone-line': ('#f6f1e7', '#242424', '#99938b', '#fffcf5', '#242424'),
}


def revision(request: PreviewRequest) -> str:
    return hashlib.sha256(request.model_dump_json().encode()).hexdigest()


def create_preview(request: PreviewRequest, root: Path, snapshot_id: str) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    rows, playlist = [], []
    for i, scene in enumerate(request.scenes, 1):
        filename = f'phase_{i}.html'
        (root / filename).write_text(phase_html(request, i - 1), encoding='utf-8')
        row = {'id': scene.id, 'name': scene.name, 'duration': scene.duration,
               'url': f'/api/previews/{snapshot_id}/{filename}'}
        rows.append(row)
        playlist.append({'src': filename, 'title': scene.name, 'duration': scene.duration})
    (root / 'index.html').write_text(
        '<!doctype html><html><body><script type="application/json" id="data">' +
        json.dumps(playlist, ensure_ascii=False).replace('<', '\\u003c') + '</script></body></html>',
        encoding='utf-8')
    meta = {'id': snapshot_id, 'revision': revision(request), 'projectId': request.projectId,
            'duration': sum(s.duration for s in request.scenes), 'width': 1920, 'height': 1080,
            'phases': rows}
    (root / 'draft.json').write_text(request.model_dump_json(), encoding='utf-8')
    (root / 'snapshot.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    return meta


def phase_html(request: PreviewRequest, index: int) -> str:
    scene = request.scenes[index]
    # New configured styles can use the controlled illustration template even
    # before a dedicated render palette is provided.
    bg, sea, sun, cloud, ink = PALETTES.get(request.styleId, PALETTES['flat'])
    number = index + 1
    # Text is escaped into HTML; user content is never executed as markup or JS.
    return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
<title>{escape(scene.name)}</title>
<style>html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:{bg}}}
svg{{display:block;width:100%;height:100%}}text{{font-family:Arial,sans-serif}}
.copy{{font-family:Arial,sans-serif;color:{ink};overflow-wrap:anywhere}}
.copy h1{{font-size:66px;line-height:1.15;margin:18px 0 22px;max-width:1100px}}
.copy p{{font-size:33px;line-height:1.45;margin:0;max-width:1260px}}
</style></head><body>
<svg viewBox="0 0 1920 1080" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(scene.name, quote=True)}">
<defs><pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" fill="none" stroke="{ink}" stroke-opacity=".035" stroke-width="2"/></pattern></defs>
<rect width="1920" height="1080" fill="{bg}"/><rect width="1920" height="1080" fill="url(#grid)"/>
<circle id="sun" cx="1470" cy="240" r="120" fill="{sun}"/>
<g id="cloud" fill="{cloud}" stroke="{ink}" stroke-width="5"><path d="M1030 360C990 360 970 280 1032 260C1018 180 1130 146 1177 205C1228 146 1329 190 1320 251C1400 236 1430 351 1364 362Z"/></g>
<g id="drops" stroke="{sea}" stroke-width="8" stroke-linecap="round"><path d="M1120 405l-16 34M1200 420l-16 34M1280 405l-16 34M1360 420l-16 34"/></g>
<path id="wave" d="M-180 580Q100 500 380 580T940 580T1500 580T2060 580V840H-180Z" fill="{sea}" opacity=".25"/>
<path d="M0 650Q240 570 480 650T960 650T1440 650T1920 650V850H0Z" fill="{sea}"/>
<path d="M0 720Q240 660 480 720T960 720T1440 720T1920 720" fill="none" stroke="{cloud}" stroke-opacity=".25" stroke-width="3"/>
<circle id="orbit" cx="500" cy="490" r="55" fill="{sun}"/>
<foreignObject x="132" y="100" width="1656" height="410"><div xmlns="http://www.w3.org/1999/xhtml" class="copy">
<p style="font-size:22px;letter-spacing:5px;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(request.title)} · CẢNH {number:02d}</p>
<h1 id="scene-title" style="max-width:850px">{escape(scene.name)}</h1></div></foreignObject>
<text x="142" y="770" fill="{cloud}" font-size="22" letter-spacing="3">ANIMATION MINH HỌA · {number:02d} / {len(request.scenes):02d}</text>
</svg><script>
var D={scene.duration};
window.renderAt=function(value){{
 const t=Math.max(0,Math.min(D,Number.isFinite(value)?value:0));
 document.getElementById('cloud').setAttribute('transform','translate('+ (Math.sin(t*.7+{index})*45) +',0)');
 document.getElementById('wave').setAttribute('transform','translate('+ (Math.sin(t*.9)*90) +',0)');
 document.getElementById('drops').setAttribute('transform','translate(0,'+ ((t*45)%65) +')');
 document.getElementById('drops').setAttribute('opacity',String(.45+.5*Math.sin(t*2)**2));
 document.getElementById('orbit').setAttribute('cx',String(390+Math.sin(t*.8+{index})*140));
 document.getElementById('orbit').setAttribute('cy',String(480+Math.cos(t*.8)*45));
}};
addEventListener('message',function(e){{if(e.source===parent&&e.data&&typeof e.data.t==='number')window.renderAt(e.data.t)}});
window.renderAt(0);
window.previewReady=document.fonts.ready.then(function(){{
 const heading=document.getElementById('scene-title');
 for(let size=66;heading.scrollHeight>280&&size>=28;size-=2)heading.style.fontSize=size+'px';
 return true;
}});
</script></body></html>'''
