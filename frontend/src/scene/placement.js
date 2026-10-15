import {drawGraph} from './graph-panel.js';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {TransformControls} from 'three/addons/controls/TransformControls.js';
import {relations} from './relations.js';
const $=s=>document.querySelector(s);
function dispose(object){object.traverse(n=>{n.geometry?.dispose();for(const m of Array.isArray(n.material)?n.material:[n.material]){if(m){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}}});}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
export class Placement {
  constructor(viewer,status){
    this.v=viewer;this.status=status;this.items=[];this.baseNodes=[];this.graph={nodes:[],edges:[]};this.selected=null;
    this.objects=new THREE.Scene();this.objects.add(new THREE.HemisphereLight(0xffffff,0x6a755d,2));
    const light=new THREE.DirectionalLight(0xfff5e5,2);light.position.set(-2,4,2);this.objects.add(light);
    this.occlusion=new THREE.Scene();this.depthMaterial=new THREE.MeshBasicMaterial({colorWrite:false,side:THREE.DoubleSide});
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
      if(this.pending){this.placeFromRay(this.ray);return;}
      const hits=this.ray.intersectObjects(this.items.map(x=>x.object),true);
      if(hits[0]){const item=this.items.find(x=>{let found=false;x.object.traverse(n=>{if(n===hits[0].object)found=true;});return found;});this.select(item);}
      else this.pickGraph(this.ray);
    });
    viewer.afterRender=()=>this.render();
    window.addEventListener('scene-loaded',()=>this.loadGraph().catch(e=>this.status(e.message,true)));
    this.ui();
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
    if(this.proxy)this.occlusion.remove(this.proxy);
    this.proxy=new THREE.Mesh(this.v.surface.geometry,this.depthMaterial);this.occlusion.add(this.proxy);
    this.update();
  }
  render(){
    if(!this.v.manifest)return;
    const r=this.v.renderer;r.autoClear=false;r.clearDepth();
    if(this.proxy)r.render(this.occlusion,this.v.camera);
    r.outputColorSpace=THREE.SRGBColorSpace;r.render(this.objects,this.v.camera);r.outputColorSpace=THREE.LinearSRGBColorSpace;r.autoClear=true;
  }
  ui(){
    $('#placement').innerHTML='<div class="section-label spaced">02 / OBJECTS</div><h2>물체 배치</h2><label>물체 종류<select id="category"></select></label><label class="upload">+ 생성된 GLB 선택<input id="glb" type="file" accept=".glb"></label><p class="muted" id="objectHint">GLB를 선택한 뒤 바닥 또는 상판을 클릭하세요.</p><div class="controls"><button data-mode="translate">이동</button><button data-mode="rotate">회전</button><button data-mode="scale">크기</button></div><div class="controls"><button id="snap">지지면 스냅</button><button id="remove">삭제</button></div><button id="export">결과 저장</button><div id="objects"></div>';
    fetch('/scene-api/policies').then(r=>r.json()).then(p=>{for(const x of p){const o=document.createElement('option');o.value=x.category_id;o.textContent=x.category_id;$('#category').append(o);}$('#category').value='small_prop';}).catch(()=>this.status('크기 정책을 불러오지 못했습니다.',true));
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
    $('#export').onclick=async()=>{try{const result=await this.export();download(result.image,'scene-original.png');download(new Blob([JSON.stringify(result.graph,null,2)],{type:'application/json'}),'scene-graph.json');this.status('원본 시점 이미지와 scene graph를 저장했습니다.');}catch(e){this.status(e.message,true);}};
  }
  async prepare(asset){
    const gltf=await new GLTFLoader().loadAsync(asset.url);
    if(this.pending)dispose(this.pending.object);
    this.pending={id:crypto.randomUUID(),name:asset.name,object:gltf.scene,asset,normal:new THREE.Vector3(0,1,0)};
    $('#objectHint').textContent=asset.name+' · 배치할 바닥이나 상판을 클릭하세요.';
    this.status('지지면을 클릭하여 물체를 배치하세요.');
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
    const item=this.pending;item.object.position.copy(h.point);item.normal.copy(h.normal);
    item.supportPoint=h.point.clone();item.supportId='support-'+item.id;item.lastPosition=item.object.position.clone();
    this.measureSupport(item,h);
    item.shadow=this.shadow(item);
    this.objects.add(item.object,item.shadow);this.items.push(item);this.pending=null;
    $('#objectHint').textContent=item.name+' 선택됨';this.select(item);this.update();this.status('물체를 배치했습니다. 기즈모로 조절하세요.');return true;
  }
  shadow(item){
    const canvas=document.createElement('canvas');canvas.width=canvas.height=128;
    const ctx=canvas.getContext('2d'),g=ctx.createRadialGradient(64,64,6,64,64,64);
    g.addColorStop(0,'rgba(0,0,0,.45)');g.addColorStop(.5,'rgba(0,0,0,.22)');g.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g;ctx.fillRect(0,0,128,128);
    const plane=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(canvas),transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2}));
    plane.renderOrder=1;return plane;
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
    const box=new THREE.Box3().setFromObject(item.object),center=box.getCenter(new THREE.Vector3());
    const origin=new THREE.Vector3(center.x,box.max.y+.5,center.z);
    const ray=new THREE.Raycaster(origin,new THREE.Vector3(0,-1,0),0,20),hit=this.supportHit(ray);
    if(!hit){
      const b=item.supportBox,p=item.supportPoint,n=item.normal;
      if(center.x>=b.min.x&&center.x<=b.max.x&&center.z>=b.min.z&&center.z<=b.max.z){
        const y=p.y-(n.x*(center.x-p.x)+n.z*(center.z-p.z))/n.y;
        item.object.position.y+=y-box.min.y;item.lastPosition=item.object.position.clone();return;
      }
      item.object.position.copy(item.lastPosition);this.status('지지면 밖입니다. 마지막 배치 위치로 돌아갑니다.');return;}
    item.object.position.y+=hit.point.y-box.min.y;item.supportPoint=hit.point.clone();item.normal.copy(hit.normal);item.lastPosition=item.object.position.clone();
    this.measureSupport(item,hit);
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
    const supports=this.items.map(x=>({id:x.supportId,name:'지지면',source:'depth-surface',box:{min:x.supportBox.min.toArray(),max:x.supportBox.max.toArray()}}));
    const nodes=[...this.baseNodes,...supports,...this.items.map(x=>({id:x.id,name:x.name,box:x.box,source:'placed-glb',asset:x.asset,transform:{position:x.object.position.toArray(),quaternion:x.object.quaternion.toArray(),scale:x.object.scale.toArray()}}))];
    const contacts=[];
    for(const item of this.items){
      const center=new THREE.Box3().setFromObject(item.object).getCenter(new THREE.Vector3());
      const p=item.supportPoint,n=item.normal;
      const supportY=p.y-(n.x*(center.x-p.x)+n.z*(center.z-p.z))/n.y;
      if(Math.abs(item.box.min[1]-supportY)>.04)continue;
      const support=this.baseNodes.find(n=>n.box&&item.supportPoint.x>=n.box.min[0]-.05&&item.supportPoint.x<=n.box.max[0]+.05&&item.supportPoint.z>=n.box.min[2]-.05&&item.supportPoint.z<=n.box.max[2]+.05&&Math.abs(item.supportPoint.y-n.box.max[1])<.12);
      const target=support?.id||item.supportId;
      contacts.push({source:item.id,target,relation:'on',method:'raycast-support-contact'});
    }
    this.graph={...this.baseGraph,version:1,scene_id:this.v.manifest?.id,coordinate_system:'three-camera-x-right-y-up-z-back',units:'meters',nodes,edges:relations(nodes,contacts),geometry_status:'monocular-estimate'};
    this.graphUI();
  }
  graphUI(){
    $('#objects').replaceChildren();
    for(const item of this.items){const b=document.createElement('button');b.className='node'+(item===this.selected?' active':'');b.textContent=item.name;b.onclick=()=>this.select(item);$('#objects').append(b);}
    drawGraph($('#graph'),this.graph,this.selectedGraphId,id=>{
      const item=this.items.find(x=>x.id===id);
      if(item){this.selectedGraphId=id;this.select(item);}
      else {const node=this.graph.nodes.find(x=>x.id===id);if(node)this.highlight(node);}
    });
  }

  highlight(node){
    this.selectedGraphId=node.id;this.graphUI();
    if(this.boxHelper){this.objects.remove(this.boxHelper);dispose(this.boxHelper);}
    if(node.box){this.boxHelper=new THREE.Box3Helper(new THREE.Box3(new THREE.Vector3(...node.box.min),new THREE.Vector3(...node.box.max)),0xb8dfa4);this.objects.add(this.boxHelper);}
    this.status(node.name+' 선택됨');
  }
  pickGraph(ray){
    let closest=null,distance=Infinity;
    for(const node of this.baseNodes){if(!node.box)continue;const hit=ray.ray.intersectBox(new THREE.Box3(new THREE.Vector3(...node.box.min),new THREE.Vector3(...node.box.max)),new THREE.Vector3());if(hit&&hit.distanceTo(ray.ray.origin)<distance){closest=node;distance=hit.distanceTo(ray.ray.origin);}}
    if(closest)this.highlight(closest);
  }
  async export(){
    if(!this.v.manifest)throw Error('배경을 먼저 선택하세요.');
    const v=this.v,pos=v.camera.position.clone(),target=v.controls.target.clone(),visible=this.helper.visible;
    this.helper.visible=false;const highlight=this.boxHelper?.visible;if(this.boxHelper)this.boxHelper.visible=false;
    const surface=v.surface.visible;v.surface.visible=false;
    try{
      v.reset();await new Promise(r=>setTimeout(r,500));
      v.renderer.render(v.scene,v.camera);this.render();
      const image=await new Promise(r=>v.renderer.domElement.toBlob(r,'image/png'));
      if(!image)throw Error('이미지 내보내기 실패');
      return {image,graph:{...this.graph,camera:v.manifest.camera,alignment:v.manifest.alignment}};
    }finally{v.camera.position.copy(pos);v.controls.target.copy(target);v.controls.update();this.helper.visible=visible;v.surface.visible=surface;if(this.boxHelper)this.boxHelper.visible=highlight;}
  }
}
