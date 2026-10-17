const NS='http://www.w3.org/2000/svg';
const el=(t,a={})=>{const n=document.createElementNS(NS,t);for(const[k,v]of Object.entries(a))n.setAttribute(k,v);return n;};
const icons={'설비':'▣','적재물':'▤','공구':'⚒','구조물':'▥','기타':'◇'};
export function drawTwinGraph(root,graph,selected,onSelect,{base,onHover}={}){
 const previous=root._twinIds||new Set();root._twinIds=new Set(graph.nodes.map(n=>n.id));root.replaceChildren();
 const heading=document.createElement('h2');heading.textContent='자산 연결도';root.append(heading);
 const caption=document.createElement('p');caption.className='graph-meta';caption.textContent=`${graph.nodes.filter(n=>n.asset_id).length} ASSETS / ${graph.edges.length} LINKS · 이격 거리 추정`;root.append(caption);
 const svg=el('svg',{viewBox:'0 0 390 500',class:'twin-graph','aria-label':'구역별 자산 관계 그래프'}),points=new Map();let y=0;
 const ids=[...new Set(graph.nodes.map(n=>n.zone||'미지정'))];
 for(const zone of ids){
  const nodes=graph.nodes.filter(n=>(n.zone||'미지정')===zone);
  const rank=(n,seen=[])=>{if(seen.includes(n.id))return 0;const edge=graph.edges.find(e=>e.source===n.id&&e.relation==='on'),target=graph.nodes.find(n=>n.id===edge?.target);return target?1+rank(target,[...seen,n.id]):0;};
  nodes.sort((a,b)=>rank(b)-rank(a));const rows=Math.ceil(nodes.length/3),height=rows*95+43,color=graph.zones?.find(z=>z.id===zone)?.color||'#6ac9c9';
  svg.append(el('rect',{x:4,y:y+4,width:382,height,rx:14,fill:color+'0c',stroke:color+'66',class:'zone-group'}));
  const label=el('text',{x:18,y:y+25,fill:color,'font-size':12});label.textContent=zone+' · '+(graph.zones?.find(z=>z.id===zone)?.name||'자산');svg.append(label);
  nodes.forEach((n,i)=>points.set(n.id,[68+(i%3)*127,y+76+Math.floor(i/3)*95]));y+=height+17;
 }
 svg.setAttribute('viewBox',`0 0 390 ${y}`);
 for(const e of graph.edges){const a=points.get(e.source),b=points.get(e.target);if(!a||!b)continue;
  const support=e.relation==='on',chosen=selected===e.source||selected===e.target;
  const line=el('path',{d:`M${a[0]},${a[1]} Q${(a[0]+b[0])/2+20},${(a[1]+b[1])/2-40} ${b[0]},${b[1]}`,class:'twin-edge'+(chosen?' selected':'')+(!previous.has(e.source)&&previous.size?' arriving':'')});svg.append(line);
  const label=el('text',{x:(a[0]+b[0])/2+4,y:(a[1]+b[1])/2-18,class:'twin-edge-label'+(chosen?' selected':'')});label.textContent=(e.operational_label||e.relation)+(e.distance_m!=null?` ${e.distance_m.toFixed(2)}m`:'');
  if(chosen||support||e.distance_m!=null)svg.append(label);
 }
 for(const n of graph.nodes){const [x,y]=points.get(n.id),g=el('g',{transform:`translate(${x} ${y})`,role:'button',tabindex:0,'aria-label':n.label||n.name,class:'twin-node'+(selected===n.id?' selected':'')+(!previous.has(n.id)&&previous.size?' arriving':'')});
  g.append(el('rect',{x:-54,y:-33,width:108,height:70,rx:9,class:'twin-card'}));
  const icon=el('text',{x:-44,y:-11,fill:'#62cbd8','font-size':17});icon.textContent=icons[n.classification]||'◇';g.append(icon);
  const id=el('text',{x:-20,y:-13,fill:'#89a9ba','font-size':10});id.textContent=n.asset_id||'지지면';g.append(id);
  const name=el('text',{x:0,y:9,'text-anchor':'middle',fill:'#e4edf2','font-size':10});name.textContent=n.asset_name||n.label||n.name;g.append(name);
  const status=el('text',{x:0,y:26,'text-anchor':'middle',fill:'#77c6b1','font-size':8});status.textContent=n.registration_source||'';g.append(status);
  g.onclick=()=>onSelect(n.id);g.onmouseenter=()=>onHover?.(n.id);g.onmouseleave=()=>onHover?.(null);g.onkeydown=e=>{if(e.key==='Enter')onSelect(n.id);};svg.append(g);
 }
 root.append(svg);const summary=document.createElement('p');summary.className='graph-summary';summary.textContent=graph.summary;root.append(summary);
}
