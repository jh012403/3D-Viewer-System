import './style.css';
import './twin.css';
import './dashboard.css';
import {SceneViewer} from './viewer.js';
import {showProgress,finishProgress} from './progress.js';
const $=(s)=>document.querySelector(s);
const viewer=new SceneViewer($('#viewport'));window.sceneWorkspace=viewer;
function status(text,error=false){$('#status').textContent=text;$('#status').classList.toggle('error',error);}
async function load(url){
  if(viewer.loading)return;viewer.loading=true;
  status('공간을 불러오는 중…');
  showProgress(0,{cached:true});viewer.onLoadProgress=stage=>showProgress(stage,{cached:true});
  try{
    const m=await viewer.load(url);
    $('#sceneTitle').textContent=m.title;
    $('#viewHint').textContent='ORBIT ±'+viewer.maxOrbitDegrees+'°';
    $('#source').src=new URL(m.source,viewer.base);$('#comparison').src=$('#source').src;
    $('.source-card').hidden=false;$('#comparison').hidden=true;
    $('#details').replaceChildren();
    for(const [name,value] of [['둘러보기','좌우로 드래그'],['물체 놓기','추천 위치 클릭'],['결과 저장','이미지 + 그래프']]){
      const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=value;$('#details').append(dt,dd);
    }
    showProgress(2,{cached:true});
    await new Promise((resolve,reject)=>window.dispatchEvent(new CustomEvent('scene-loaded',{detail:{...m,resolve,reject}})));
    showProgress(3,{cached:true});finishProgress();status('드래그하여 둘러보거나 추천 위치에 물체를 놓아보세요');
    document.querySelectorAll('.scene-card').forEach(b=>b.classList.toggle('active',b.dataset.scene===m.id));
  }catch(e){status(e.message,true);showProgress(0,{cached:true,error:e.message});setTimeout(finishProgress,2500);}finally{viewer.loading=false;}
}
async function refresh(){
  const res=await fetch('/scene-api/scenes');if(!res.ok)throw new Error('씬 서버에 연결할 수 없습니다.');
  const scenes=(await res.json()).sort((a,b)=>(a.sort_order??100)-(b.sort_order??100));$('#scenes').replaceChildren();
  scenes.forEach(m=>{const b=document.createElement('button');b.className='scene-card';b.dataset.scene=m.id;b.textContent=m.title;b.onclick=()=>load(m.url);$('#scenes').append(b);});
  return scenes;
}
$('#reset').onclick=()=>viewer.reset();
$('#compare').onclick=()=>{$('#comparison').hidden=!$('#comparison').hidden;if(!$('#comparison').hidden)viewer.reset();};
$('#surface').onclick=()=>{if(viewer.surface)viewer.surface.visible=!viewer.surface.visible;};
$('#photo').onchange=async(e)=>{
  const file=e.target.files[0];if(!file)return;
  if($('#cacheOnly').checked){status('새 배경을 생성하려면 시연 모드를 꺼주세요.');e.target.value='';return;}
  $('#photo').disabled=true;
  showProgress(0);
  try{
    const data=new FormData();data.append('file',file);
    const res=await fetch('/scene-api/build',{method:'POST',body:data});
    if(!res.ok)throw new Error(await res.text());
    const {id}=await res.json();
    for(;;){
      await new Promise(r=>setTimeout(r,1500));
      const result=await fetch('/scene-api/jobs/'+id);if(!result.ok)throw new Error('작업 상태 조회 실패');
      const job=await result.json();status(job.message);
      showProgress(job.stage??0);
      if(job.status==='failed')throw new Error(job.message);
      if(job.status==='ready'){await refresh();await load(job.url);break;}
    }
  }catch(e){status(e.message,true);showProgress(0,{error:e.message});setTimeout(finishProgress,2500);}finally{$('#photo').disabled=false;}
};
refresh().then(s=>{status(s.length?'저장된 공간을 선택하세요':'배경 사진을 추가하여 첫 공간을 만드세요');const id=new URLSearchParams(location.search).get('scene');if(id){const item=s.find(x=>x.id===id);if(item)load(item.url);}}).catch(e=>status(e.message,true));
export {viewer,status,load};

import {Placement} from './placement.js';
viewer.placement=new Placement(viewer,status);
import {PlacementSimulation} from './simulation.js';
viewer.simulation=new PlacementSimulation(viewer.placement);

const tabs=document.createElement('div');tabs.className='inspector-tabs';
tabs.innerHTML='<button id="tabEdit" class="active">배치</button><button id="tabGraph">그래프</button>';
document.querySelector('.inspector').prepend(tabs);
$('#tabEdit').onclick=()=>{document.querySelector('.inspector').classList.remove('graph-mode');$('#tabEdit').classList.add('active');$('#tabGraph').classList.remove('active');};
$('#tabGraph').onclick=()=>{document.querySelector('.inspector').classList.add('graph-mode');$('#tabGraph').classList.add('active');$('#tabEdit').classList.remove('active');};
const analyze=document.createElement('button');analyze.id='analyze';analyze.textContent='배경 그래프 생성';$('#placement').prepend(analyze);
const updateMode=()=>{document.body.classList.toggle('demo-mode',$('#cacheOnly').checked);$('#category').parentElement.hidden=$('#cacheOnly').checked;};$('#cacheOnly').addEventListener('change',updateMode);updateMode();
analyze.onclick=async()=>{
 if(!viewer.manifest)return;
 if($('#cacheOnly').checked){status('그래프를 새로 생성하려면 시연 모드를 꺼주세요.');return;}
 analyze.disabled=true;
 try{
  const response=await fetch('/scene-api/graphs/'+encodeURIComponent(viewer.manifest.id),{method:'POST'});
  if(!response.ok)throw Error(await response.text());
  const {id}=await response.json();
  for(;;){await new Promise(r=>setTimeout(r,1500));const r=await fetch('/scene-api/jobs/'+id);if(!r.ok)throw Error('작업 조회 실패');const job=await r.json();status(job.message);if(job.status==='failed')throw Error(job.message);if(job.status==='ready'){await viewer.placement.loadGraph(true);status('배경 그래프 생성 완료');break;}}
 }catch(e){status(e.message,true);}finally{analyze.disabled=false;}
};
import {TwinDashboard} from './dashboard.js';
viewer.dashboard=new TwinDashboard(viewer);
import {TwinExports} from './twin-export.js';
viewer.exports=new TwinExports(viewer);
import {AMRAreas} from './amr-areas.js';
viewer.amr=new AMRAreas(viewer);
