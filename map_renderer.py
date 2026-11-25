"""Seekable road-map phases. Geography comes from geocoding and routing services."""
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import urlencode, quote, urlparse
from urllib.request import Request, urlopen

from backend.illustrations import overlay_fragment, reference_data
from generate_kurzge import write_index


ROOT = Path(__file__).resolve().parent
VERSION = 'map-motion-v1'
GEOCODER = os.getenv('MAP_GEOCODER_URL', 'https://nominatim.openstreetmap.org/search').rstrip('/')
ROUTER = os.getenv('MAP_ROUTER_URL', 'https://router.project-osrm.org').rstrip('/')
USER_AGENT = 'FlipHTML-MapPreview/1.0 (local preview generator)'
OPENFREEMAP_ATTRIBUTION = 'OpenFreeMap © OpenMapTiles · © OpenStreetMap contributors'


def _request_json(url):
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def _name(text):
    return re.sub(r'\s+', ' ', text).strip(' ,.;:–—-')


def _style_url(context):
    """The selected map-2d style owns its basemap provider and URL."""
    map_style = context.get('preset', {}).get('map', {})
    url = map_style.get('styleUrl') if isinstance(map_style, dict) else None
    parsed = urlparse(url) if isinstance(url, str) else None
    if (not isinstance(map_style, dict) or map_style.get('provider') != 'openfreemap' or
            not parsed or parsed.scheme != 'https' or parsed.netloc != 'tiles.openfreemap.org' or
            not parsed.path.startswith('/styles/') or parsed.query or parsed.fragment):
        raise ValueError('Style map-2d phải dùng bản đồ nền OpenFreeMap hợp lệ.')
    return url


def _extract_stops(script, request):
    names = []
    for phase in script['phases']:
        title = phase['name']
        travel = re.search(r'(.+?)\s+(?:tới|đến|→)\s+(.+)', title, re.I)
        if travel:
            origin = re.sub(r'^(?:khởi hành|đi|rời)\s+(?:từ\s+)?', '', _name(travel[1]), flags=re.I)
            destination = _name(travel[2])
            if not names:
                names.append(origin)
            if destination not in names:
                names.append(destination)
    if names:
        return names
    prompt = ('Extract the ordered geographic stops from this map screenplay. Return ONLY JSON '
              '{"stops":["place name",...]}. Do not invent places. Use the script order. '
              'At least one named place is required.\n' + json.dumps(
                  [{'name': p['name'], 'description': p['description']} for p in script['phases']], ensure_ascii=False))
    from plant_kurzge import extract_json
    result = extract_json(request(prompt))
    names = result.get('stops') if isinstance(result, dict) else None
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n.strip() for n in names):
        raise ValueError('Không xác định được các điểm trên bản đồ từ kịch bản.')
    return [_name(name) for name in names]


def _geocode(name, country=None):
    parameters = {'q': name, 'format': 'jsonv2', 'limit': 8}
    if country:
        parameters['countrycodes'] = country
    query = urlencode(parameters)
    rows = _request_json(GEOCODER + '?' + query)
    if not rows:
        raise ValueError(f'Không tìm được tọa độ cho {name}.')
    row = next((r for r in rows if r.get('category') == 'place' and
                r.get('type') in ('city', 'town', 'village', 'municipality')), None)
    if row is None:
        row = next((r for r in rows if r.get('category') == 'boundary' and
                    r.get('type') == 'administrative'), rows[0])
    point = [float(row['lon']), float(row['lat'])]
    if not (-180 <= point[0] <= 180 and -85 <= point[1] <= 85):
        raise ValueError(f'Tọa độ của {name} không hợp lệ.')
    return point


