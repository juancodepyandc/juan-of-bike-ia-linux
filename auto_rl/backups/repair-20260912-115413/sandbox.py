"""Generated programs run only in bounded, networkless Podman containers."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

RUNNER = '''import importlib.util,json,sys,traceback
spec=importlib.util.spec_from_file_location("candidate","/work/program.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
fn=getattr(m,sys.argv[1])
for line in sys.stdin:
    try:
        item=json.loads(line)
        value=fn(*item.get("args",[]),**item.get("kwargs",{}))
        print(json.dumps({"value":value},allow_nan=False),flush=True)
    except BaseException as e:
        print(json.dumps({"error":type(e).__name__+": "+str(e)[:400]}),flush=True)
'''


class Sandbox:
    def __init__(self, image="docker.io/library/python:3.12-slim", timeout=12):
        self.image, self.timeout = image, timeout

    def check(self):
        if not shutil.which("podman"):
            raise RuntimeError("Podman manque : aucun code généré ne sera exécuté sur l'hôte")
        r = subprocess.run(["podman", "image", "exists", self.image], timeout=15)
        if r.returncode:
            raise RuntimeError(f"Image de sandbox absente : {self.image}")

    def execute(self, files, command, stdin=""):
        name = "aurora-rl-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix="aurora-sandbox-") as directory:
            root = Path(directory)
            root.chmod(0o755)
            for name_, content in files.items():
                if Path(name_).name != name_:
                    raise ValueError("Nom de fichier de sandbox invalide")
                (root / name_).write_text(content)
                (root / name_).chmod(0o444)
            argv = ["podman", "run", "--rm", "--pull=never", "--name", name,
                    "--network=none", "--read-only", "--cap-drop=ALL",
                    "--security-opt=no-new-privileges", "--pids-limit=32",
                    "--memory=512m", "--memory-swap=512m", "--cpus=1",
                    "--ulimit=cpu=10:10", "--ulimit=fsize=1048576:1048576",
                    "--ulimit=nofile=64:64", "--user=65534:65534",
                    "--tmpfs=/tmp:rw,noexec,nosuid,size=32m",
                    "-v", f"{root}:/work:ro", "-w", "/work", "-i", self.image, *command]
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=output, stderr=errors)
                try:
                    p.stdin.write(stdin.encode())
                    p.stdin.close()
                    start = time.monotonic()
                    reason = None
                    while p.poll() is None:
                        if time.monotonic() - start > self.timeout:
                            reason = "Temps d'exécution dépassé"
                            break
                        if os.fstat(output.fileno()).st_size + os.fstat(errors.fileno()).st_size > 128_000:
                            reason = "Sortie excessive"
                            break
                        time.sleep(0.05)
                    if reason:
                        subprocess.run(["podman", "rm", "-f", name], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=15)
                        p.kill()
                    p.wait(timeout=15)
                    output.seek(0)
                    errors.seek(0)
                    return {"exit_code": p.returncode if not reason else -1,
                            "stdout": output.read(65536).decode(errors="replace"),
                            "stderr": reason or errors.read(8192).decode(errors="replace")}
                finally:
                    if p.poll() is None:
                        p.kill()
                        p.wait()
                    subprocess.run(["podman", "rm", "-f", name], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=15)

    def python(self, code, function, cases):
        if not function.isidentifier():
            raise ValueError("Nom de fonction invalide")
        r = self.execute({"program.py": code, "runner.py": RUNNER},
                         ["python", "-I", "/work/runner.py", function],
                         "".join(json.dumps(c) + "\n" for c in cases))
        try:
            r["results"] = [json.loads(line) for line in r["stdout"].splitlines()]
        except (ValueError, TypeError):
            r["results"] = []
        return r

    def cpp(self, code, stdin):
        # Fixed command; generated source is never interpolated into shell code.
        return self.execute({"program.cpp": code}, ["sh", "-c",
            "g++ -std=c++17 -O2 /work/program.cpp -o /tmp/program && /tmp/program"], stdin)

    def bash(self, code, setup_script=""):
        # Executes a bash script for cyber/cowork/conversation agents
        # setup_script can be used to set up the container state before the model's script runs
        files = {"agent_script.sh": code}
        if setup_script:
            files["setup.sh"] = setup_script
            command = ["sh", "-c", "sh /work/setup.sh && sh /work/agent_script.sh"]
        else:
            command = ["sh", "-c", "sh /work/agent_script.sh"]
        
        return self.execute(files, command, "")
