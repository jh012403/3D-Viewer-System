import './style.css';
import {SceneViewer} from './viewer.js';
const $=(s)=>document.querySelector(s);
const viewer=new SceneViewer($('#viewport'));window.sceneWorkspace=viewer;
function status(text,error=false){$('#status').textContent=text;$('#status').classList.toggle('error',error);}
async function load(url){
  status('공간을 불러오는 중…');
  try{
    const m=await viewer.load(url);
    $('#sceneTitle').textContent=m.title;
    $('#source').src=new URL(m.source,viewer.base);$('#comparison').src=$('#source').src;
    $('.source-card').hidden=false;$('#comparison').hidden=true;
    $('#details').replaceChildren();
    for(const [name,value] of [['크기',m.camera.width+' × '+m.camera.height],['뷰 범위','±'+m.orbit_degrees+'°'],['단위','m (추정)'],['스케일 정렬',m.alignment.scale.toFixed(3)],['깊이 잔차',(m.alignment.median_relative_residual*100).toFixed(1)+'%']]){
      const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=value;$('#details').append(dt,dd);
    }
    status('캐시 로드 완료 · 드래그하여 둘러보세요');
    window.dispatchEvent(new CustomEvent('scene-loaded',{detail:m}));
  }catch(e){status(e.message,true);}
}
async function refresh(){
  const res=await fetch('/scene-api/scenes');if(!res.ok)throw new Error('씬 서버에 연결할 수 없습니다.');
  const scenes=await res.json();$('#scenes').replaceChildren();
  scenes.forEach(m=>{const b=document.createElement('button');b.className='scene-card';b.textContent=m.title;b.onclick=()=>load(m.url);$('#scenes').append(b);});
  return scenes;
}
$('#reset').onclick=()=>viewer.reset();
$('#compare').onclick=()=>{$('#comparison').hidden=!$('#comparison').hidden;if(!$('#comparison').hidden)viewer.reset();};
$('#surface').onclick=()=>{if(viewer.surface)viewer.surface.visible=!viewer.surface.visible;};
$('#photo').onchange=async(e)=>{
  const file=e.target.files[0];if(!file)return;
  if($('#cacheOnly').checked){status('새 배경을 생성하려면 시연 모드를 꺼주세요.');e.target.value='';return;}
  $('#photo').disabled=true;
  try{
    const data=new FormData();data.append('file',file);
    const res=await fetch('/scene-api/build',{method:'POST',body:data});
    if(!res.ok)throw new Error(await res.text());
    const {id}=await res.json();
    for(;;){
      await new Promise(r=>setTimeout(r,1500));
      const result=await fetch('/scene-api/jobs/'+id);if(!result.ok)throw new Error('작업 상태 조회 실패');
      const job=await result.json();status(job.message);
      if(job.status==='failed')throw new Error(job.message);
      if(job.status==='ready'){await refresh();await load(job.url);break;}
    }
  }catch(e){status(e.message,true);}finally{$('#photo').disabled=false;}
};
refresh().then(s=>{status(s.length?'저장된 공간을 선택하세요':'배경 사진을 추가하여 첫 공간을 만드세요');const id=new URLSearchParams(location.search).get('scene');if(id){const item=s.find(x=>x.id===id);if(item)load(item.url);}}).catch(e=>status(e.message,true));
export {viewer,status,load};
