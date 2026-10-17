import multiprocessing as mp
import tempfile
from pathlib import Path
from backend.app.core.job_store import locked_file
def increment(path):
 for _ in range(20):
  with locked_file(Path(path)) as f:
   value=int(f.read() or '0');f.seek(0);f.truncate();f.write(str(value+1))
if __name__=='__main__':
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp)/'sequence';procs=[mp.Process(target=increment,args=(str(path),)) for _ in range(4)]
  for p in procs:p.start()
  for p in procs:p.join();assert p.exitcode==0
  assert path.read_text()=='80'
  try:
   with locked_file(path):raise ValueError('test release')
  except ValueError:pass
  with locked_file(path) as f:assert f.read()=='80'
 print('Concurrent sequence and exception lock release passed')
