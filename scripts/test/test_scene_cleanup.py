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
            self.assertTrue(all(n['attribute_method']=='original-image-horizontal-position' for n in kept))

    def test_compressed_reflection_below_glass_shelf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(100,100),'brown').save(root/'source.jpg')
            nodes=[]
            for nid,name,rect,box in [
                ('shelf','glass shelf',[0,55,100,100],{'min':[-1,-1.1,-2],'max':[1,-1,-1]}),
                ('real','bottle',[30,10,60,60],{'min':[0,-.98,-1.7],'max':[.2,-.5,-1.5]}),
                ('reflection','bottle',[30,60,60,90],{'min':[0,-1.13,-1.7],'max':[.2,-1.06,-1.5]})]:
                mask=np.zeros((100,100),np.uint8);x1,y1,x2,y2=rect;mask[y1:y2,x1:x2]=255
                Image.fromarray(mask).save(root/(nid+'.png'))
                nodes.append(dict(id=nid,name=name,mask=nid+'.png',bbox2d=rect,box=box,score=.9))
            kept,audit=clean_nodes(nodes,root)
            self.assertEqual({n['id'] for n in kept},{'shelf','real'})
            self.assertTrue(any(r['reason']=='reflection-below-horizontal-surface' for r in audit['removed']))

if __name__=='__main__':unittest.main()
