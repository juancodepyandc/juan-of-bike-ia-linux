"""Ollama-compatible inference endpoint for explicitly selected audited models."""
from __future__ import annotations
import argparse
import gc
import json
import queue
import threading
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from .config import STATE,LABELS
from .runtime import catalog, validated_record
from .storage import exclusive_lock

app=FastAPI(title='Aurora — modèles entraînés')
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware,allow_origins=["http://127.0.0.1:1420","http://localhost:1420","tauri://localhost","http://tauri.localhost"],allow_methods=["GET","POST"],allow_headers=["Content-Type"])
lock=threading.Lock()


@app.get('/api/tags')
def tags():return {'models':catalog(include_base=True)}


@app.get('/health')
def health():return {'ready':True,'validated_models':len(catalog())}


@app.post('/api/media/generate')
def media_generate(body:dict):
    if not isinstance(body.get('module'),str) or body.get('module') not in LABELS:
        raise HTTPException(400,'Module média inconnu')
    if not isinstance(body.get('prompt'),str) or not 1<=len(body['prompt'].strip())<=6000:
        raise HTTPException(400,'Description requise, 6000 caractères maximum')
    events=queue.Queue()
    def worker():
        try:
            from .media import generate as run_media
            with lock:
                result=run_media(body['module'],body['prompt'],body['use_base'] if isinstance(body.get('use_base'),bool) else None,
                                 reference_id=body.get('reference_id'),candidate_id=body.get('candidate_id'))
            events.put({**result,'done':True})
        except Exception as exc:events.put({'error':str(exc),'done':True})
    threading.Thread(target=worker,daemon=True).start()
    def stream():
        while True:
            try:item=events.get(timeout=3)
            except queue.Empty:
                yield json.dumps({'done':False,'status':'Génération en cours'})+'\n'
                continue
            yield json.dumps(item,ensure_ascii=False)+'\n'
            if item.get('done'):break
    return StreamingResponse(stream(),media_type='application/x-ndjson')


@app.post('/api/show')
def show(body:dict):
    model=next((m for m in catalog(include_base=True) if m['name']==body.get('model',body.get('name'))),None)
    if not model:raise HTTPException(404,'Modèle validé introuvable')
    return {'details':model['details'],'capabilities':['completion'],'model_info':{'general.architecture':'qwen3','qwen3.context_length':4096}}


def generate(body,events):
    backend=None
    try:
        from .backends import CodeBackend, resolve_paths
        from .config import defaults
        model=next((m for m in catalog(include_base=True) if m['name']==body['model']),None)
        if not model:raise ValueError('Version du modèle absente du registre validé')
        use_base=model.get('selection')=='base'
        record=validated_record(model['module']) if not use_base else None
        if not use_base and (not record or record['sha256'] != model['digest']):
            raise ValueError('Le modèle validé a changé pendant la requête ; actualiser la liste')
        config=record['config'] if record else defaults(model['module'])
        c={**config,'generation':dict(config['generation'])}
        options=body.get('options') or {}
        maximum=options.get('num_predict',c['generation']['max_new_tokens'])
        c['generation'].update(max_new_tokens=min(2048,max(1,int(maximum))),temperature=float(options.get('temperature',.7)),top_p=float(options.get('top_p',.9)))
        messages=body.get('messages') or [{'role':'user','content':body.get('prompt','')}]
        if body.get('tools') or any(m.get('images') or m.get('tool_calls') or m.get('role')=='tool' for m in messages):
            raise ValueError('Ce modèle entraîné accepte uniquement du texte ; images et appels d’outils ne sont pas pris en charge.')
        if any(m.get('role') not in {'user','assistant','system'} or not isinstance(m.get('content'),str) for m in messages):
            raise ValueError('Messages texte invalides')
        if sum(len(m['content']) for m in messages)>24000:
            raise ValueError('Contexte trop long pour ce profil local')
        with lock, exclusive_lock(STATE/'cycle.lock'):
            backend=CodeBackend(c,resolve_paths(c))
            if record:backend.adapter.load(record['adapter'])
            else:backend.adapter.enabled=False
            prompt=backend.tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            if len(backend.tokenizer.encode(prompt))+c['generation']['max_new_tokens']>4096:
                raise ValueError('Le profil entraîné est limité à 4096 tokens, réponse comprise')
            answer=backend.chat(messages,int(options.get('seed',42)))
            events.put({'model':body['model'],'message':{'role':'assistant','content':answer},'response':answer,'done':True,'done_reason':'stop'})
    except Exception as exc:
        events.put({'error':str(exc),'done':True})
    finally:
        if backend:backend.close()
        del backend
        gc.collect()
        import torch
        torch.cuda.empty_cache()


@app.post('/api/chat')
@app.post('/api/generate')
def chat(body:dict):
    if body.get('model') not in {m['name'] for m in catalog(include_base=True)}:
        raise HTTPException(404,'Aucun modèle validé sous ce nom')
    events=queue.Queue()
    threading.Thread(target=generate,args=(body,events),daemon=True).start()
    if body.get('stream',True) is False:
        result=events.get(timeout=600)
        if result.get('error'):raise HTTPException(503,result['error'])
        return result
    def stream():
        while True:
            try:item=events.get(timeout=3)
            except queue.Empty:
                yield json.dumps({'model':body['model'],'message':{'role':'assistant','content':''},'done':False})+'\n'
                continue
            yield json.dumps(item,ensure_ascii=False)+'\n'
            if item.get('done'):break
    return StreamingResponse(stream(),media_type='application/x-ndjson')


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=11435);a=p.parse_args()
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=a.port)

if __name__=='__main__':main()
