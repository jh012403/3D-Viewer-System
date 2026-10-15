const GENERATING=['깊이 추정','3D 공간 복원','물체 인식','관계 분석'];
const CACHED=['배경 불러오기','3D 공간 준비','물체 불러오기','관계 연결'];
let panel,finishTimer;
export function showProgress(stage,{cached=false,error=null}={}){
 clearTimeout(finishTimer);
 if(!panel){panel=document.createElement('div');panel.className='scene-progress';panel.setAttribute('role','status');document.querySelector('#viewport').append(panel);}
 panel.hidden=false;panel.classList.remove('complete');panel.classList.toggle('failed',!!error);
 panel.replaceChildren();
 const mark=document.createElement('div');mark.className='progress-orbit';mark.innerHTML='<i></i><i></i><i></i>';panel.append(mark);
 const badge=document.createElement('span');badge.className='progress-badge';badge.textContent=cached?'저장된 시연 장면':'사진에서 공간으로';panel.append(badge);
 const title=document.createElement('h2');title.textContent=error?'잠시 확인해 주세요':cached?'공간을 펼치고 있습니다':'사진 속 공간을 만들고 있습니다';panel.append(title);
 const steps=document.createElement('ol');for(const [i,label]of (cached?CACHED:GENERATING).entries()){
  const li=document.createElement('li');li.className=i<stage?'done':i===stage?'current':'';const number=document.createElement('span');number.textContent=i<stage?'✓':String(i+1).padStart(2,'0');li.append(number,document.createTextNode(label));steps.append(li);
 }panel.append(steps);
 const caption=document.createElement('p');caption.textContent=error||'잠시 후 이 공간에 물체를 놓을 수 있습니다.';panel.append(caption);
}
export function finishProgress(){if(panel){panel.classList.add('complete');finishTimer=setTimeout(()=>{panel.hidden=true;panel.classList.remove('complete');},350);}}
