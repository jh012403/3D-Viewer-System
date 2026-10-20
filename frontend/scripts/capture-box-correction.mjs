import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
const phase=process.argv[2]||'before',job=process.argv[3]||'job_000002';
const out='../docs/placement-correction';await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1920,height:1080}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>console.log(m.text()));
try{
 await page.goto('http://127.0.0.1:5173/scene.html?scene=twin-logistics');
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy&&!window.sceneWorkspace.loading,null,{timeout:120000});
 await page.evaluate(async job=>{const v=window.sceneWorkspace;await v.placement.importGenerated(job);v.placement.pending.name='반입 상자';v.placement.placeAtSpot(v.placement.spots[0]);const input=document.querySelector('#assetHeight');input.value='.35';input.dispatchEvent(new Event('change'));console.log('FIT',JSON.stringify({fit:v.placement.gravity?.audit,result:v.simulation.result}));if(!v.simulation.confirm())console.log('NOT_CLEAR',JSON.stringify({fit:v.placement.gravity?.audit,result:v.simulation.result,position:v.simulation.draft?.object.position.toArray()}));},job);
 await page.waitForTimeout(1000);
 await page.addStyleTag({content:'.statusbar,.local,.placement-spot,.ledger-note{display:none!important}.twin-node,.twin-edge{animation:none!important}'});
 await page.evaluate(()=>{const v=window.sceneWorkspace;v.placement.controls.detach();v.hidePresentationOverlays=true;if(v.simulation.helper)v.simulation.helper.visible=false;if(v.simulation.safety)v.simulation.safety.visible=false;});
 const result={phase,job,errors,views:{}};
 for(const degrees of [0,-5,5]){
  await page.evaluate(async degrees=>{const v=window.sceneWorkspace;v.reset(true);v.controls.enableDamping=false;const THREE=await import('/node_modules/three/build/three.module.js');const offset=v.camera.position.clone().sub(v.controls.target);offset.applyAxisAngle(new THREE.Vector3(0,1,0),degrees*Math.PI/180);v.camera.position.copy(v.controls.target).add(offset);v.controls.update();},degrees);
  await page.waitForTimeout(800);
  const name=degrees===0?'original':degrees<0?'minus5':'plus5';
  await page.screenshot({path:`${out}/${phase}-${name}.png`});
  await page.locator('#viewport canvas').screenshot({path:`${out}/${phase}-${name}-view.png`});
  result.views[name]=await page.evaluate(()=>{const v=window.sceneWorkspace,p=v.placement,i=p.items[0]||v.simulation.draft;return {camera:v.camera.position.toArray(),projection:v.camera.projectionMatrix.toArray(),position:i.object.position.toArray(),quaternion:i.object.quaternion.toArray(),support:i.supportPoint.toArray(),gravity:p.gravity?.audit,ground:p.groundAudit?.(i),tone:i.toneAudit};});
 }
 await writeFile(`${out}/${phase}.json`,JSON.stringify(result,null,2));
 if(errors.length)throw Error(errors.join('\n'));
}finally{await browser.close();}

