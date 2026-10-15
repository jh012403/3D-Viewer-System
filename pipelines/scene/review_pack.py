"""Freeze five post-cleanup predictions for explicit human review."""
import csv,hashlib,json,shutil
from pathlib import Path
from .build import ROOT

SELECTED=['dav2-01','dav2-10','dav2-13','dav2-14','dav2-15']

def run():
    manifest=json.loads((ROOT/'docs/scene-evaluation-set.json').read_text(encoding='utf-8'))
    destination=ROOT/'docs/scene-review';destination.mkdir(exist_ok=True)
    photos=[]
    index=['# 5장 사용자 검수표','',
      '검수 보류 상태의 재생성 자료입니다. 노드 precision/recall 및 관계 정확도는 아직 계산하지 않습니다.',
      '','[이미지와 번호를 보며 검수하기](index.html)','',
      '범위: 독립된 물체와 주요 지지면. 반사상·물체의 부품·중복 검출은 별도 정답 물체로 세지 않습니다. 라벨은 원본 사진의 좌우 위치이며 RGB 색 추정은 제거했습니다. RANSAC 바닥은 분류 신뢰도가 없는 기하 추정입니다.',
      '','맞음=TP, 과검출/잘못된 카테고리/중복=FP. 사진에서 빠진 물체는 한 개체당 한 줄로 추가합니다. 관계도 맞음/틀림과 누락 관계를 기록합니다. 관계는 같은 쌍의 역방향을 중복 정답으로 세지 않습니다.',
      '','| 사진 | 노드 | 관계 | 전체 표 |','|---|---:|---:|---|']
    for entry in manifest['images']:
        if entry['id'] not in SELECTED:continue
        directory=ROOT/entry['out'];raw=(directory/'graph.json').read_bytes();graph=json.loads(raw)
        photo={'id':entry['id'],'source':entry['image'],'graph_sha256':hashlib.sha256(raw).hexdigest(),
            'width':graph['camera']['width'],'height':graph['camera']['height'],'nodes':graph['nodes'],'edges':graph['edges']}
        photos.append(photo);shutil.copyfile(directory/'source.jpg',destination/(entry['id']+'.jpg'))
        names={n['id']:n.get('label',n['name']) for n in graph['nodes']}
        rows=[f"# {entry['id']} 검수표",'',f"![원본]({entry['id']}.jpg)",'','## 노드','',
            '| ID | 라벨 | 신뢰도 | 2D 박스 (x1,y1,x2,y2) | 판정 / 수정 |','|---|---|---:|---|---|']
        for n in graph['nodes']:
            score=f"{n['score']:.3f}" if n.get('score') is not None else 'RANSAC (분류 신뢰도 아님)'
            rows.append(f"| {n['id']} | {names[n['id']]} | {score} | {n['bbox2d']} | 미검수 |")
        rows+=['','## 관계','','| 번호 | 주체 | 관계 | 대상 | 판정 / 수정 |','|---:|---|---|---|---|']
        for i,e in enumerate(graph['edges']):rows.append(f"| {i} | {names[e['source']]} | {e['relation']} | {names[e['target']]} | 미검수 |")
        rows+=['','## 누락 항목','','물체는 개체별 한 줄, 관계는 주체 / 관계 / 대상으로 추가해 주세요.','']
        (destination/(entry['id']+'.md')).write_text('\n'.join(rows),encoding='utf-8')
        with (destination/(entry['id']+'-nodes.csv')).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['id','label','score','bbox2d','decision','correction'])
            for n in graph['nodes']:writer.writerow([n['id'],names[n['id']],n['score'],n['bbox2d'],'',''])
        with (destination/(entry['id']+'-relations.csv')).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['index','source','source_label','relation','target','target_label','decision','correction'])
            for i,e in enumerate(graph['edges']):writer.writerow([i,e['source'],names[e['source']],e['relation'],e['target'],names[e['target']],'',''])
        index.append(f"| {entry['id']} | {len(graph['nodes'])} | {len(graph['edges'])} | [노드·관계 목록]({entry['id']}.md) |")
    pack={'version':1,'status':'awaiting-human-review','photos':photos}
    pack['pack_id']=hashlib.sha256(json.dumps(photos,sort_keys=True).encode()).hexdigest()[:16]
    (destination/'review-pack.json').write_text(json.dumps(pack,ensure_ascii=False,indent=2),encoding='utf-8')
    template=(ROOT/'pipelines/scene/review-template.html').read_text(encoding='utf-8')
    (destination/'index.html').write_text(template.replace('__REVIEW_DATA__',json.dumps(pack,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
    index+=['','HTML에서 항목을 검수하고 누락 항목을 입력한 뒤 **검수 확정 JSON 저장**을 누르세요. 임시 저장은 정답 확정으로 취급하지 않습니다.',
            '','확정 JSON을 받은 뒤 실행: `python -m pipelines.scene.review_evaluate PATH_TO_REVIEW_JSON`','',
            '노드 precision = TP/(TP+FP), 과검출 비율 = FP/(TP+FP), recall = TP/(TP+FN). 관계도 같은 정의를 사용합니다. 결과는 이 5장 검수 범위에 한정합니다.']
    (destination/'README.md').write_text('\n'.join(index),encoding='utf-8')
    print(json.dumps({'pack_id':pack['pack_id'],'photos':[{ 'id':p['id'],'nodes':len(p['nodes']),'relations':len(p['edges'])} for p in photos]},indent=2))

if __name__=='__main__':run()
