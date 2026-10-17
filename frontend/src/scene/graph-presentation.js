const RELATIONS={on:'위에', 'attached to':'부착','next to':'옆에','left of':'왼쪽','right of':'오른쪽','in front of':'앞에',behind:'뒤에'};
const NS='http://www.w3.org/2000/svg';
function svgElement(tag,attributes={}){const node=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attributes))node.setAttribute(k,v);return node;}

export function drawGraph(root,graph,selected,onSelect,{base,onHover}={}){
 const oldIds=root._nodeIds||new Set(),newIds=new Set(graph.nodes.map(n=>n.id));root._nodeIds=newIds;root.replaceChildren();
 const title=document.createElement('h2');title.textContent='공간의 이야기';root.append(title);
 const meta=document.createElement('p');meta.className='graph-meta';meta.textContent=`${graph.nodes.length}개의 물체가 ${graph.edges.length}개의 관계로 이어져 있습니다`;root.append(meta);
 if(!graph.nodes.length)return;
 const byId=new Map(graph.nodes.map(n=>[n.id,n]));
 const rank=(id,seen=new Set())=>{if(seen.has(id))return 0;seen=new Set([...seen,id]);const supports=graph.edges.filter(e=>e.source===id&&e.relation==='on');return supports.length?1+Math.max(...supports.map(e=>rank(e.target,seen))):0;};
 const levels=new Map(graph.nodes.map(n=>[n.id,rank(n.id)]));
 const supportIds=new Set(graph.edges.filter(e=>e.relation==='on').map(e=>e.target));
 for(const n of graph.nodes){if(!supportIds.has(n.id)&&levels.get(n.id)===0)levels.set(n.id,1);if(n.name==='ceiling')levels.set(n.id,3);}
 const points=new Map();let row=0;
 for(const level of [...new Set(levels.values())].sort((a,b)=>b-a)){
  const group=graph.nodes.filter(n=>levels.get(n.id)===level);
  for(let i=0;i<group.length;i+=3){const chunk=group.slice(i,i+3);chunk.forEach((n,j)=>points.set(n.id,[chunk.length===3?60+j*120:chunk.length===2?90+j*180:180,58+row*112]));row++;}
 }
 const svg=svgElement('svg',{viewBox:`0 0 360 ${row*112+20}`,'aria-label':'물체 썸네일과 공간 관계 그래프',class:'graph-story'});
 const defs=svgElement('defs');svg.append(defs);
 for(const [i,e]of graph.edges.entries()){
  const relationLabel=graph.digital_twin?(e.operational_label||RELATIONS[e.relation]||e.relation)+(e.distance_m!=null?` · ${e.distance_m.toFixed(2)}m`:''):(RELATIONS[e.relation]||e.relation);
  if(!points.has(e.source)||!points.has(e.target))continue;
  const [ax,ay]=points.get(e.source),[bx,by]=points.get(e.target),support=e.relation==='on'||e.relation==='attached to';
  const y1=ay+(by>=ay?39:-39),y2=by+(by>=ay?-39:39),bend=(y1+y2)/2;
  const path=svgElement('path',{d:support?`M${ax},${y1} C${ax},${bend} ${bx},${bend} ${bx},${y2}`:`M${ax},${ay} Q${(ax+bx)/2},${Math.min(ay,by)-66} ${bx},${by}`,class:'story-edge'+(e.source===selected||e.target===selected?' selected':'')+(!oldIds.has(e.source)&&oldIds.size?' arriving':''),'data-source':e.source,'data-target':e.target});
  const tip=svgElement('title');tip.textContent=`${byId.get(e.source)?.label||byId.get(e.source)?.name} · ${RELATIONS[e.relation]||e.relation} · ${byId.get(e.target)?.label||byId.get(e.target)?.name}`;path.append(tip);svg.append(path);
  if(support||e.source===selected||e.target===selected||graph.digital_twin){const label=svgElement('text',{x:(ax+bx)/2+5,y:support?bend:Math.min(ay,by)-34,class:'story-relation'});label.textContent=relationLabel;svg.append(label);}
 }
 for(const [i,n]of graph.nodes.entries()){
  const [x,y]=points.get(n.id),g=svgElement('g',{transform:`translate(${x} ${y})`,role:'button',tabindex:0,'aria-label':n.label||n.name,class:'story-node'+(n.id===selected?' selected':'')+(!oldIds.has(n.id)&&oldIds.size?' arriving':'')});
  const clip=svgElement('clipPath',{id:`thumb-${i}`});clip.append(svgElement('rect',{x:-43,y:-35,width:86,height:49,rx:7}));defs.append(clip);
  g.append(svgElement('rect',{x:-47,y:-40,width:94,height:81,rx:10,class:'story-card'}));
  if(n.thumbnail){const href=/^(data:|https?:|\/)/.test(n.thumbnail)?n.thumbnail:new URL(n.thumbnail,base).href;g.append(svgElement('image',{href,x:-43,y:-35,width:86,height:49,preserveAspectRatio:'xMidYMid slice','clip-path':`url(#thumb-${i})`}));}
  else {const icon=svgElement('text',{x:0,y:0,'text-anchor':'middle',fill:'#c4e5b9','font-size':25});icon.textContent='＋';g.append(icon);}
  const name=svgElement('text',{x:0,y:31,'text-anchor':'middle',class:'story-name'});name.textContent=n.label||n.name;g.append(name);
  g.onclick=()=>onSelect(n.id);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' ')onSelect(n.id);};g.onmouseenter=()=>onHover?.(n.id);g.onmouseleave=()=>onHover?.(null);g.onfocus=()=>onHover?.(n.id);g.onblur=()=>onHover?.(null);svg.append(g);
 }
 root.append(svg);const summary=document.createElement('p');summary.className='graph-summary';summary.textContent=graph.summary||'물체를 선택하면 사진 속 위치와 주변 관계를 함께 살펴볼 수 있습니다.';root.append(summary);
}
