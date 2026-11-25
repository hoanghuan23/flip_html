import * as THREE from "three";

// This file is bundled as a classic IIFE: it also runs in opaque sandbox iframes.
const meta = JSON.parse(document.getElementById("scene-data").textContent);
const {plan, references} = JSON.parse(document.getElementById("mesh-data").textContent);
const stage = document.getElementById("stage");
const nodes = new Map(), base = new Map(), pending = [], overlayNodes = [];
const scene = new THREE.Scene();
scene.background = new THREE.Color(plan.background);
const camera = new THREE.PerspectiveCamera(plan.fov, 1920 / 1080, .05, 2000);
let renderer;
const errorBox = document.getElementById("scene-error");
function fail(error) {
  errorBox.hidden = false;
  errorBox.textContent = "Không dựng được cảnh 3D. " + (error?.message || "Hãy kiểm tra WebGL và tài nguyên.");
  parent.postMessage({type:"preview-error", message:errorBox.textContent}, "*");
}
function resize() {
  stage.style.transform = `translate(-50%,-50%) scale(${Math.min(innerWidth/1920, innerHeight/1080)})`;
}
addEventListener("resize", resize); resize();
function sample(keys, t, field, smooth) {
  if (t <= keys[0].t) return keys[0][field];
  for (let i=1;i<keys.length;i++) {
    if(t <= keys[i].t) {
      let p=(t-keys[i-1].t)/(keys[i].t-keys[i-1].t);
      if(smooth) p=p*p*(3-2*p);
      return keys[i-1][field].map((v,j)=>v+(keys[i][field][j]-v)*p);
    }
  }
  return keys[keys.length-1][field];
}
function geometry(type) {
  switch(type) {
    case "box": return new THREE.BoxGeometry(1,1,1);
    case "sphere": return new THREE.SphereGeometry(1,64,40);
    case "plane": return new THREE.PlaneGeometry(1,1);
    case "cylinder": return new THREE.CylinderGeometry(.5,.5,1,32);
    case "cone": return new THREE.ConeGeometry(.5,1,32);
    case "torus": return new THREE.TorusGeometry(1,.06,12,96);
    default: throw new Error("Hình học không hỗ trợ: "+type);
  }
}
function seededStars() {
  let seed=7291;
  const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};
  const positions=new Float32Array(2400*3);
  for(let i=0;i<2400;i++) {
    const a=rand()*Math.PI*2,z=rand()*2-1,r=180+rand()*120,s=Math.sqrt(1-z*z);
    positions.set([r*s*Math.cos(a),r*z,r*s*Math.sin(a)],i*3);
  }
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(positions,3));
  return new THREE.Points(g,new THREE.PointsMaterial({color:0xd0dbea,size:.18,sizeAttenuation:true}));
}
const textureCache=new Map();
function texture(name) {
  if(textureCache.has(name)) return textureCache.get(name);
  const image=new Image(); image.src=plan.textures[name];
  const tex=new THREE.Texture(image);tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=4;
  pending.push(image.decode().then(()=>{tex.needsUpdate=true}));
  textureCache.set(name,tex);return tex;
}
function point(target, anchor) {
  return nodes.get(target).localToWorld(new THREE.Vector3(...anchor));
}
function screenPoint(target, anchor) {
  const p=point(target,anchor).project(camera);
  return {x:(p.x+1)*960,y:(1-p.y)*540,visible:p.z>=-1&&p.z<=1};
}
try {
  renderer = new THREE.WebGLRenderer({canvas:document.getElementById("scene"),antialias:true,preserveDrawingBuffer:true});
  renderer.setSize(1920,1080,false);renderer.setPixelRatio(1);
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;
  renderer.domElement.addEventListener("webglcontextlost",e=>{e.preventDefault();fail(new Error("WebGL mất kết nối."))});
  scene.add(new THREE.AmbientLight(0xffffff,plan.ambient));
  const key=new THREE.DirectionalLight(0xfff5e6,plan.lightIntensity);key.position.set(...plan.lightPosition);scene.add(key);
  const fill=new THREE.DirectionalLight(0x6a9fd9,.8);fill.position.set(8,-3,-6);scene.add(fill);
  for(const spec of plan.nodes) {
    let object;
    if(spec.geometry==="group") object=new THREE.Group();
    else if(spec.geometry==="stars") object=seededStars();
    else {
      const m=spec.material;
      const material=new THREE.MeshStandardMaterial({color:m.color,metalness:m.metalness,roughness:m.roughness,
        emissive:m.emissive,transparent:m.opacity<1,opacity:m.opacity,depthWrite:m.opacity===1,side:THREE.DoubleSide,
        map:m.texture?texture(m.texture):null});
      object=new THREE.Mesh(geometry(spec.geometry),material);
    }
    object.name=spec.id;object.position.set(...spec.position);object.rotation.set(...spec.rotation);object.scale.set(...spec.scale);
    nodes.set(spec.id,object);base.set(spec.id,spec);
  }
  for(const spec of plan.nodes) (spec.parent?nodes.get(spec.parent):scene).add(nodes.get(spec.id));
  const overlayRoot=document.getElementById("overlays"),svg=document.getElementById("connectors");
  for(const overlay of plan.overlays) {
    let element,line;
    if(overlay.type==="image") {
      const reference=references[String(overlay.number)];
      if(!reference) throw new Error("Thiếu Hình "+overlay.number);
      element=document.createElement("figure");element.className="reference-card";
      element.style.width=overlay.width*1920+"px";
      const image=document.createElement("img");image.alt="Hình "+overlay.number;image.src=reference.src;
      pending.push(image.decode());
      const caption=document.createElement("figcaption");caption.textContent=overlay.text||("Hình "+overlay.number);
      element.append(image,caption);overlayRoot.append(element);
    } else {
      element=document.createElement("div");element.className="info-label";element.textContent=overlay.text;overlayRoot.append(element);
      if(overlay.type==="connector") {
        line=document.createElementNS("http://www.w3.org/2000/svg","line");
        line.setAttribute("stroke","#dcecf7");line.setAttribute("stroke-width","2");line.setAttribute("stroke-dasharray","8 7");svg.append(line);
      }
    }
    element.style.left=overlay.x*1920+"px";element.style.top=overlay.y*1080+"px";
    overlayNodes.push({overlay,element,line});
  }
  window.renderAt = function(value) {
    const t=Math.max(0,Math.min(meta.phase.duration,Number(value)||0));
    for(const [id,object] of nodes) {
      const spec=base.get(id);object.position.set(...spec.position);object.rotation.set(...spec.rotation);object.scale.set(...spec.scale);
    }
    for(const track of plan.tracks) nodes.get(track.target)[track.property].set(...sample(track.keys,t,"value",track.easing==="smooth"));
    camera.position.set(...sample(plan.camera,t,"position",true));camera.lookAt(...sample(plan.camera,t,"lookAt",true));
    camera.updateMatrixWorld();scene.updateMatrixWorld(true);
    const occupied=overlayNodes.filter(({overlay:o})=>o.type==="image"&&t>=o.start&&t<o.end)
      .map(({overlay:o,layout})=>({x:o.x*1920,y:o.y*1080,w:layout?.w||o.width*1920,h:layout?.h||410}));
    const overlap=(a,b)=>Math.max(0,Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y));
    for(const {overlay:o,element,line,layout} of overlayNodes) {
      const active=t>=o.start&&t<o.end;
      let visible=active;
      element.style.display=active?"":"none";
      if(o.target&&o.type==="label") {
        const p=screenPoint(o.target,o.anchor);visible=visible&&p.visible;
        const w=layout?.w||640,h=layout?.h||70;
        const candidates=[[p.x+30,p.y-45],[p.x+30,p.y+h+30],[p.x-w-30,p.y-45],[o.x*1920,o.y*1080]]
          .map(([x,y])=>({x:Math.max(192,Math.min(1728-w,x)),y:Math.max(108,Math.min(972-h,y)),w,h}));
        candidates.sort((a,b)=>occupied.reduce((sum,box)=>sum+overlap(a,box)-overlap(b,box),0));
        const chosen=candidates[0];element.style.left=chosen.x+"px";element.style.top=chosen.y+"px";
        if(visible)occupied.push(chosen);
      }
      if(line) {
        const a=screenPoint(o.target,o.anchor),b=screenPoint(o.endTarget,o.endAnchor);visible=visible&&a.visible&&b.visible;
        for(const [key,v] of Object.entries({x1:a.x,y1:a.y,x2:b.x,y2:b.y})) line.setAttribute(key,v);
        line.style.display=visible?"":"none";
      }
      element.style.display=visible&&(o.type!=="connector"||o.text.trim())?"":"none";
      element.style.opacity=String(o.start===0?1:Math.min(1,Math.max(0,(t-o.start)/.45)));
    }
    renderer.render(scene,camera);window.currentTime=t;
  };
  window.previewReady=Promise.all([...pending,document.fonts.ready]).then(async()=>{
    for(const record of overlayNodes) {
      record.element.style.display="";
      record.layout={w:record.element.offsetWidth,h:record.element.offsetHeight};
    }
    await renderer.compileAsync(scene,camera);window.renderAt(window.pendingTime||0);
    parent.postMessage({type:"preview-ready"},"*");return true;
  }).catch(error=>{fail(error);return false});
} catch(error) {
  fail(error);window.previewReady=Promise.resolve(false);
}
addEventListener("message",event=>{if(event.source===parent&&typeof event.data?.t==="number") window.previewReady.then(ok=>{if(ok)window.renderAt(event.data.t)})});
addEventListener("message",event=>{if(event.source===parent&&event.data?.type==="preview-probe") window.previewReady.then(ok=>parent.postMessage({type:ok?"preview-ready":"preview-error",message:errorBox.textContent},"*"))});
addEventListener("hf-seek",event=>{event.detail.waitUntil(window.previewReady.then(ok=>{if(!ok)throw new Error("Cảnh 3D chưa sẵn sàng");window.renderAt(event.detail.time)}))});
addEventListener("pagehide",()=>renderer?.dispose());
