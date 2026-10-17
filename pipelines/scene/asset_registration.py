"""Register automatic scene nodes without changing their detection/geometry."""
def register(nodes):
    for index,node in enumerate(nodes,1):
        box=node['box'];lo,hi=box['min'],box['max']
        node.update(asset_id=f'EQ-{index:04d}',asset_name=node.get('label') or node['name'],
          center_m=[round((a+b)/2,3) for a,b in zip(lo,hi)],
          dimensions_m={'width':round(hi[0]-lo[0],3),'depth':round(hi[2]-lo[2],3),'height':round(hi[1]-lo[1],3)},
          zone='미지정',status='등록됨',registration_source='현장 인식',dimension_source='monocular metric estimate')
    return nodes
