import * as THREE from 'three';
import {boxDistance} from './asset-model.js';
const $=s=>document.querySelector(s);
export class PlacementSimulation{
 constructor(p){
  this.p=p;this.clearance=.5;this.history=[];
  const oldCommit=p.commitPlacement.bind(p);p.commitPlacement=(h,s)=>p.v.manifest?.digital_twin?this.begin(h,s):oldCommit(h,s);
  const oldUpdate=p.update.bind(p);p.update=()=>{oldUpdate();this.inspect();window.dispatchEvent(new CustomEvent('asset-register-changed'));};
  const oldSnap=p.snapSelected.bind(p);p.snapSelected=()=>{if(this.draft&&p.selected===this.draft){const hit=p.supportHit(p.supportRay(this.draft.object.position));if(hit)this.draft.supportPoint.copy(hit.point);p.ground(this.draft);this.inspect();}else oldSnap();};
  const oldRender=p.render.bind(p);p.render=()=>{this.visuals();oldRender();};
  const oldLoad=p.loadGraph.bind(p);p.loadGraph=async(...args)=>{this.cancel();this.history=[];await oldLoad(...args);this.panel.hidden=!p.v.manifest.digital_twin;$('#demoProp').textContent=p.v.manifest.digital_twin?'＋ 시연 장비 케이스':'＋ 시연 화분 선택';};
  const oldPrepare=p.prepare.bind(p);p.prepare=async a=>{this.cancel();return oldPrepare(a);};
  this.panel=document.createElement('div');this.panel.id='simulation';this.panel.hidden=true;
  this.panel.innerHTML='<h3>신규 자산 반입 시뮬레이션</h3><p class="muted">위치를 검토한 뒤 반입을 확정하세요.</p><label>최소 이격 거리 (m)<input id="clearance" type="number" min="0" max="5" step="0.1" value="0.5"></label><div id="simulationResult" role="status">GLB를 선택하고 지지면을 클릭하세요.</div><div class="controls"><button id="findSafe">빈 위치 찾기</button><button id="confirmAsset" disabled>반입 확정</button><button id="cancelAsset">취소</button></div>';
  $('#placement').prepend(this.panel);
  const sizeLabel=document.createElement('label');sizeLabel.textContent='반입 자산 높이 (m)';const sizeInput=document.createElement('input');sizeInput.id='assetHeight';sizeInput.type='number';sizeInput.min='.02';sizeInput.max='20';sizeInput.step='.01';sizeInput.value='1';sizeLabel.append(sizeInput);$('#simulationResult').before(sizeLabel);
  sizeInput.onchange=()=>{const item=this.draft;if(!item)return;const target=Math.max(.02,Math.min(20,Number(sizeInput.value)||1));item.object.scale.multiplyScalar(target/p.height(item));p.ground(item);this.inspect();};
  $('#clearance').onchange=()=>{this.clearance=Math.max(0,Math.min(5,Number($('#clearance').value)||0));this.inspect();};
  $('#findSafe').onclick=()=>this.findSafe();$('#confirmAsset').onclick=()=>this.confirm();$('#cancelAsset').onclick=()=>this.cancel();
 }
 begin(hit,spot){
  this.cancel();const p=this.p,item=p.pending;if(!item)return false;
  item.object.position.copy(hit.point);item.normal.copy(hit.normal);item.supportTarget=spot?.support;item.spotId=spot?.id;item.supportPoint=hit.point.clone();item.supportId='support-'+item.id;item.lastPosition=hit.point.clone();
  p.orient(item);p.ground(item);
  p.measureSupport(item,hit);item.shadow=p.shadow(item);p.objects.add(item.object,item.shadow);p.pending=null;this.draft=item;p.selected=item;p.selectedGraphId=null;p.controls.attach(item.object);
  $('#assetHeight').value=p.height(item).toFixed(2);
  this.inspect();p.status('반입 미리보기입니다. 간섭과 이격 거리를 확인한 뒤 확정하세요.');return true;
 }
 obstacles(item){return [...this.p.baseNodes.filter(n=>n.box&&n.id!==item.supportTarget&&!/^(floor|wall|ceiling|table)$/.test(n.name)),...this.p.items.filter(i=>i!==item).map(i=>({id:i.id,name:i.name,box:this.box(i)}))];}
 box(item){item.object.updateMatrixWorld(true);const b=new THREE.Box3().setFromObject(item.object);return {min:b.min.toArray(),max:b.max.toArray()};}
 check(item){
  const box=this.box(item),hits=[],near=[];
  for(const n of this.obstacles(item)){
   const overlaps=[0,1,2].every(i=>Math.min(box.max[i],n.box.max[i])-Math.max(box.min[i],n.box.min[i])>.012);
   const distance=boxDistance(box,n.box);const row={id:n.id,name:n.label||n.name,distance_m:distance};
   if(overlaps)hits.push(row);else if(distance<this.clearance)near.push(row);
  }
  return {state:hits.length?'collision':near.length?'clearance':'clear',collisions:hits,near,required_clearance_m:this.clearance,geometry:'estimated AABB',checked_at:new Date().toISOString()};
 }
 inspect(){
  const item=this.draft||this.p.selected;if(!item?.object){this.result=null;$('#confirmAsset').disabled=true;return;}
  this.result=this.check(item);item.review=this.result;const {state,collisions,near}=this.result;
  if(this.lastState!==state){this.history.push({event:'placement-check',name:item.name,result:this.result});this.lastState=state;}
  $('#simulationResult').className='simulation-result '+state;
  $('#simulationResult').textContent=state==='collision'?`간섭 ${collisions.length}건 · ${collisions.map(n=>n.name).join(', ')}`:state==='clearance'?`이격 부족 ${near.length}건 · 최소 ${Math.min(...near.map(n=>n.distance_m)).toFixed(2)}m / 기준 ${this.clearance.toFixed(2)}m`:`간섭 없음 · 이격 ${this.clearance.toFixed(2)}m 기준 충족`;
  $('#confirmAsset').disabled=!this.draft||state!=='clear';
  if(this.draft&&item.object.position.clone().sub(item.supportPoint).projectOnPlane(this.p.up).length()>.04){
   const hit=this.p.supportHit(this.p.supportRay(item.object.position));
   if(!hit){this.result.state='unsupported';$('#simulationResult').className='simulation-result clearance';$('#simulationResult').textContent='지지면 밖입니다. 추천 위치 또는 확인된 지지면으로 이동하세요.';$('#confirmAsset').disabled=true;}
  }
  this.visuals();
 }
 visuals(){
  if(this.p.v.hidePresentationOverlays)return;
  const item=this.draft||this.p.selected;
  if(!this.p.v.manifest?.digital_twin||!item?.object){if(this.helper)this.helper.visible=false;if(this.safety)this.safety.visible=false;return;}
  const b=new THREE.Box3().setFromObject(item.object),center=b.getCenter(new THREE.Vector3()),size=b.getSize(new THREE.Vector3());
  const result=this.check(item),color=result.state==='collision'?0xff5366:result.state==='clearance'?0xffb249:0x56e0b6;
  if(!this.helper){this.helper=new THREE.Box3Helper(b.clone(),color);this.helper.material.depthTest=false;this.helper.renderOrder=25;this.p.objects.add(this.helper);}
  this.helper.visible=true;this.helper.box.copy(b);this.helper.material.color.setHex(color);
  if(!this.safety){this.safety=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.13,depthWrite:false,side:THREE.DoubleSide}));this.safety.rotation.x=-Math.PI/2;this.p.objects.add(this.safety);}
  this.safety.visible=true;this.safety.material.color.setHex(color);this.safety.position.copy(item.supportPoint).addScaledVector(this.p.up,.004);this.safety.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),this.p.up);this.safety.scale.set(size.x+2*this.clearance,size.z+2*this.clearance,1);
  if(item.shadow)this.p.updateShadow(item);
 }
 findSafe(){
  const item=this.draft;if(!item)return;
  const previous=item.object.position.clone(),spots=this.p.spots||[];
  for(const spot of spots){
   item.object.position.fromArray(spot.position);item.supportTarget=spot.support;item.supportPoint.fromArray(spot.position);this.p.ground(item);
   if(this.check(item).state==='clear'){item.spotId=spot.id;item.lastPosition.copy(item.object.position);this.inspect();this.p.status('추천 지지면의 안전한 위치로 이동했습니다.');return;}
  }
  // Search real visible horizontal depth surfaces in the vicinity. No guessed
  // off-screen floor or silent reduction of the user's clearance threshold.
  const candidates=[];for(let z=-18;z<=18;z++)for(let x=-18;x<=18;x++)candidates.push([x*.06,z*.06]);candidates.sort((a,b)=>Math.hypot(...a)-Math.hypot(...b));
  for(const spot of spots)for(const [dx,dz]of candidates){
   const point=new THREE.Vector3(...spot.position).add(this.p.floorOffset(dx,dz));
   const hit=this.p.supportHit(this.p.supportRay(point));
   if(!hit)continue;
   const support=this.p.baseNodes.find(n=>n.id===spot.support),c=this.p.baseGraph.camera,rect=support?.bbox2d;
   const u=c.fx*hit.point.x/-hit.point.z+c.cx,v=c.cy-c.fy*hit.point.y/-hit.point.z;
   if(rect&&(u<rect[0]||u>rect[2]||v<rect[1]||v>rect[3]))continue;
   const projected=hit.point.clone().project(this.p.v.camera);if(Math.abs(projected.x)>.83||Math.abs(projected.y)>.83)continue;
   item.object.position.copy(hit.point);item.supportTarget=spot.support;
   this.p.ground(item,hit.point);
   if(this.check(item).state!=='clear')continue;
   item.supportPoint.copy(hit.point);item.normal.copy(hit.normal);item.lastPosition.copy(hit.point);item.spotId=spot.id;this.p.measureSupport(item,hit);this.inspect();this.p.status('가까운 빈 지지면에서 이격 기준을 충족하는 위치를 찾았습니다.');return;
  }
  item.object.position.copy(previous);this.inspect();this.p.status('추천 위치에서 기준을 충족하지 못했습니다. 이동 기즈모로 위치를 조정하거나 검토 기준을 변경하세요.');
 }
 confirm(){
  if(!this.draft)return false;this.inspect();if(this.result.state!=='clear')return false;
  const item=this.draft;this.history.push({event:'asset-confirmed',name:item.name,result:this.result});this.draft=null;this.p.items.push(item);
  item.landing={start:performance.now(),from:item.object.position.clone().addScaledVector(this.p.up,.08),to:item.object.position.clone()};this.p.update();this.p.status('신규 자산 반입 확정 · 자산 대장과 관계 그래프를 갱신했습니다.');return true;
 }
 cancel(){
  this.result=null;this.lastState=null;
  if(this.draft){this.p.controls.detach();this.p.objects.remove(this.draft.object,this.draft.shadow);this.p.selected=null;this.draft=null;}
  if(this.helper)this.helper.visible=false;if(this.safety)this.safety.visible=false;
  if($('#confirmAsset'))$('#confirmAsset').disabled=true;
 }
}
