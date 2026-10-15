import tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from pipelines.scene.floor import augment_floor

class FloorTest(unittest.TestCase):
    def test_observed_plane_does_not_complete_hidden_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);h=w=300;yy,xx=np.mgrid[:h,:w]
            depth=np.where(yy>150,200/np.maximum(yy-150,1),20).astype(np.float32)
            np.save(root/'depth.npy',depth)
            mask=(yy>240)&(xx>240);Image.fromarray(mask.astype(np.uint8)*255).save(root/'mask.png')
            floor={'id':'floor','name':'floor','mask':'mask.png','mask_pixels':int(mask.sum()),'box':{'min':[0,-1.02,-3],'max':[2,-.98,-1]}}
            chair={'id':'chair','name':'chair','box':{'min':[0,-.5,-3],'max':[1,.5,-2]}}
            nodes,audit=augment_floor([floor,chair],root,{'fx':200,'fy':200,'cx':150,'cy':150})
            self.assertEqual(audit['status'],'estimated')
            self.assertAlmostEqual(floor['plane']['height_coefficients'][2],-1,places=3)
            self.assertGreater(floor['mask_pixels'],mask.sum())
            self.assertEqual(chair['box']['min'][1],-.5)
            self.assertFalse(audit['hidden_supports_completed'])

if __name__=='__main__':unittest.main()
