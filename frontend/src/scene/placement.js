import {drawGraph} from './graph-presentation.js';
import {enrichAssets} from './asset-model.js';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {TransformControls} from 'three/addons/controls/TransformControls.js';
import {relations,isSupport,isStructure,supportHeight} from './relations.js';
const $=s=>document.querySelector(s);
function dispose(object){object.traverse(n=>{n.geometry?.dispose();for(const m of Array.isArray(n.material)?n.material:[n.material]){if(m){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}}});}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
export class Placement {
  constructor(viewer,status){
    this.v=viewer;this.status=status;this.items=[];this.baseNodes=[];this.graph={nodes:[],edges:[]};this.selected=null;
    this.objects=new THREE.Scene();this.objects.add(new THREE.HemisphereLight(0xffffff,0x6a755d,2));
    const light=new THREE.DirectionalLight(0xfff5e5,2);light.position.set(-2,4,2);this.objects.add(light);
    this.occlusion=new THREE.Scene();this.depthMaterial=new THREE.MeshBasicMaterial({colorWrite:false,side:THREE.DoubleSide});
    this.depthTarget=new THREE.WebGLRenderTarget(1,1);this.depthTarget.depthTexture=new THREE.DepthTexture(1,1);
    this.occlusionUniforms={sceneDepth:{value:this.depthTarget.depthTexture},depthSize:{value:new THREE.Vector2(1,1)},depthNear:{value:viewer.camera.near},depthFar:{value:viewer.camera.far}};
    this.controls=new TransformControls(viewer.camera,viewer.renderer.domElement);
    this.helper=this.controls.getHelper();this.objects.add(this.helper);
    this.controls.addEventListener('dragging-changed',e=>{viewer.controls.enabled=!e.value;this.dragging=e.value;});
    this.controls.addEventListener('objectChange',()=>this.update());
    this.controls.addEventListener('mouseUp',()=>{this.skipClick=true;this.snapSelected();this.update();});
    this.ray=new THREE.Raycaster();
    const canvas=viewer.renderer.domElement;
    canvas.addEventListener('pointerdown',e=>{this.down=[e.clientX,e.clientY];});
    canvas.addEventListener('pointerup',e=>{
      if(this.skipClick){this.skipClick=false;return;}
      if(!this.down||Math.hypot(e.clientX-this.down[0],e.clientY-this.down[1])>5||this.dragging)return;
      const rect=canvas.getBoundingClientRect();
      this.ray.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),viewer.camera);
      if(this.pending){const spot=this.nearestSpot(e.clientX,e.clientY);if(spot)this.placeAtSpot(spot);else this.placeFromRay(this.ray);return;}
      const hits=this.ray.intersectObjects(this.items.map(x=>x.object),true);
      if(hits[0]){const item=this.items.find(x=>{let found=false;x.object.traverse(n=>{if(n===hits[0].object)found=true;});return found;});this.select(item);}
      else this.pickGraph(this.ray);
    });
    viewer.afterRender=()=>this.render();
    window.addEventListener('scene-loaded',async event=>{try{
      await this.loadGraph();
      const job=new URLSearchParams(location.search).get('job');
      if(job&&!this.importedJob){await this.importGenerated(job);this.importedJob=job;}
      event.detail?.resolve?.();
    }catch(e){this.status(e.message,true);event.detail?.reject?.(e);}});
    this.ui();
    this.generatedUI();
  }
  async loadGraph(preserveItems=false){
    const base=this.v.base,manifest=this.v.manifest;
    const r=await fetch(new URL(manifest.graph,base),{cache:'no-store'});
    if(!r.ok)throw Error('그래프를 불러오지 못했습니다.');
    const graph=await r.json();
    if(this.v.manifest!==manifest)return;
    if(!preserveItems){
    this.controls.detach();for(const item of this.items){this.objects.remove(item.object,item.shadow);dispose(item.object);dispose(item.shadow);}
    this.items=[];this.selected=null;if(this.pending){dispose(this.pending.object);this.pending=null;}
    this.baseNodes=[];this.selectedGraphId=null;if(this.boxHelper){this.objects.remove(this.boxHelper);dispose(this.boxHelper);this.boxHelper=null;}
    }
    this.baseGraph=graph;this.baseNodes=(graph.nodes||[]).map(n=>{
      if(n.source!=='sam3-metric-depth'||!n.attributes)return n;
      const {attributes,...rest}=n;return {...rest,category_attributes:attributes};
    });
    if(!preserveItems)this.assetRegistry={ids:new Map(),next:1};
    this.spots=graph.recommended_placements||[];this.spotUI();
    if(this.proxy){this.occlusion.remove(this.proxy);this.proxy.geometry.dispose();}
    const geometry=this.v.surface.geometry.clone(),transparent=new Uint8Array(graph.camera.width*graph.camera.height);
    const canvas=document.createElement('canvas');canvas.width=graph.camera.width;canvas.height=graph.camera.height;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    for(const n of this.baseNodes.filter(n=>n.mask&&/glass|transparent|window|mirror/i.test(n.name+' '+(n.category_attributes||[]).join(' ')))){
      const image=new Image();image.src=new URL(n.mask,base).href;await image.decode();ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0);
      const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;for(let i=0;i<transparent.length;i++)if(data[i*4]>127)transparent[i]=1;
    }
    const c=graph.camera,p=geometry.attributes.position,index=geometry.index.array,indices=[];
    const clearAt=(x,y,z)=>{const u=Math.round(c.fx*x/-z+c.cx),v=Math.round(c.cy-c.fy*y/-z);return u>=0&&u<c.width&&v>=0&&v<c.height&&transparent[v*c.width+u];};
    for(let i=0;i<index.length;i+=3){const a=index[i],b=index[i+1],d=index[i+2];
      if([a,b,d].some(k=>clearAt(p.getX(k),p.getY(k),p.getZ(k)))||clearAt((p.getX(a)+p.getX(b)+p.getX(d))/3,(p.getY(a)+p.getY(b)+p.getY(d))/3,(p.getZ(a)+p.getZ(b)+p.getZ(d))/3))continue;
      indices.push(a,b,d);
    }
    geometry.setIndex(indices);this.proxy=new THREE.Mesh(geometry,this.depthMaterial);this.occlusion.add(this.proxy);
    this.occlusionAudit={trianglesBefore:index.length/3,trianglesAfter:indices.length/3,antialias:this.v.renderer.getContext().getContextAttributes().antialias};
    this.update();
  }
  render(){
    if(!this.v.manifest)return;
    this.animate();this.positionSpots();
    const r=this.v.renderer,size=r.getDrawingBufferSize(new THREE.Vector2());
    if(this.depthTarget.width!==size.x||this.depthTarget.height!==size.y)this.depthTarget.setSize(size.x,size.y);
    this.occlusionUniforms.depthSize.value.copy(size);
    r.setRenderTarget(this.depthTarget);r.clear();if(this.proxy)r.render(this.occlusion,this.v.camera);r.setRenderTarget(null);
    r.autoClear=false;r.clearDepth();
    r.outputColorSpace=THREE.SRGBColorSpace;r.render(this.objects,this.v.camera);r.outputColorSpace=THREE.LinearSRGBColorSpace;r.autoClear=true;
  }
  async prepareDemo(){const twin=this.v.manifest?.digital_twin;return this.prepare({name:twin?'신규 장비 케이스':'새 화분',category:twin?'container':'small_prop',url:twin?'/demo/equipment-case.glb':'/demo/planter.glb',normalization_applied:true,demo:true,provenance:'authored presentation prop'});}
  spotUI(){
    if(!this.spotLayer){this.spotLayer=document.createElement('div');this.spotLayer.className='spot-layer';this.v.container.append(this.spotLayer);}
    this.spotLayer.replaceChildren();
    for(const spot of this.spots){const b=document.createElement('button');b.className='placement-spot';b.dataset.spot=spot.id;b.innerHTML='<span>＋</span>';b.append(document.createTextNode(spot.label));
      b.onclick=async()=>{try{if(!this.pending)await this.prepareDemo();this.placeAtSpot(spot);}catch(e){this.status(e.message,true);}};this.spotLayer.append(b);}
  }
  spotScreen(spot){const p=new THREE.Vector3(...spot.position).project(this.v.camera),r=this.v.renderer.domElement.getBoundingClientRect();return {x:r.left+(p.x+1)*r.width/2,y:r.top+(1-p.y)*r.height/2,visible:p.z>-1&&p.z<1&&Math.abs(p.x)<.95&&Math.abs(p.y)<.95};}
  positionSpots(){if(!this.spotLayer)return;const rect=this.v.container.getBoundingClientRect();for(const spot of this.spots||[]){const b=this.spotLayer.querySelector(`[data-spot="${spot.id}"]`),p=this.spotScreen(spot);b.hidden=!p.visible||this.items.some(i=>i.spotId===spot.id);b.style.left=(p.x-rect.left)+'px';b.style.top=(p.y-rect.top)+'px';}}
  nearestSpot(x,y){return (this.spots||[]).filter(s=>!this.items.some(i=>i.spotId===s.id)).map(s=>({s,p:this.spotScreen(s)})).filter(({s,p})=>p.visible&&Math.hypot(x-p.x,y-p.y)<s.radius_px).sort((a,b)=>Math.hypot(x-a.p.x,y-a.p.y)-Math.hypot(x-b.p.x,y-b.p.y))[0]?.s;}
  placeAtSpot(spot){
    if(!this.pending)return false;
    if(this.pending.asset.demo){const size=new THREE.Box3().setFromObject(this.pending.object).getSize(new THREE.Vector3());this.pending.object.scale.multiplyScalar(spot.height_m/size.y);}
    return this.commitPlacement({point:new THREE.Vector3(...spot.position),normal:new THREE.Vector3(...spot.normal)},spot);
  }
  animate(){
    const now=performance.now();for(const item of this.items){if(!item.landing)continue;const t=Math.min(1,(now-item.landing.start)/650),ease=1-(1-t)**3;
      item.object.position.lerpVectors(item.landing.from,item.landing.to,ease);item.object.position.y+=Math.sin(t*Math.PI)*.035;
      item.shadow.material.opacity=.3+.7*ease;if(t===1){item.object.position.copy(item.landing.to);item.landing=null;}}
  }
  softenOcclusion(material){
    material.transparent=true;
    const original=material.onBeforeCompile;
    material.onBeforeCompile=shader=>{
      original?.call(material,shader,this.v.renderer);Object.assign(shader.uniforms,this.occlusionUniforms);
      shader.fragmentShader='uniform sampler2D sceneDepth; uniform vec2 depthSize; uniform float depthNear; uniform float depthFar;\nfloat linearSceneDepth(float z){return depthNear*depthFar/(depthFar-z*(depthFar-depthNear));}\n'+shader.fragmentShader;
      shader.fragmentShader=shader.fragmentShader.replace('#include <dithering_fragment>',`#include <dithering_fragment>
        float visibility=0.0;float objectDepth=linearSceneDepth(gl_FragCoord.z);
        for(int dx=-1;dx<=1;dx++)for(int dy=-1;dy<=1;dy++){
          float backgroundDepth=linearSceneDepth(texture2D(sceneDepth,(gl_FragCoord.xy+vec2(float(dx),float(dy)))/depthSize).x);
          visibility+=smoothstep(-0.025,0.025,backgroundDepth-objectDepth)/9.0;
        }
        gl_FragColor.a*=visibility;if(gl_FragColor.a<0.005)discard;`);
    };
    material.customProgramCacheKey=()=> 'scene-soft-depth-v1';material.needsUpdate=true;
  }
  ui(){
    $('#placement').innerHTML='<div class="section-label spaced">02 / OBJECTS</div><h2>물체 배치</h2><label>물체 종류<select id="category"></select></label><label class="upload">+ 생성된 GLB 선택<input id="glb" type="file" accept=".glb"></label><p class="muted" id="objectHint">GLB를 선택한 뒤 바닥 또는 상판을 클릭하세요.</p><div class="controls"><button data-mode="translate">이동</button><button data-mode="rotate">회전</button><button data-mode="scale">크기</button></div><div class="controls"><button id="snap">지지면 스냅</button><button id="remove">삭제</button></div><button id="export">결과 저장</button><div id="objects"></div>';
    fetch('/scene-api/policies').then(r=>r.json()).then(p=>{const auto=document.createElement('option');auto.value='auto';auto.textContent='자동 · 파일명으로 종류 선택';$('#category').append(auto);for(const x of p){const o=document.createElement('option');o.value=x.category_id;o.textContent=x.category_id+' · '+x.target_size_m+' m';$('#category').append(o);}$('#category').value='auto';}).catch(()=>this.status('크기 정책을 불러오지 못했습니다.',true));
    $('#glb').onchange=async(e)=>{
      const f=e.target.files[0];if(!f)return;
      if(!this.v.manifest){this.status('배경을 먼저 선택하세요.');e.target.value='';return;}
      try{
        this.status('GLB 준비 중…');
        const form=new FormData();form.append('file',f);
        const r=await fetch('/scene-api/assets?category='+encodeURIComponent($('#category').value),{method:'POST',body:form});
        if(!r.ok)throw new Error(await r.text());
        const asset=await r.json();await this.prepare(asset);
      }catch(err){this.status(err.message,true);}finally{e.target.value='';}
    };
    document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>this.controls.setMode(b.dataset.mode));
    $('#snap').onclick=()=>{this.snapSelected();this.update();};
    $('#remove').onclick=()=>{if(!this.selected)return;const item=this.selected;this.controls.detach();this.objects.remove(item.object,item.shadow);dispose(item.object);dispose(item.shadow);this.items=this.items.filter(x=>x!==item);this.selected=null;this.update();};
    $('#export').onclick=async()=>{try{const result=await this.export();download(result.image,'scene-original.png');download(new Blob([JSON.stringify(result.graph,null,2)],{type:'application/json'}),'scene-graph.json');this.status('원본 시점 이미지와 scene graph를 저장했습니다.');const toast=document.createElement('div');toast.className='save-toast';toast.textContent='✓ 원본 이미지와 그래프를 저장했어요';this.v.container.append(toast);setTimeout(()=>toast.remove(),3500);}catch(e){this.status(e.message,true);}};
    const demo=document.createElement('button');demo.id='demoProp';demo.className='demo-prop';demo.textContent='＋ 시연 화분 선택';demo.onclick=()=>this.prepareDemo().catch(e=>this.status(e.message,true));$('#placement').prepend(demo);
  }
  async prepare(asset){
    const gltf=await new GLTFLoader().loadAsync(asset.url);
    let object=gltf.scene;
    if(asset.normalization_applied===false){
      const n=asset.normalization,s=n.scale_applied||1,min=n.bbox_min_before,max=n.bbox_max_before;
      if(min&&max){const normalized=new THREE.Group();normalized.add(object);normalized.scale.setScalar(s);
        normalized.position.set(-(min[0]+max[0])/2*s,-min[1]*s,-(min[2]+max[2])/2*s);
        object=new THREE.Group();object.add(normalized);}
    }
    // The existing material package's tint and EV controls also apply in 3D.
    const settings=asset.material_settings||{},gain=2**Math.max(-3,Math.min(3,Number(settings.viewerExposureEV)||0));
    object.traverse(n=>{for(const material of Array.isArray(n.material)?n.material:[n.material])if(material?.color){
      if(settings.viewerBaseTint)material.color.set(settings.viewerBaseTint);
      material.color.multiplyScalar(gain);material.needsUpdate=true;
      material.color.multiply(new THREE.Color(this.v.manifest.presentation?.object_tint||'#ffffff'));
      this.softenOcclusion(material);
    }});
    if(this.pending)dispose(this.pending.object);
    this.pending={id:crypto.randomUUID(),name:asset.name,object,asset,normal:new THREE.Vector3(0,1,0)};
    asset.thumbnail=this.objectThumbnail(object);
    if(asset.demo)this.pending.name=asset.name;
    $('#objectHint').textContent=asset.name+' · '+asset.category+' · 배치할 바닥이나 상판을 클릭하세요.';
    this.status('지지면을 클릭하여 물체를 배치하세요.');
  }
  generatedUI(){
    const row=document.createElement('div');row.className='generated-assets';
    row.innerHTML='<label>생성된 물체<select id="generatedAsset"><option value="">생성 결과 없음</option></select></label><div class="controls"><button id="refreshGenerated">새로고침</button><button id="placeGenerated">씬에 가져오기</button></div>';
    $('#placement').append(row);
    const refresh=async()=>{
      try{const r=await fetch('/scene-api/generated-assets');if(!r.ok)throw Error('생성 결과 조회 실패');
      const items=await r.json();$('#generatedAsset').replaceChildren();
      row.hidden=!items.length;
      for(const item of items){const o=document.createElement('option');o.value=item.job_id;o.textContent=item.name;$('#generatedAsset').append(o);}
      if(!items.length){const o=document.createElement('option');o.value='';o.textContent='생성 결과 없음';$('#generatedAsset').append(o);}
      }catch(e){this.status(e.message,true);}
    };
    $('#refreshGenerated').onclick=refresh;
    $('#placeGenerated').onclick=()=>this.importGenerated($('#generatedAsset').value).catch(e=>this.status(e.message,true));
    refresh();
  }
  objectThumbnail(object){
    const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});renderer.setSize(160,120);renderer.outputColorSpace=THREE.SRGBColorSpace;
    const scene=new THREE.Scene(),copy=object.clone(true);scene.add(copy,new THREE.HemisphereLight(0xffffff,0x69755e,2));
    const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(2,3,4);scene.add(light);
    // Clone unmodified materials: the placement depth shader needs the main view.
    copy.traverse(n=>{if(n.material)n.material=Array.isArray(n.material)?n.material.map(m=>m.clone()):n.material.clone();});
    const box=new THREE.Box3().setFromObject(copy),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),d=Math.max(size.x,size.y,size.z);
    const camera=new THREE.PerspectiveCamera(35,4/3,.001,100);camera.position.copy(center).add(new THREE.Vector3(d*1.1,d*.65,d*1.6));camera.lookAt(center);renderer.render(scene,camera);
    const url=renderer.domElement.toDataURL('image/png');copy.traverse(n=>{for(const m of Array.isArray(n.material)?n.material:[n.material])m?.dispose();});renderer.dispose();renderer.forceContextLoss();return url;
  }
  async importGenerated(job){
    if(!job)return;
    if(!this.v.manifest)throw Error('배경을 먼저 선택하세요.');
    const r=await fetch('/scene-api/generated-assets/'+encodeURIComponent(job),{method:'POST'});
    if(!r.ok)throw Error(await r.text());
    await this.prepare(await r.json());
  }
  supportHit(ray){
    if(!this.v.surface)return null;
    this.v.surface.updateMatrixWorld(true);
    const hits=ray.intersectObject(this.v.surface,false);
    // Only accept the nearest visible surface; never tunnel through a wall.
    const h=hits[0];if(!h)return null;
    const normal=h.face.normal.clone().transformDirection(this.v.surface.matrixWorld);
    if(normal.y<0)normal.negate();
    if(normal.y<.65)return null;
    h.normal=normal;return h;
  }
  placeFromRay(ray){
    const h=this.supportHit(ray);
    if(!h){this.status('평평한 지지면이 확인되지 않았습니다. 다른 위치를 선택하세요.');return false;}
    return this.commitPlacement(h);
  }
  commitPlacement(h,spot=null){
    const item=this.pending;item.object.position.copy(h.point);item.normal.copy(h.normal);item.supportTarget=spot?.support;item.spotId=spot?.id;
    item.supportPoint=h.point.clone();item.supportId='support-'+item.id;item.lastPosition=item.object.position.clone();
    this.measureSupport(item,h);
    if(!this.resolveCollision(item)){this.status('물체가 들어갈 빈 지지면을 찾지 못했습니다. 다른 위치를 선택하세요.');return false;}
    item.shadow=this.shadow(item);
    this.objects.add(item.object,item.shadow);this.items.push(item);this.pending=null;
    item.landing={start:performance.now(),from:item.object.position.clone().add(new THREE.Vector3(-.035,.10,.02)),to:item.object.position.clone()};
    $('#objectHint').textContent=item.name+' 선택됨';this.select(item);this.update();this.status('물체를 배치했습니다. 기즈모로 조절하세요.');return true;
  }
  shadow(item){
    const canvas=document.createElement('canvas');canvas.width=canvas.height=128;
    const ctx=canvas.getContext('2d'),g=ctx.createRadialGradient(64,64,6,64,64,64);
    g.addColorStop(0,'rgba(0,0,0,.45)');g.addColorStop(.5,'rgba(0,0,0,.22)');g.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g;ctx.fillRect(0,0,128,128);
    const plane=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(canvas),transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2}));
    this.softenOcclusion(plane.material);
    plane.renderOrder=1;return plane;
  }
  overlaps(item){
    const box=new THREE.Box3().setFromObject(item.object);box.min.y+=.035;box.max.y-=.01;
    // A wall mask can wrap several room walls; its AABB encloses empty room.
    // Structural surfaces are constrained by the depth support ray instead.
    const obstacles=[...this.baseNodes.filter(n=>n.box&&!isStructure(n)&&n.id!==item.supportTarget&&!(item.spotId&&/shelf/.test(n.name))),...this.items.filter(n=>n!==item)];
    return obstacles.some(n=>{const b=n.object?new THREE.Box3().setFromObject(n.object):new THREE.Box3(new THREE.Vector3(...n.box.min),new THREE.Vector3(...n.box.max));return box.intersectsBox(b);});
  }
  resolveCollision(item){
    const start=item.object.position.clone();
    if(!this.overlaps(item))return true;
    const offsets=[];for(let x=-20;x<=20;x++)for(let z=-20;z<=20;z++)offsets.push([x*.08,z*.08]);offsets.sort((a,b)=>Math.hypot(...a)-Math.hypot(...b));
    for(const [dx,dz] of offsets){
      item.object.position.copy(start).add(new THREE.Vector3(dx,0,dz));
      if(this.overlaps(item))continue;
      const box=new THREE.Box3().setFromObject(item.object),center=box.getCenter(new THREE.Vector3());
      let hit=this.supportHit(new THREE.Raycaster(new THREE.Vector3(center.x,start.y+.25,center.z),new THREE.Vector3(0,-1,0),0,.5));
      if(!hit){
        const floor=this.baseNodes.find(n=>n.plane&&n.name==='floor'&&box.min.x>=n.box.min[0]&&box.max.x<=n.box.max[0]&&box.min.z>=n.box.min[2]&&box.max.z<=n.box.max[2]);
        if(floor){const [a,b,c]=floor.plane.height_coefficients;hit={point:new THREE.Vector3(center.x,a*center.x+b*center.z+c,center.z),normal:new THREE.Vector3(-a,1,-b).normalize(),estimatedFloor:floor.id};}
      }
      if(!hit||Math.abs(hit.point.y-start.y)>.15)continue;
      item.object.position.y+=hit.point.y-box.min.y;
      if(this.overlaps(item))continue;
      item.supportPoint=hit.point.clone();item.normal.copy(hit.normal);this.measureSupport(item,hit);item.lastPosition=item.object.position.clone();
      item.collisionResolution={method:'nearest-valid-surface-grid',step_m:.08,offset_m:[dx,dz],estimatedFloor:hit.estimatedFloor||null};return true;
    }
    item.object.position.copy(start);return false;
  }
  measureSupport(item,hit){
    const pos=this.v.surface.geometry.attributes.position,points=[];
    for(let i=0;i<pos.count;i++){
      const v=new THREE.Vector3().fromBufferAttribute(pos,i),d=v.clone().sub(hit.point);
      if(d.length()<.6&&Math.abs(d.dot(hit.normal))<.04)points.push(v);
    }
    item.supportBox=new THREE.Box3().setFromPoints(points.length?points:[hit.point]);
  }
  snapSelected(){
    const item=this.selected;if(!item)return;
    const previousPosition=item.lastPosition.clone();
    const box=new THREE.Box3().setFromObject(item.object),center=box.getCenter(new THREE.Vector3());
    const origin=new THREE.Vector3(center.x,box.max.y+.5,center.z);
    const ray=new THREE.Raycaster(origin,new THREE.Vector3(0,-1,0),0,20),hit=this.supportHit(ray);
    if(!hit){
      const b=item.supportBox,p=item.supportPoint,n=item.normal;
      if(center.x>=b.min.x&&center.x<=b.max.x&&center.z>=b.min.z&&center.z<=b.max.z){
        const y=p.y-(n.x*(center.x-p.x)+n.z*(center.z-p.z))/n.y;
        item.object.position.y+=y-box.min.y;if(!this.resolveCollision(item))item.object.position.copy(item.lastPosition);item.lastPosition=item.object.position.clone();return;
      }
      item.object.position.copy(item.lastPosition);this.status('지지면 밖입니다. 마지막 배치 위치로 돌아갑니다.');return;}
    item.object.position.y+=hit.point.y-box.min.y;item.supportPoint=hit.point.clone();item.normal.copy(hit.normal);item.lastPosition=item.object.position.clone();
    this.measureSupport(item,hit);
    if(!this.resolveCollision(item))item.object.position.copy(previousPosition);
    item.lastPosition=item.object.position.clone();
  }
  select(item){this.selected=item;if(item)this.selectedGraphId=item.id;if(item)this.controls.attach(item.object);else this.controls.detach();this.update();}
  update(){
    for(const item of this.items){
      item.object.scale.clampScalar(.05,20);
      item.object.updateMatrixWorld(true);
      const box=new THREE.Box3().setFromObject(item.object),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());
      item.box={min:box.min.toArray(),max:box.max.toArray()};
      item.shadow.position.set(center.x,(item.box.min[1])+.008,center.z);
      item.shadow.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),item.normal);
      item.shadow.scale.set(Math.max(.08,size.x*1.35),Math.max(.08,size.z*1.35),1);
      item.shadow.visible=Math.abs(box.min.y-item.supportPoint.y)<.1;
    }
    const supports=this.items.map(x=>({id:x.supportId,name:'지지면',source:'depth-surface',plane:{height_coefficients:[-x.normal.x/x.normal.y,-x.normal.z/x.normal.y,x.supportPoint.dot(x.normal)/x.normal.y],tolerance_m:.04},box:{min:x.supportBox.min.toArray(),max:x.supportBox.max.toArray()}}));
    const nodes=[...this.baseNodes,...supports,...this.items.map(x=>({id:x.id,name:x.name,thumbnail:x.asset.thumbnail,box:x.box,source:'placed-glb',asset:x.asset,transform:{position:x.object.position.toArray(),quaternion:x.object.quaternion.toArray(),scale:x.object.scale.toArray()}}))];
    const contacts=[];
    for(const item of this.items){
      const center=new THREE.Box3().setFromObject(item.object).getCenter(new THREE.Vector3());
      const p=item.supportPoint,n=item.normal;
      const supportY=p.y-(n.x*(center.x-p.x)+n.z*(center.z-p.z))/n.y;
      if(Math.abs(item.box.min[1]-supportY)>.04)continue;
      const support=this.baseNodes.find(n=>isSupport(n)&&n.box&&item.supportPoint.x>=n.box.min[0]-.05&&item.supportPoint.x<=n.box.max[0]+.05&&item.supportPoint.z>=n.box.min[2]-.05&&item.supportPoint.z<=n.box.max[2]+.05&&Math.abs(item.supportPoint.y-supportHeight(n,item))<.05);
      const target=item.supportTarget||support?.id||item.supportId;
      contacts.push({source:item.id,target,relation:'on',method:'raycast-support-contact'});
    }
    this.graph={...this.baseGraph,version:1,scene_id:this.v.manifest?.id,coordinate_system:'three-camera-x-right-y-up-z-back',units:'meters',nodes,edges:relations(nodes,contacts),geometry_status:'monocular-estimate'};
    if(this.baseGraph?.curated)this.graph.edges=[...this.baseGraph.edges,...contacts];
    if(this.baseGraph?.curated){
      this.graph.nodes=this.graph.nodes.filter(n=>n.source!=='depth-surface'||this.graph.edges.some(e=>e.target===n.id));
      this.graph.summary=this.baseGraph.summary+this.items.map(i=>{const support=this.baseNodes.find(n=>n.id===i.supportTarget);return ' '+i.name+'은 '+(support?.label||'선택한 지지면')+' 위에 놓여 있습니다.';}).join('');
    }
    enrichAssets(this.graph,this.assetRegistry||{ids:new Map(),next:1});
    this.graphUI();
  }
  graphUI(){
    $('#objects').replaceChildren();
    for(const item of this.items){const b=document.createElement('button');b.className='node'+(item===this.selected?' active':'');b.textContent=item.name;b.onclick=()=>this.select(item);$('#objects').append(b);}
    drawGraph($('#graph'),this.graph,this.selectedGraphId,id=>{
      const item=this.items.find(x=>x.id===id);
      if(item){this.selectedGraphId=id;this.select(item);}
      else {const node=this.graph.nodes.find(x=>x.id===id);if(node)this.highlight(node);}
    },{base:this.v.base,onHover:id=>this.outline(this.graph.nodes.find(n=>n.id===(id||this.selectedGraphId)))});
  }

  outline(node){
    if(this.boxHelper){this.objects.remove(this.boxHelper);dispose(this.boxHelper);this.boxHelper=null;}
    if(!node)return;
    if(node.outline?.length>2){const points=node.outline.map(p=>new THREE.Vector3(...p));const geometry=new THREE.BufferGeometry().setFromPoints(points);this.boxHelper=new THREE.LineLoop(geometry,new THREE.LineBasicMaterial({color:0xc9ffaf,depthTest:false,transparent:true,opacity:.95}));this.boxHelper.renderOrder=10;}
    else if(node.box)this.boxHelper=new THREE.Box3Helper(new THREE.Box3(new THREE.Vector3(...node.box.min),new THREE.Vector3(...node.box.max)),0xb8dfa4);
    if(this.boxHelper)this.objects.add(this.boxHelper);
  }
  highlight(node){
    this.selectedGraphId=node.id;this.graphUI();
    this.outline(node);
    this.status(node.name+' 선택됨');
    this.showAssetCard(node);
  }
  showAssetCard(node){
    let card=document.querySelector('#assetSpec');if(!card){card=document.createElement('div');card.id='assetSpec';document.querySelector('#graph').after(card);}
    card.replaceChildren();const title=document.createElement('h3');title.textContent=(node.asset_id||'신규 자산')+' · '+(node.asset_name||node.label||node.name);card.append(title);
    const d=node.dimensions_m||{},rows=[['분류',node.classification],['구역',node.zone],['크기 W×D×H',`${d.width??0} × ${d.depth??0} × ${d.height??0} m (추정)`],['등록 출처',node.registration_source],['종류',node.specification?.kind],['재질',node.specification?.materials?.join(', ')||'미확인'],['상태',node.status]];
    for(const [key,value]of rows){const p=document.createElement('p');p.textContent=key+' · '+(value||'미확인');card.append(p);}
  }
  pickGraph(ray){
    let closest=null,distance=Infinity;
    for(const node of this.baseNodes){if(!node.box)continue;const hit=ray.ray.intersectBox(new THREE.Box3(new THREE.Vector3(...node.box.min),new THREE.Vector3(...node.box.max)),new THREE.Vector3());if(hit&&hit.distanceTo(ray.ray.origin)<distance){closest=node;distance=hit.distanceTo(ray.ray.origin);}}
    if(closest)this.highlight(closest);
  }
  async export(){
    if(!this.v.manifest)throw Error('배경을 먼저 선택하세요.');
    const v=this.v,pos=v.camera.position.clone(),target=v.controls.target.clone(),visible=this.helper.visible,zoom=v.camera.zoom;
    for(const item of this.items)if(item.landing){item.object.position.copy(item.landing.to);item.landing=null;}
    this.helper.visible=false;const highlight=this.boxHelper?.visible;if(this.boxHelper)this.boxHelper.visible=false;
    const surface=v.surface.visible;v.surface.visible=false;
    try{
      v.reset();await new Promise(r=>setTimeout(r,500));
      v.renderer.render(v.scene,v.camera);this.render();
      const image=await new Promise(r=>v.renderer.domElement.toBlob(r,'image/png'));
      if(!image)throw Error('이미지 내보내기 실패');
      return {image,graph:{...this.graph,camera:v.manifest.camera,alignment:v.manifest.alignment}};
    }finally{v.camera.position.copy(pos);v.camera.zoom=zoom;v.camera.updateProjectionMatrix();v.controls.target.copy(target);v.controls.update();this.helper.visible=visible;v.surface.visible=surface;if(this.boxHelper)this.boxHelper.visible=highlight;}
  }
}
