"""Forward real child progress while retaining its JSON result and diagnostics."""
import subprocess
import threading

def run_entity(command,*,timeout=7200,on_progress=print):
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
    buffers={'stdout':[],'stderr':[]};sizes={'stdout':0,'stderr':0}
    def read(name,stream):
        for line in stream:
            buffers[name].append(line);sizes[name]+=len(line)
            while sizes[name]>8*1024*1024 and len(buffers[name])>1:sizes[name]-=len(buffers[name].pop(0))
            if line.startswith(('PROGRESS:','SCENE_ORCH')):on_progress(line.rstrip('\n'))
        stream.close()
    threads=[threading.Thread(target=read,args=(name,getattr(process,name)),daemon=True) for name in buffers]
    for thread in threads:thread.start()
    try:process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill();process.wait()
        raise
    finally:
        for thread in threads:thread.join(timeout=5)
    return subprocess.CompletedProcess(command,process.returncode,''.join(buffers['stdout']),''.join(buffers['stderr']))
