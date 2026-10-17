"""Run the unchanged official TRELLIS helper in WSL from the Windows service."""
import os,re,shlex,subprocess,sys
def translate(value):
    # Runtime helper paths and inline probe strings may contain Windows paths.
    return re.sub(r'([A-Za-z]):[/\\]([^\s\"\']*)',lambda m:'/mnt/'+m[1].lower()+'/'+m[2].replace('\\','/'),value)
if __name__=='__main__':
    args=[translate(a) for a in sys.argv[1:]]
    command=['env','PYTHONPATH=/opt/prism/TRELLIS.2','CUDA_HOME=/usr/local/cuda-12.4','PATH=/usr/local/cuda-12.4/bin:/opt/prism/trellis2/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
      'HF_HOME=/opt/prism/hf','HF_HUB_OFFLINE=1','TRANSFORMERS_OFFLINE=1','ATTN_BACKEND=flash_attn','SPARSE_ATTN_BACKEND=flash_attn','SPARSE_CONV_BACKEND=flex_gemm','MAX_JOBS=4',
      '/opt/prism/trellis2/bin/python',*args]
    setup='if [ -f /opt/prism/swapfile ]; then swapon /opt/prism/swapfile 2>/dev/null || true; fi; '
    result=subprocess.run([r'C:\Program Files\WSL\wsl.exe','-d','Ubuntu-22.04','-u','root','--','bash','-lc',setup+'exec '+shlex.join(command)])
    sys.exit(result.returncode)
