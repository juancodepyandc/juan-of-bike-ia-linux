"""One local desktop challenge at a time; remote requests never approve themselves."""
from __future__ import annotations
import html
import os
import queue
import shutil
import subprocess
import sys
import threading
import time


def ask_code(name, timeout, *, platform=None, run=subprocess.run):
    platform=platform or sys.platform
    text=('Demande de connexion Aurora : '+name+'\n\nSaisissez le code affiché sur votre téléphone ou dans votre CLI.\nSi vous ne reconnaissez pas cette demande, annulez.')
    timeout=max(1,int(timeout))
    if platform=='win32':
        # Text travels as data over stdin, never interpolated into PowerShell.
        import base64
        script="$text=[Console]::In.ReadToEnd(); Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.Interaction]::InputBox($text,'Connexion Aurora','')"
        command=['powershell.exe','-NoProfile','-STA','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()]
        result=run(command,input=text,capture_output=True,text=True,timeout=timeout)
    elif platform=='darwin':
        script='on run argv\ntry\nset answer to display dialog (item 1 of argv) default answer "" with title "Connexion Aurora" buttons {"Annuler", "Autoriser"} default button "Autoriser" giving up after '+str(timeout)+'\nif gave up of answer then return ""\nreturn text returned of answer\non error\nreturn ""\nend try\nend run'
        result=run(['osascript','-e',script,text],capture_output=True,text=True,timeout=timeout+2)
    else:
        if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):raise OSError('Aucun bureau graphique disponible.')
        if shutil.which('zenity'):
            command=['zenity','--entry','--title=Connexion Aurora','--text='+html.escape(text),'--entry-text=','--ok-label=Autoriser','--cancel-label=Refuser','--timeout='+str(timeout),'--width=480']
        elif shutil.which('kdialog'):
            command=['kdialog','--title','Connexion Aurora','--inputbox',text,'']
        else:raise OSError("Aucun dialogue disponible sur ce bureau.")
        result=run(command,capture_output=True,text=True,timeout=timeout)
    return (result.stdout.strip() or None) if result.returncode==0 else None


def _cancellable_run(command,*,pending,input=None,capture_output=True,text=True,timeout=300):
    process=subprocess.Popen(command,stdin=subprocess.PIPE if input is not None else None,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=text)
    deadline=time.monotonic()+timeout
    try:
        while True:
            if not pending() or time.monotonic()>=deadline:
                process.kill();out,err=process.communicate();return subprocess.CompletedProcess(command,1,out,err)
            try:
                out,err=process.communicate(input=input,timeout=min(.3,max(.01,deadline-time.monotonic())))
                return subprocess.CompletedProcess(command,process.returncode,out,err)
            except subprocess.TimeoutExpired:input=None
    finally:
        if process.poll() is None:process.kill();process.communicate()


class DesktopApproval:
    def __init__(self, lookup, approve, decline, *, prompt=ask_code):
        self.lookup=lookup;self.approve=approve;self.decline=decline;self.prompt=prompt
        self.queue=queue.Queue(maxsize=20)
        self.worker=threading.Thread(target=self._work,name='aurora-local-approval',daemon=True)
        self.worker.start()

    def request(self, identity):
        try:self.queue.put_nowait(identity)
        except queue.Full:pass  # Expiry still denies it; no automatic permission.

    def _work(self):
        while True:
            identity=self.queue.get()
            try:
                item=self.lookup(identity)
                if not item or item['approved']:continue
                remaining=item['expires']-time.time()
                if remaining<=0:continue
                name=item['name']
                while remaining>0:
                    try:
                        if self.prompt is ask_code:
                            def pending():
                                current=self.lookup(identity)
                                return bool(current and not current['approved'] and current['expires']>time.time())
                            code=self.prompt(name,remaining,run=lambda command,**kwargs:_cancellable_run(command,pending=pending,**kwargs))
                        else:code=self.prompt(name,remaining)
                    except (OSError,subprocess.SubprocessError):break  # Headless desktop: local manager remains available.
                    if code is None:
                        current=self.lookup(identity)
                        if current and not current['approved']:self.decline(identity)
                        break
                    if code and self.approve(identity,code):break
                    item=self.lookup(identity)
                    if not item or item['approved']:break
                    remaining=item['expires']-time.time()
                    name=item['name']+'\nCode incorrect. Recopiez celui affiché sur l’appareil.'
            finally:self.queue.task_done()