def _route(origin, destination):
    points = ';'.join(f'{p[0]:.6f},{p[1]:.6f}' for p in (origin, destination))
    result = _request_json(f'{ROUTER}/route/v1/driving/{points}?overview=full&geometries=geojson&steps=false')
    if result.get('code') != 'Ok' or not result.get('routes'):
        raise ValueError('Dịch vụ định tuyến không trả tuyến đường bộ hợp lệ.')
    route = result['routes'][0]
    geometry = route.get('geometry', {})
    coordinates = geometry.get('coordinates')
    if (geometry.get('type') != 'LineString' or not isinstance(coordinates, list) or len(coordinates) < 2 or
            not all(isinstance(p, list) and len(p) == 2 and all(math.isfinite(v) for v in p) for p in coordinates)):
        raise ValueError('Hình học tuyến đường bộ không hợp lệ.')
    return {'coordinates': coordinates, 'distance_m': route['distance'],
            'source': ROUTER, 'profile': 'driving'}


def _phase_states(script, names):
    states = []
    for index, phase in enumerate(script['phases']):
        title = phase['name'].casefold()
        if any(word in title for word in ('tổng kết', 'kết thúc', 'tóm tắt')):
            states.append({'mode': 'summary', 'stopIndex': len(names) - 1})
            continue
        match = re.search(r'(.+?)\s+(?:tới|đến|→)\s+(.+)', phase['name'], re.I)
        if match:
            destination = _name(match[2])
            stop = next((i for i, name in enumerate(names) if name.casefold() == destination.casefold()), None)
            if stop is None or stop == 0:
                raise ValueError(f'Điểm đến của phase {index + 1} không khớp danh sách bản đồ.')
            states.append({'mode': 'move', 'stopIndex': stop, 'legIndex': stop - 1})
            continue
        stop = next((i for i, name in enumerate(names) if name.casefold() in title), None)
        if stop is None:
            stop = states[-1]['stopIndex'] if states else 0
        states.append({'mode': 'depart' if index == 0 else 'stop', 'stopIndex': stop})
    return states


def prepare_map(script, output, context, request):
    style_url = _style_url(context)
    path = output / 'map_plan.json'
    if path.is_file():
        plan = json.loads(path.read_text(encoding='utf-8'))
        if plan.get('styleUrl') != style_url or plan.get('attribution') != OPENFREEMAP_ATTRIBUTION:
            plan.update(styleUrl=style_url, attribution=OPENFREEMAP_ATTRIBUTION)
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
        return plan
    names = _extract_stops(script, request)
    cache = output.parent.parent / 'map_cache'
    cache.mkdir(exist_ok=True)
    country = 'vn' if 'Việt Nam' in script.get('title', '') + ' '.join(
        phase.get('description', '') for phase in script['phases']) else None
    points = []
    for name in names:
        key = hashlib.sha256((GEOCODER + '\n' + name + '\n' + str(country) + '\nv2').encode()).hexdigest()
        cached = cache / f'geo_{key}.json'
        if cached.is_file():
            coord = json.loads(cached.read_text(encoding='utf-8'))
        else:
            coord = _geocode(name, country)
            cached.write_text(json.dumps(coord), encoding='utf-8')
            time.sleep(1.05)
        points.append({'name': name, 'coord': coord})
    states = _phase_states(script, names)
    legs = []
    if any(state['mode'] == 'move' for state in states):
        for i in range(len(points) - 1):
            key = hashlib.sha256(json.dumps([ROUTER, points[i]['coord'], points[i + 1]['coord']]).encode()).hexdigest()
            cached = cache / f'route_{key}.json'
            if cached.is_file():
                route = json.loads(cached.read_text(encoding='utf-8'))
            else:
                route = _route(points[i]['coord'], points[i + 1]['coord'])
                cached.write_text(json.dumps(route), encoding='utf-8')
                time.sleep(1.05)
            legs.append(route)
    plan = {'stops': points, 'legs': legs, 'phases': states,
            'styleUrl': style_url, 'geocoder': GEOCODER, 'router': ROUTER,
            'attribution': OPENFREEMAP_ATTRIBUTION}
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    return plan


