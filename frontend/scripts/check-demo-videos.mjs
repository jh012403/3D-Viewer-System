import {chromium} from '@playwright/test';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),external=[],rows=[];
 page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
 await page.goto(pathToFileURL(resolve('../docs/demo-videos/index.html')).href);
 for(let i=0;i<4;i++){
  await page.locator('.scenes button').nth(i).click();
  await page.waitForFunction(()=>{const v=document.querySelector('video');return v.readyState>=3&&!v.paused&&v.currentTime>.3;});
  const state=await page.evaluate(()=>{const v=document.querySelector('video');return {src:v.getAttribute('src'),width:v.videoWidth,height:v.videoHeight,duration:v.duration,playing:!v.paused};});
  assert.equal(state.width,1600);assert.equal(state.height,1000);assert(state.duration>20);rows.push(state);
 }
 assert.deepEqual(external,[]);await page.screenshot({path:'../docs/screenshots/demo-stage6-offline-player.png'});
 await writeFile('../docs/demo-videos/playback-check.json',JSON.stringify({rows,external},null,2));console.log(JSON.stringify({rows,external}));
}finally{await browser.close();}
