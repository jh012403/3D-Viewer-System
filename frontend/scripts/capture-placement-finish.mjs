import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const phase=process.argv[2]||'before',job=process.argv[3]||'job_000003';
const out='../docs/placement-finish';await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1920,height:1080}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>console.log(m.text()));
try{
 await page.goto('http://127.0.0.1:5173/scene.html?scene=twin-logistics');
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,null,{timeout:120000});
 await page.evaluate(async job=>{const v=window.sceneWorkspace;await v.placement.importGenerated(job);v.placement.pending.name='반입 상자';if(job==='job_000003')v.placement.pending.asset.placement_yaw_degrees=90;v.placement.placeAtSpot(v.placement.spots[0]);const input=document.querySelector('#assetHeight');input.value='.35';input.dispatchEvent(new Event('change'));console.log('FIT',JSON.stringify({fit:v.placement.gravity?.audit,result:v.simulation.result}));v.simulation.findSafe();if(!v.simulation.confirm())console.log('NOT_CLEAR',JSON.stringify({fit:v.placement.gravity?.audit,result:v.simulation.result,position:v.simulation.draft?.object.position.toArray()}));},job);
 await page.waitForTimeout(1000);
 await page.addStyleTag({content:'.statusbar,.local,.placement-spot,.ledger-note{display:none!important}.twin-node,.twin-edge{animation:none!important}'});
 await page.evaluate(()=>{const v=window.sceneWorkspace;v.placement.controls.detach();v.hidePresentationOverlays=true;if(v.simulation.helper)v.simulation.helper.visible=false;if(v.simulation.safety)v.simulation.safety.visible=false;});
 const result={phase,job,errors,views:{}};
 for(const degrees of [0,-3,3]){
  await page.evaluate(async degrees=>{const v=window.sceneWorkspace;v.reset(true);v.controls.enableDamping=false;const offset=v.camera.position.clone().sub(v.controls.target);offset.applyAxisAngle(v.camera.position.clone().set(0,1,0),degrees*Math.PI/180);v.camera.position.copy(v.controls.target).add(offset);v.controls.update();},degrees);
  await page.waitForTimeout(800);
  const name=degrees===0?'original':degrees<0?'minus3':'plus3';
  await page.screenshot({path:`${out}/${phase}-${name}.png`});
  await page.locator('#viewport canvas').screenshot({path:`${out}/${phase}-${name}-view.png`});
  result.views[name]=await page.evaluate(()=>{const v=window.sceneWorkspace,p=v.placement,i=p.items[0]||v.simulation.draft;return {confirmed:p.items.length===1,asset_id:p.graph.nodes.find(n=>n.id===i.id)?.asset_id,review:i.review,camera:v.camera.position.toArray(),projection:v.camera.projectionMatrix.toArray(),intrinsics:v.manifest.camera,position:i.object.position.toArray(),quaternion:i.object.quaternion.toArray(),support:i.supportPoint.toArray(),gravity:p.gravity?.audit,ground:p.groundAudit?.(i),tone:i.toneAudit,shadow:i.shadowAudit,faces:i.faceAudit,maxOrbitDegrees:v.maxOrbitDegrees,azimuth:v.controls.getAzimuthalAngle(),structuralLabels:[...v.dashboard.labels.children].filter(b=>p.graph.nodes.find(n=>n.id===b.dataset.id)?.classification==='구조물').length};});
 }
 await writeFile(`${out}/${phase}.json`,JSON.stringify(result,null,2));
 if(phase==='after')for(const view of Object.values(result.views)){
  assert(view.confirmed);assert.equal(view.asset_id,'EQ-0008');assert.equal(view.review.state,'clear');
  assert.equal(view.structuralLabels,0);assert(Math.abs(view.ground.embedding_m-.015)<1e-6);
  assert(Math.abs(view.projection[0]-2*view.intrinsics.fx/view.intrinsics.width)<1e-10);
  assert(Math.abs(view.projection[5]-2*view.intrinsics.fy/view.intrinsics.height)<1e-10);
  assert(view.tone.materials.length);assert(view.shadow.bottom_vertices>10);assert.equal(view.maxOrbitDegrees,3);assert(view.shadow.rim_width_m>=.01);assert(view.faces.target_ratio>1);
 }
 if(errors.length)throw Error(errors.join('\n'));
}finally{await browser.close();}



