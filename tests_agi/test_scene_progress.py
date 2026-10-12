import importlib.util
from pathlib import Path
import sys
import threading

source=Path(__file__).resolve().parents[1]/'application/python-services/scene_process.py'
spec=importlib.util.spec_from_file_location('scene_process_fixture',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_entity_progress_arrives_before_child_finishes_and_json_is_preserved(tmp_path):
    child=tmp_path/'child.py'
    child.write_text("import time\nprint('PROGRESS:shape:real child step',flush=True)\ntime.sleep(.5)\nprint('{\"ok\":true}')\n",encoding='utf-8')
    progress=threading.Event();result=[]
    thread=threading.Thread(target=lambda:result.append(module.run_entity([sys.executable,str(child)],on_progress=lambda line:progress.set())))
    thread.start();assert progress.wait(3);assert thread.is_alive()
    thread.join(5);assert not thread.is_alive()
    assert result[0].returncode==0 and '{"ok":true}' in result[0].stdout
