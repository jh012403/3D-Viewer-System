import unittest
import numpy as np
from pipelines.scene.build import align_scale, surface

class GeometryTest(unittest.TestCase):
    def test_known_scale_with_outlier(self):
        h,w=60,80; f=70
        yy,xx=np.mgrid[:h,:w]; z=np.full((h,w),2.)
        p=np.stack(((xx-w/2)*z/f,(yy-h/2)*z/f,z),-1)
        depth=np.full((h,w),5.,dtype=np.float32);depth[:2]=12
        scale,d=align_scale(p,np.ones((h,w)),depth,f)
        self.assertAlmostEqual(scale,2.5)
        self.assertGreater(d["samples"],500)
    def test_surface_reprojection_and_discontinuities(self):
        d=np.ones((20,20),dtype=np.float32);d[:,10:]=10
        result=surface(d,20,stride=1)
        p=np.array(result["positions"]).reshape(-1,3);faces=np.array(result["indices"]).reshape(-1,3)
        self.assertTrue(np.all(np.ptp(p[faces,2],axis=1)<1))
        z=-p[:,2];u=p[:,0]*20/z+10;v=-p[:,1]*20/z+10
        yy,xx=np.mgrid[:20,:20]
        np.testing.assert_allclose(u,xx.ravel(),atol=1e-5)
        np.testing.assert_allclose(v,yy.ravel(),atol=1e-5)
    def test_no_depth_rejects(self):
        with self.assertRaises(ValueError):
            align_scale(np.zeros((10,3)),np.ones(10),np.zeros((20,20)),20)
if __name__=="__main__":unittest.main()
