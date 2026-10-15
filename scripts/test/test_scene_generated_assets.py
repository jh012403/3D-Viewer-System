import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import trimesh
from fastapi import HTTPException
from pipelines.scene import server

class GeneratedAssetTest(unittest.TestCase):
    def test_import_uses_completed_glb_and_existing_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'storage/outputs/test-job';out.mkdir(parents=True)
            assets=root/'scene-assets';assets.mkdir()
            mesh=trimesh.creation.box(extents=[2,3,2]);mesh.export(out/'object_mesh.glb')
            (out/'metadata.json').write_text(json.dumps({'asset_name':'fixture chair','object_category':'chair'}))
            with patch.object(server,'ROOT',root),patch.object(server,'asset_dir',assets):
                self.assertEqual(server.generated_assets()[0]['category'],'chair')
                result=asyncio.run(server.import_generated_asset('test-job'))
                self.assertEqual(result['source_job'],'test-job')
                self.assertTrue((assets/(result['id']+'.glb')).exists())
                self.assertEqual((assets/(result['id']+'.glb')).read_bytes(),(out/'object_mesh.glb').read_bytes())
                self.assertFalse(result['normalization_applied'])
                self.assertEqual(result['category'],'chair')
                with self.assertRaises(HTTPException):server.generated_asset('../escape')
                (out/'object_mesh.glb').write_bytes(b'glTF')
                self.assertEqual(server.generated_assets(),[])

if __name__=='__main__':unittest.main()
