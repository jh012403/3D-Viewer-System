import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({headless:true,args:['--enable-gpu','--use-angle=d3d11']});
try {
 const page=await browser.newPage({viewport:{width:1600,height:1000}});const errors=[];
 page.on('pageerror',e=>{errors.push(e.stack);console.log(e.stack);});page.on('console',msg=>{if(msg.type()==='error')console.log(msg.text());});
 await page.goto('http://127.0.0.1:5173/scene.html?scene=sunroom');
 await page.waitForFunction(()=>window.sceneWorkspace?.placement?.proxy,{},{timeout:120000});
 await page.selectOption('#category','small_prop');
 await page.setInputFiles('#glb','../storage/scene_assets/validation-chair.glb');
 await page.waitForFunction(()=>window.sceneWorkspace.placement.pending,{},{timeout:60000}).catch(async e=>{console.log(await page.locator('#status').textContent());throw e;});
 const point=await page.evaluate(async()=>{
   const THREE=await import('/node_modules/three/build/three.module.js');
   const v=window.sceneWorkspace,p=v.placement;
   for(let y=.55;y<.9;y+=.03)for(let x=.25;x<.8;x+=.03){
     const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(x*2-1,1-y*2),v.camera);
     const hit=p.supportHit(ray);if(hit&&hit.normal.y>.85){return {x,y,point:hit.point.toArray()};}
   }
   throw Error('No support surface found');
 });
 const rect=await page.locator('canvas').boundingBox();
 await page.mouse.click(rect.x+rect.width*point.x,rect.y+rect.height*point.y);
 await page.waitForFunction(()=>window.sceneWorkspace.placement.items.length===1);
 await page.getByRole('button',{name:'이동',exact:true}).click();
 const initial=await page.evaluate(()=>window.sceneWorkspace.placement.selected.object.position.toArray());
 // Exercise actual gizmo pointer drag and check the transform changed.
 const origin=await page.evaluate(async()=>{
   const v=window.sceneWorkspace,p=v.placement;
   const n=p.selected.object.position.clone().project(v.camera);
   return [(n.x+1)/2,(1-n.y)/2];
 });
 await page.mouse.move(rect.x+rect.width*origin[0]+35,rect.y+rect.height*origin[1]);await page.mouse.down();
 await page.mouse.move(rect.x+rect.width*origin[0]+65,rect.y+rect.height*origin[1],{steps:10});await page.mouse.up();
 await page.waitForTimeout(1000);
 await page.evaluate(async()=>{
   const p=window.sceneWorkspace.placement,id=p.items[0].id;
   await p.loadGraph(true);
   if(p.items.length!==1||p.items[0].id!==id)throw Error('Graph refresh lost placed object');
 });
 const result=await page.evaluate(async()=>{
   const p=window.sceneWorkspace.placement;
   const out=await p.export();const bytes=Array.from(new Uint8Array(await out.image.arrayBuffer()));
   return {graph:out.graph,png:bytes,position:p.selected.object.position.toArray(),mode:p.controls.getMode(),scale:p.selected.object.scale.toArray()};
 });
 await writeFile('../docs/screenshots/stage3-export.png',Buffer.from(result.png));
 delete result.png;result.initial=initial;result.errors=errors;result.clicked=point;
 if(Math.abs(result.position[0]-initial[0])<.001)throw Error('Gizmo did not move object');
 await page.screenshot({path:'../docs/screenshots/stage3-placement.png',timeout:120000});
 await writeFile('../docs/scene-placement-check.json',JSON.stringify(result,null,2));
 if(errors.length||result.graph.nodes.filter(x=>x.source==='placed-glb').length!==1)throw Error(JSON.stringify(errors));
 console.log(JSON.stringify({errors,position:result.position,initial,nodes:result.graph.nodes.length}));
}finally{await browser.close();}
