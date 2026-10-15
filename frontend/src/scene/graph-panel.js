export function drawGraph(root,graph,selected,onSelect){
  root.replaceChildren();
  const title=document.createElement('h2');title.textContent='Scene graph';root.append(title);
  const meta=document.createElement('p');meta.className='muted';meta.textContent=graph.nodes.length+'개 물체 · '+graph.edges.length+'개 방향 관계';root.append(meta);
  const note=document.createElement('p');note.className='muted';note.textContent='사진 기반 추정 · 반사·가림·접촉 관계는 확인이 필요합니다.';root.append(note);
  if(!graph.nodes.length){meta.textContent='그래프를 생성하면 물체와 관계가 표시됩니다.';return;}
  const focus=graph.nodes.find(n=>n.id===selected)||graph.nodes[0];
  const names=Object.fromEntries(graph.nodes.map(n=>[n.id,n.name]));
  const edges=graph.edges.filter(e=>e.source===focus.id).sort((a,b)=>(['on','under','next to'].includes(b.relation)?1:0)-(['on','under','next to'].includes(a.relation)?1:0));
  const neighbors=[...new Set(edges.map(e=>e.target))].slice(0,6);
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 300 300');svg.setAttribute('aria-label','선택 물체의 관계 그래프');svg.classList.add('graph-svg');
  const points=new Map([[focus.id,[150,150]]]);
  neighbors.forEach((id,i)=>{const a=-Math.PI/2+i*2*Math.PI/neighbors.length;points.set(id,[150+110*Math.cos(a),150+110*Math.sin(a)]);});
  for(const id of neighbors){
    const [x,y]=points.get(id),edge=edges.find(e=>e.target===id);
    const line=document.createElementNS(ns,'line');for(const [k,v] of Object.entries({x1:150,y1:150,x2:x,y2:y,stroke:'#536d58'}))line.setAttribute(k,v);svg.append(line);
    const text=document.createElementNS(ns,'text');text.setAttribute('x',(150+x)/2);text.setAttribute('y',(150+y)/2-4);text.setAttribute('text-anchor','middle');text.setAttribute('fill','#a5bfaa');text.setAttribute('font-size','9');text.textContent=edge.relation;svg.append(text);
  }
  for(const [id,[x,y]]of points){
    const g=document.createElementNS(ns,'g');g.setAttribute('role','button');g.setAttribute('tabindex','0');g.style.cursor='pointer';g.setAttribute('aria-label',names[id]);
    const circle=document.createElementNS(ns,'circle');for(const [k,v]of Object.entries({cx:x,cy:y,r:id===focus.id?27:22,fill:id===focus.id?'#b8dfa4':'#253b2d',stroke:'#8eb182'}))circle.setAttribute(k,v);
    const text=document.createElementNS(ns,'text');text.setAttribute('x',x);text.setAttribute('y',y+4);text.setAttribute('text-anchor','middle');text.setAttribute('font-size','10');text.setAttribute('fill',id===focus.id?'#17221a':'#e0ece2');text.textContent=names[id].slice(0,13);
    g.append(circle,text);g.onclick=()=>onSelect(id);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' ')onSelect(id);};svg.append(g);
  }
  root.append(svg);
  const summary=document.createElement('p');summary.className='graph-summary';summary.textContent=edges.length?edges.slice(0,6).map(e=>names[e.source]+' '+e.relation+' '+names[e.target]).join(' · '):focus.name+'의 확인된 관계가 없습니다.';root.append(summary);
  const label=document.createElement('div');label.className='section-label';label.textContent='모든 물체 · 클릭하여 선택';root.append(label);
  const list=document.createElement('div');list.className='graph-nodes';
  for(const node of graph.nodes){const b=document.createElement('button');b.className='node'+(node.id===focus.id?' active':'');b.textContent=node.name+' · '+node.id.replace('obj-','#').slice(0,8);b.setAttribute('aria-pressed',node.id===focus.id);b.onclick=()=>onSelect(node.id);list.append(b);}
  root.append(list);
}
