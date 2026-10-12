import subprocess
import time
from types import SimpleNamespace
from application.desktop_pairing import DesktopApproval,ask_code


def test_native_prompt_treats_device_name_as_data():
    calls=[]
    def run(command,**kwargs):calls.append((command,kwargs));return SimpleNamespace(returncode=0,stdout='123456\n')
    for platform in ['win32','darwin']:
        assert ask_code('CLI " ; malicious & <name>',20,platform=platform,run=run)=='123456'
    assert calls[0][1]['input'].startswith('Demande de connexion Aurora : CLI "')
    assert 'malicious' not in ' '.join(calls[0][0])
    assert 'malicious' not in calls[1][0][2]


def test_queue_wrong_code_never_approves_then_correct_challenge():
    item={'name':'Un appareil','expires':time.time()+10,'approved':False};entries=iter(['999999','123456']);attempts=[];declined=[]
    def approve(identity,code):attempts.append(code);item['approved']=code=='123456';return item['approved']
    popup=DesktopApproval(lambda i:item,approve,declined.append,prompt=lambda n,t:next(entries))
    popup.request('unique');popup.queue.join()
    assert attempts==['999999','123456'] and item['approved'] and not declined


def test_cancel_and_expiry_fail_closed():
    item={'name':'Inconnu','expires':time.time()+10,'approved':False};declined=[];approved=[]
    popup=DesktopApproval(lambda i:item,lambda *a:approved.append(a),declined.append,prompt=lambda *a:None)
    popup.request('cancel');popup.queue.join();assert declined==['cancel'] and not approved
    item['expires']=time.time()-1;popup.request('expired');popup.queue.join();assert declined==['cancel']


def test_external_approval_closes_prompt_without_revoking_pending_claim():
    item={'name':'Appareil','expires':time.time()+10,'approved':False};declined=[]
    def prompt(*a):item['approved']=True;return None
    popup=DesktopApproval(lambda i:item,lambda *a:False,declined.append,prompt=prompt)
    popup.request('external');popup.queue.join();assert item['approved'] and not declined
