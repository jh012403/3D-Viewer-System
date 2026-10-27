import argparse
import asyncio
import json
import unittest
from unittest.mock import AsyncMock,Mock,patch
from run import Demo,ROOT

class RecordingControl(unittest.IsolatedAsyncioTestCase):
    def demo(self):
        d=Demo(json.loads((ROOT/'demo/config.json').read_text(encoding='utf-8')),argparse.Namespace(speed=.3,rehearsal=False))
        d.p=Mock();d.p.evaluate=AsyncMock();return d

    async def test_manual_countdown_is_five_real_seconds(self):
        d=self.demo()
        with patch('run.obs.ReqClient',side_effect=ConnectionError('unavailable')),patch('run.asyncio.sleep',new_callable=AsyncMock) as sleep:
            await d.setup_obs()
        self.assertEqual([c.args for c in sleep.call_args_list],[(1,)]*5)
        self.assertFalse(d.owns_record)
        self.assertEqual(d.report['recording_mode'],'manual')

    async def test_does_not_take_over_existing_recording(self):
        d=self.demo();client=Mock();client.get_record_status.return_value.output_active=True
        with patch('run.obs.ReqClient',return_value=client):
            with self.assertRaisesRegex(RuntimeError,'already recording'):await d.setup_obs()
        await d.finish_obs()
        client.start_record.assert_not_called();client.stop_record.assert_not_called()

if __name__=='__main__':unittest.main()
