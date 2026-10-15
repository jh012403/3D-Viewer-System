import unittest
from copy import deepcopy
from pipelines.scene.review_evaluate import evaluate

class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.pack={'pack_id':'unit-fixture','photos':[{'id':'fixture','graph_sha256':'hash','nodes':[{'id':'a'},{'id':'b'},{'id':'duplicate'}],'edges':[{'source':'a','target':'b'}]}]}
        self.review={'pack_id':'unit-fixture','confirmed':True,'reviewer':'unit test fixture, not real review','photos':[{'id':'fixture','graph_sha256':'hash','missing_checked':True,'nodes':{'a':{'decision':'tp'},'b':{'decision':'tp'},'duplicate':{'decision':'duplicate'}},'edges':{'0':{'decision':'tp'}},'missing_nodes':['missed object'],'missing_edges':[]}]}
    def test_precision_recall_and_duplicate_penalty(self):
        result=evaluate(self.pack,self.review)['micro_average']['nodes']
        self.assertAlmostEqual(result['precision'],2/3);self.assertAlmostEqual(result['recall'],2/3)
        self.assertAlmostEqual(result['over_detection_rate'],1/3)
    def test_draft_rejected(self):
        self.review['confirmed']=False
        with self.assertRaises(ValueError):evaluate(self.pack,self.review)
    def test_inconsistent_edge_rejected(self):
        self.review['photos'][0]['nodes']['b']['decision']='fp'
        with self.assertRaises(ValueError):evaluate(self.pack,self.review)
    def test_changed_snapshot_rejected(self):
        self.review['pack_id']='other'
        with self.assertRaises(ValueError):evaluate(self.pack,self.review)
if __name__=='__main__':unittest.main()