def _runtime(output):
    assets = output / 'assets' / 'map'
    assets.mkdir(parents=True, exist_ok=True)
    dist = ROOT / 'frontend' / 'node_modules' / 'maplibre-gl' / 'dist'
    if not (dist / 'maplibre-gl.js').is_file():
        raise ValueError('Thiếu MapLibre. Chạy npm install trong frontend/.')
    for filename in ('maplibre-gl.js', 'maplibre-gl.css', 'LICENSE.txt'):
        shutil.copy2(dist / filename, assets / filename)
    return hashlib.sha256((assets / 'maplibre-gl.js').read_bytes() + Path(__file__).read_bytes()).hexdigest()


def _phase_html(index, phase, plan, fingerprint, images):
    data = {'phase': plan['phases'][index - 1], 'stops': plan['stops'], 'legs': plan['legs'],
            'duration': phase['duration'], 'styleUrl': plan['styleUrl'], 'attribution': plan['attribution']}
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    scene = json.dumps({'phase': phase, 'renderer': VERSION}, ensure_ascii=False).replace('<', '\\u003c')
    card = overlay_fragment(phase, images)
    return f'''<!doctype html><html lang="vi" data-renderer="{VERSION}" data-fingerprint="{fingerprint}">
<head><meta charset="utf-8"><title>{html.escape(phase['name'])}</title>
<link rel="stylesheet" href="assets/map/maplibre-gl.css">
<style>html,body,#map{{margin:0;width:100%;height:100%;overflow:hidden}}body{{position:relative;background:#a9dcec}}
#map{{position:absolute;inset:0}}.maplibregl-control-container{{display:none}}
.brand{{position:absolute;bottom:12px;right:14px;background:#fffd;padding:5px 9px;border-radius:5px;font:12px system-ui;z-index:30}}
.stop-label{{font:700 20px system-ui,sans-serif;color:#fff;background:#d71920;border:2px solid #fff;
  border-radius:9px;padding:3px 9px;white-space:nowrap;box-shadow:0 3px 9px #0005}}
.car{{width:78px;height:47px;filter:drop-shadow(0 4px 3px #3338);z-index:25}}
.car svg{{display:block;transform-origin:center;transform:rotate(var(--heading,0deg))}}
</style></head><body><div id="map"></div><div class="brand">{html.escape(plan['attribution'])}</div>
<script type="application/json" id="scene-data">{scene}</script>
<script type="application/json" id="map-data">{payload}</script>
<script src="assets/map/maplibre-gl.js"></script>
<script>
const D=JSON.parse(document.getElementById('map-data').textContent),phase=D.phase;
const map=new maplibregl.Map({{container:'map',style:D.styleUrl,center:D.stops[0].coord,zoom:5.7,
  attributionControl:false,interactive:false,preserveDrawingBuffer:true}});
window.mapInstance=map;
let resolveReady,rejectReady;window.previewReady=new Promise((resolve,reject)=>{{resolveReady=resolve;rejectReady=reject}});
const car=document.createElement('div');car.className='car';car.innerHTML='<svg viewBox="0 0 78 47" width="78" height="47" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="11" width="62" height="26" rx="10" fill="#b41118" stroke="#fff" stroke-width="2"/><rect x="18" y="15" width="42" height="18" rx="6" fill="#d71920"/><rect x="27" y="17" width="25" height="14" rx="3" fill="#405470"/><rect x="34" y="17" width="13" height="14" rx="2" fill="#8a43ba" stroke="#e5c7f2"/><path d="M13 9h8v3h-8zm0 26h8v3h-8zm43-26h8v3h-8zm0 26h8v3h-8z" fill="#222"/></svg>';
const marker=new maplibregl.Marker({{element:car,anchor:'center'}}).setLngLat(D.stops[0].coord).addTo(map);
window.carMarker=marker;
for(const stop of D.stops){{const label=document.createElement('div');label.className='stop-label';label.textContent=stop.name;
  new maplibregl.Marker({{element:label,anchor:'bottom-left',offset:[12,-10]}}).setLngLat(stop.coord).addTo(map)}}
let ready=false,pending=0,appliedTime=NaN;
function feature(coords){{return {{type:'Feature',geometry:{{type:'LineString',coordinates:coords}},properties:{{}}}}}}
function mercatorY(lat){{return Math.log(Math.tan(Math.PI/4+lat*Math.PI/360))}}
const paths=D.legs.map(leg=>{{const points=leg.coordinates,lengths=[0];
  for(let i=1;i<points.length;i++){{const a=points[i-1],b=points[i];
    lengths.push(lengths[i-1]+Math.hypot((b[0]-a[0])*Math.PI/180,mercatorY(b[1])-mercatorY(a[1])));}}
  return {{points,lengths,total:lengths.at(-1)}}}});
function locate(path,p){{const goal=path.total*Math.max(0,Math.min(1,p));let low=1,high=path.lengths.length-1;
  while(low<high){{const mid=(low+high)>>1;if(path.lengths[mid]<goal)low=mid+1;else high=mid;}}
  const i=low,a=path.points[i-1],b=path.points[i],span=path.lengths[i]-path.lengths[i-1];
  const f=span?Math.max(0,Math.min(1,(goal-path.lengths[i-1])/span)):0;
  return {{coord:[a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f],index:i}};}}
function headingAt(path,p){{
  // A road vertex can turn sharply over a few metres. Use the direction of a
  // short stretch of the journey so a fast-moving icon does not flicker left/right.
  const width=Math.min(.12,Math.max(.05,.8/D.duration));
  const start=Math.max(0,Math.min(1-width,p-width/2));
  const before=map.project(locate(path,start).coord),after=map.project(locate(path,start+width).coord);
  return Math.atan2(after.y-before.y,after.x-before.x)*180/Math.PI;
}}
function reveal(p){{return ['step',['line-progress'],'#d71920',Math.max(0,Math.min(1,p)),'rgba(215,25,32,0)']}}
function renderAt(value){{pending=Math.max(0,Math.min(D.duration,Number(value)||0));
  if(!ready||pending===appliedTime)return;appliedTime=pending;
  const p=D.duration?pending/D.duration:0, stop=phase.stopIndex;
  const moving=phase.mode==='move';
  if(moving)map.setPaintProperty('active-route','line-gradient',reveal(p));
  const position=moving?locate(paths[phase.legIndex],p):null;
  let coord=moving?position.coord:D.stops[stop].coord;
  marker.setLngLat(coord);let center=coord,zoom=13;
  if(phase.mode==='summary'){{center=D.stops[Math.floor(D.stops.length/2)].coord;zoom=5.7;}}
  else if(phase.mode==='depart'){{zoom=5.7+7.3*Math.min(1,p*3);}}
  else if(phase.mode==='move'){{zoom=p<.85?6.4:6.4+6.6*(p-.85)/.15;}}
  map.jumpTo({{center,zoom,duration:0}});
  if(position)car.style.setProperty('--heading',headingAt(paths[phase.legIndex],p)+'deg');
}}
window.renderAt=renderAt;
map.on('load',()=>{{ready=true;
  const completed=phase.mode==='summary'?D.legs.length:phase.mode==='move'?phase.legIndex:phase.stopIndex;
  map.addSource('route',{{type:'geojson',data:{{type:'FeatureCollection',features:D.legs.slice(0,completed).map(l=>feature(l.coordinates))}}}});
  map.addLayer({{id:'route',type:'line',source:'route',paint:{{'line-color':'#d71920','line-width':7,'line-opacity':.95}},layout:{{'line-cap':'round','line-join':'round'}}}});
  if(phase.mode==='move'){{map.addSource('active-route',{{type:'geojson',lineMetrics:true,data:feature(paths[phase.legIndex].points)}});
    map.addLayer({{id:'active-route',type:'line',source:'active-route',paint:{{'line-width':7,'line-gradient':reveal(0)}},layout:{{'line-cap':'round','line-join':'round'}}}});}}
  map.addSource('stops',{{type:'geojson',data:{{type:'FeatureCollection',features:D.stops.map(s=>({{type:'Feature',geometry:{{type:'Point',coordinates:s.coord}},properties:{{name:s.name}}}}))}}}});
  map.addLayer({{id:'dots',type:'circle',source:'stops',paint:{{'circle-color':'#d71920','circle-radius':10,'circle-stroke-color':'#fff','circle-stroke-width':3}}}});
  renderAt(pending);map.once('idle',()=>resolveReady(true));
  parent.postMessage({{type:'preview-ready'}},'*');
}});
map.on('error',e=>{{rejectReady(e.error||new Error('Không tải được bản đồ.'));
  parent.postMessage({{type:'preview-error',message:e.error?.message||'Không tải được bản đồ.'}},'*')}});
addEventListener('message',e=>{{if(e.source===parent&&e.data&&Number.isFinite(e.data.t))renderAt(e.data.t)}});
renderAt(0);
</script>{card}</body></html>'''


