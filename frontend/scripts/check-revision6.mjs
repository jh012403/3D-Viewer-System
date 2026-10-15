import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto('http://127.0.0.1:5173/scene.html?scene=sunroom');
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy,{},{timeout:120000});
 await page.evaluate(()=>window.sceneWorkspace.reset());
 await page.setInputFiles('#glb','../storage/scene_assets/validation-chair.glb');
 await page.waitForFunction(()=>window.sceneWorkspace.placement.pending,{},{timeout:60000});
 const placement=await page.evaluate(async()=>{
   const THREE=await import('/node_modules/three/build/three.module.js'),v=window.sceneWorkspace,p=v.placement;
   const defaultHeight=new THREE.Box3().setFromObject(p.pending.object).getSize(new THREE.Vector3()).y;
   // This sample is a low lounge chair (native height 0.686 m), not a dining chair.
   // Exercise user scale adjustment while retaining the existing 1 m default.
   p.pending.object.scale.setScalar(.7);
   for(let y=.98;y>.82;y-=.02)for(let x=.88;x<.98;x+=.02){
     const r=new THREE.Raycaster();r.setFromCamera(new THREE.Vector2(x*2-1,1-y*2),v.camera);
     const h=p.supportHit(r);if(!h||h.point.y>-.8||h.normal.y<.8)continue;
     if(p.placeFromRay(r)){
       const i=p.items[0];p.controls.detach();
       return {defaultHeight,demonstrationScale:.7,height:i.box.max[1]-i.box.min[1],position:i.object.position.toArray(),overlap:p.overlaps(i),resolution:i.collisionResolution,occlusion:p.occlusionAudit,shadow:i.shadow.visible};
     }
   }throw Error('No collision-free floor placement');
 });
 assert(!placement.overlap);assert(placement.position[1]<-.8);assert(Math.abs(placement.defaultHeight-1)<.02);assert(Math.abs(placement.height-.7)<.02);assert(placement.shadow);
 await page.waitForTimeout(1200);await page.screenshot({path:'../docs/screenshots/revision6-chair-original.png'});
 for(const degree of [-5,5]){
   await page.evaluate(degree=>{
     const v=window.sceneWorkspace;v.reset(false);const r=v.camera.position.distanceTo(v.controls.target),a=degree*Math.PI/180;
     v.camera.position.set(v.controls.target.x+r*Math.sin(a),0,v.controls.target.z+r*Math.cos(a));v.controls.update();
   },degree);
   await page.waitForTimeout(1200);await page.screenshot({path:`../docs/screenshots/revision6-chair-${degree}.png`});
 }
 await page.locator('#tabGraph').click();await page.screenshot({path:'../docs/screenshots/revision6-graph.png'});
 assert.deepEqual(errors,[]);await writeFile('../docs/scene-revision6-placement.json',JSON.stringify({placement,errors},null,2));console.log(JSON.stringify({placement,errors}));
}finally{await browser.close();}
