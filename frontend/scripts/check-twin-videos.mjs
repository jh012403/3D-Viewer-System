import {chromium} from '@playwright/test';import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';import {writeFile} from 'node:fs/promises';import assert from 'node:assert/strict';
const b=await chromium.launch({headless:true}),p=await b.newPage({viewport:{width:1500,height:1000}}),external=[],errors=[];
p.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});p.on('pageerror',e=>errors.push(e.message));
try{
 await p.goto(pathToFileURL(resolve('../docs/twin-videos/index.html')).href);
 const rows=[];for(let i=0;i<4;i++){const video=p.locator('video').nth(i);await video.scrollIntoViewIfNeeded();await video.evaluate(async v=>{await v.play();});await p.waitForTimeout(1500);rows.push(await video.evaluate(v=>({src:v.getAttribute('src'),duration:v.duration,time:v.currentTime,width:v.videoWidth,height:v.videoHeight,error:v.error?.message})));await video.evaluate(v=>v.pause());}
 for(const r of rows){assert(r.time>0);assert(r.duration>30);assert.equal(r.width,1800);assert(!r.error);}assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 await p.evaluate(()=>window.scrollTo(0,0));await p.screenshot({path:'../docs/screenshots/twin-stage7-offline-gallery.png'});await writeFile('../docs/twin-videos/playback-check.json',JSON.stringify({rows,errors,external},null,2));console.log(JSON.stringify(rows));
}finally{await b.close();}