def _write_pages(script, output, plan, fingerprint):
    manifest_path = output / 'references.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else []
    images = reference_data(output, manifest)
    for index, phase in enumerate(script['phases'], 1):
        (output / f'phase_{index}.html').write_text(_phase_html(index, phase, plan, fingerprint, images), encoding='utf-8')
    write_index(script, output, fingerprint)


def build_map_stills(script, output, context, request, progress):
    plan = prepare_map(script, output, context, request)
    runtime_hash = _runtime(output)
    fingerprint = hashlib.sha256(json.dumps({'plan': plan, 'style': context, 'runtime': runtime_hash,
                                            'script': script, 'version': VERSION}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    for phase in script['phases']:
        for event in phase.get('illustration_events', []):
            if event['operation'] == 'hide':
                event['time'] = event.get('fraction', 0) * phase['duration']
            else:
                event['time'] = phase['duration'] * phase['voiceover'].index(event['cue']) / max(1, len(phase['voiceover']))
        phase.get('illustration_events', []).sort(key=lambda e: e['time'])
    _write_pages(script, output, plan, fingerprint)
    helper = ROOT / 'frontend' / 'scripts' / 'map-stills.cjs'
    result = subprocess.run(['node', str(helper), str(output.resolve()), str(len(script['phases']))],
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise ValueError('Không chụp được preview bản đồ: ' + result.stderr[-1000:])
    rows = []
    for index, phase in enumerate(script['phases'], 1):
        from image_asset_generator import validate_png
        raw = (output / f'phase_{index}.preview.png').read_bytes()
        info = validate_png(raw)
        rows.append({'id': str(phase['id']), 'name': phase['name'], 'width': info['size'][0],
                     'height': info['size'][1], 'sha256': hashlib.sha256(raw).hexdigest()})
        (output / 'stills.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        progress('stills', index, len(script['phases']))


def build_map_preview(script, output, context, request, progress):
    plan = prepare_map(script, output, context, request)
    runtime_hash = _runtime(output)
    manifest = json.loads((output / 'references.json').read_text(encoding='utf-8')) if (output / 'references.json').is_file() else []
    fingerprint = hashlib.sha256(json.dumps({'plan': plan, 'style': context, 'runtime': runtime_hash,
                                            'script': script, 'references': manifest, 'version': VERSION},
                                           ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    _write_pages(script, output, plan, fingerprint)
    progress('phases', len(script['phases']), len(script['phases']))
    return fingerprint


def verify_map_phases(output, script, fingerprint):
    rows = []
    for index, phase in enumerate(script['phases'], 1):
        page = (output / f'phase_{index}.html').read_text(encoding='utf-8')
        if (f'data-fingerprint="{fingerprint}"' not in page or 'window.renderAt=renderAt' not in page or
                'maplibre-gl.js' not in page):
            raise ValueError(f'Phase bản đồ {index} không hợp lệ.')
        rows.append({'id': str(phase['id']), 'name': phase['name'], 'duration': phase['duration'],
                     'url': f'/api/previews/{output.name}/phase_{index}.html'})
    return rows
