import {chromium} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const root='../docs/placement-correction',browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1920,height:1080}});
const views=[['original','원본 시점'],['minus5','−5° 시점'],['plus5','+5° 시점']];
try{
 for(const [key,title]of views){
  const images=await Promise.all(['before','after'].map(async phase=>'data:image/png;base64,'+(await readFile(`${root}/${phase}-${key}-view.png`)).toString('base64')));
  await page.setContent(`<meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;background:#101c26;color:#eaf3f7;font-family:"Malgun Gothic",sans-serif}main{padding:60px;width:1920px;height:1080px}h1{font-size:36px;margin:12px 0 36px}small{color:#82cbd3;font-size:18px}section{display:flex;gap:28px}article{width:886px;background:#182b37;border:1px solid #36505f;border-radius:14px;overflow:hidden}img{display:block;width:100%;height:710px;object-fit:contain}h2{margin:0;padding:25px;font-size:25px;text-align:center}p{color:#b4c9d4;font-size:19px;margin-top:28px}</style><main><small>PRISM / 물류 창고 · EQ-0008</small><h1>바닥에 바로 선 반입 상자 — ${title}</h1><section><article><img src="${images[0]}"><h2>수정 전 · 기존 메시와 화면 Y축</h2></article><article><img src="${images[1]}"><h2>수정 후 · 바닥 법선과 새 닫힌 상자</h2></article></section><p>동일한 현장·카메라 시점·높이 0.35m · 바닥 법선 정렬 / 1.5cm 접지 / 하단 캡 / 윤곽 그림자 / 톤 보정</p></main>`);
  await page.locator('img').evaluateAll(imgs=>Promise.all(imgs.map(i=>i.decode())));
  await page.screenshot({path:`${root}/comparison-${key}.png`});
 }
 await writeFile(root+'/index.html',`<!doctype html><meta charset="utf-8"><title>반입 상자 수정 전후</title><style>body{background:#101c26;color:#eaf3f7;font:18px "Malgun Gothic",sans-serif;margin:32px}img{width:100%;max-width:1500px;display:block;margin:20px 0}a{color:#82cbd3}</style><h1>반입 상자 EQ-0008 수정 전후</h1><p>동일 장면, 원본·좌우 5° 비교. <a href="README.md">측정값·출처·검증 기록</a></p>${views.map(([key,title])=>`<h2>${title}</h2><a href="comparison-${key}.png"><img src="comparison-${key}.png"></a><p><a href="before-${key}.png">수정 전 전체 화면</a> · <a href="after-${key}.png">수정 후 전체 화면</a></p>`).join('')}<p>새 메시: HireAHelper의 CC BY 2.0 사진을 SAM3와 TRELLIS.2로 처리. 기존 캐시와 생성 원본 보존.</p>`);
}finally{await browser.close();}
