import {fileURLToPath} from 'node:url';
import {writeFile} from 'node:fs/promises';
import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
const errors=[],results=[];
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 for(const scene of ['sunroom','ceramics','hall','d4f646fcc79650d6']){
  await page.goto('http://127.0.0.1:5173/scene.html?scene='+scene);
  await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy,{},{timeout:120000});
  await page.locator('#tabGraph').click();
  await page.waitForTimeout(1500);
  await page.screenshot({path:'../docs/screenshots/revision4-'+scene+'.png',timeout:120000});
  const box=await page.locator('canvas').boundingBox();
  for(const direction of [-1,1]){
   await page.evaluate(()=>window.sceneWorkspace.reset(false));
   await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
   await page.mouse.move(box.x+box.width/2+direction*350,box.y+box.height/2,{steps:20});await page.mouse.up();
   await page.waitForTimeout(1200);
   await page.screenshot({path:'../docs/screenshots/revision4-'+scene+'-orbit'+direction+'.png',timeout:120000});
  }
  results.push(await page.evaluate(()=>({scene:window.sceneWorkspace.manifest.id,title:window.sceneWorkspace.manifest.title,zoom:window.sceneWorkspace.camera.zoom,orbit:window.sceneWorkspace.controls.getAzimuthalAngle(),limit:window.sceneWorkspace.manifest.orbit_degrees})));
 }
 await page.goto('http://127.0.0.1:5173/scene.html?scene=sunroom');
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy,{},{timeout:120000});
 await page.setInputFiles('#glb','../storage/scene_assets/validation-chair.glb');
 await page.waitForFunction(()=>window.sceneWorkspace.placement.pending,{},{timeout:60000});
 const point=await page.evaluate(async()=>{
  const THREE=await import('/node_modules/three/build/three.module.js'),v=window.sceneWorkspace;
  for(let x=.88;x>.8;x-=.01)for(let y=.94;y>.85;y-=.01){
   const r=new THREE.Raycaster();r.setFromCamera(new THREE.Vector2(x*2-1,1-y*2),v.camera);
   const h=v.placement.supportHit(r);if(h&&h.normal.y>.8)return {x,y,point:h.point.toArray()};
  }throw Error('No floor next to right chair');
 });
 const rect=await page.locator('canvas').boundingBox();await page.mouse.click(rect.x+point.x*rect.width,rect.y+point.y*rect.height);
 await page.waitForFunction(()=>window.sceneWorkspace.placement.items.length===1);
 const placement=await page.evaluate(()=>{const p=window.sceneWorkspace.placement,i=p.items[0];return {category:i.asset.category,height:i.box.max[1]-i.box.min[1],position:i.object.position.toArray(),normal:i.normal.toArray()};});
 assert.equal(placement.category,'chair');assert.ok(Math.abs(placement.height-1)<.02);
 await page.evaluate(()=>{const p=window.sceneWorkspace.placement;p.controls.detach();});await page.waitForTimeout(1000);
 await page.screenshot({path:'../docs/screenshots/revision4-chair-scale.png',timeout:120000});
 for(const r of results)assert.ok(Math.abs(r.orbit)<=r.limit*Math.PI/180+.001);
 assert.deepEqual(errors,[]);
 await writeFile('../docs/scene-presentation-check.json',JSON.stringify({results,placement,point,errors},null,2));
 console.log(JSON.stringify({results,placement,errors}));
}finally{await browser.close();}
