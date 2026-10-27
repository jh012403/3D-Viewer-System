"""Contract checks against the separately running prepared server, no inference."""
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.schemas.job import UploadResponse,JobRecord,JobResultResponse,SegmentationCandidatesResponse

class PreparedContracts(unittest.TestCase):
    base='http://127.0.0.1:8020'

    def test_off_is_disabled(self):
        env={**os.environ,'DEMO_MODE':'0'}
        result=subprocess.run([sys.executable,str(ROOT/'demo/demo_server.py')],env=env,capture_output=True,timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'Prepared API is disabled',result.stderr)

    def test_response_contract_and_click_independence(self):
        upload=requests.post(self.base+'/api/upload',files={'file':('x.jpg',b'fixed-demo-input')},data={'type':'image_to_3d'},timeout=10)
        value=UploadResponse.model_validate(upload.json());jid=value.job_id
        a=requests.post(self.base+f'/api/jobs/{jid}/segmentation-prompt',json={'points':[{'x':1,'y':1,'label':1}]},timeout=10).json()
        b=requests.post(self.base+f'/api/jobs/{jid}/segmentation-text-prompt',json={'prompt':'arbitrary alternate choice'},timeout=10).json()
        SegmentationCandidatesResponse.model_validate(a)
        self.assertEqual(a['candidates'],b['candidates'])
        job=requests.post(self.base+'/api/jobs',json={'job_id':jid,'type':'image_to_3d'},timeout=10).json()
        self.assertEqual(JobRecord.model_validate(job).status,'running')
        time.sleep(8.1)
        result=requests.get(self.base+f'/api/jobs/{jid}/result',timeout=10)
        JobResultResponse.model_validate(result.json())
        self.assertEqual(result.headers['X-PRISM-Demo-Mode'],'prepared-results')
        html=requests.get('http://127.0.0.1:5174/prismscan-v2.html',timeout=10).text
        self.assertIn('window.__AI3D_API_BASE_URL="http://127.0.0.1:8020"',html)

if __name__=='__main__':unittest.main()
