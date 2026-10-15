import tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from pipelines.scene.cleanup import clean_nodes

class CleanupTest(unittest.TestCase):
    def test_reflection_duplicate_and_distinct_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(100,100),'white').save(root/'source.jpg')
            nodes=[]
            def node(nid,name,rect,box,score=.9):
                mask=np.zeros((100,100),np.uint8);x,y,w,h=rect;mask[y:y+h,x:x+w]=255
                Image.fromarray(mask).save(root/f'{nid}.png')
                nodes.append(dict(id=nid,name=name,mask=f'{nid}.png',box=box,score=score))
            node('mirror','mirror',(0,0,60,100),{'min':[0,0,-2],'max':[2,2,-1.9]})
            node('reflection','chair',(10,10,30,30),{'min':[.2,.2,-4],'max':[1,1,-3]})
            node('real','chair',(65,10,30,30),{'min':[3,0,-1],'max':[4,1,0]})
            node('duplicate','chair',(65,10,30,30),{'min':[3.01,0,-1],'max':[4,1,0]},.8)
            node('low','table',(65,50,30,30),{'min':[3,0,-1],'max':[4,1,0]},.52)
            kept,audit=clean_nodes(nodes,root)
            self.assertEqual({n['id'] for n in kept},{'mirror','real'})
            self.assertTrue(any(x['reason']=='inside-reflective-region' for x in audit['removed']))
            self.assertEqual(audit['merged'][0]['into'],'real')
            self.assertTrue(all('label' in n for n in kept))

if __name__=='__main__':unittest.main()
