import datetime,gc,json,pathlib,threading
from flask import Flask,Response,jsonify,request,stream_with_context
from .config import LABELS,ROOT,TEXT_MODULES,defaults
from .control import reserve_gpu
from .runtime import validated_record
from .storage import read_json


def active_path(c):
    module=c['module']
    rec=validated_record(module,c.get('state_dir'))
    if rec and rec.get('adapter'):
        p=pathlib.Path(rec['adapter'])
        if p.exists():
            return p
    for fname in ('adapter.safetensors','adapter_model.safetensors'):
        renf=pathlib.Path(ROOT)/'modele'/'renforce'/module/fname
        if renf.exists():
            return renf
    return None

SERVE_PORT=11435
MODEL_PREFIX='aurora-rl-'
CHAT_MODULES=TEXT_MODULES
LOCK=threading.Lock()
CACHE={'module':None,'signature':None,'tokenizer':None,'model':None}


def model_tag(module):
    return f'{MODEL_PREFIX}{module}:selected'


def parse_tag(name):
    raw=(name or '').strip()
    if not raw.startswith(MODEL_PREFIX):
        return None
    module=raw[len(MODEL_PREFIX):].split(':',1)[0]
    return module if module in LABELS else None


def selected_entry(c):
    module=c['module']
    path=active_path(c)
    if not path:
        return None
    meta=read_json(pathlib.Path(c['state_dir'])/'registry'/module/'active.json',{})
    flagship=c.get('flagship_ollama_models',{}).get(module,c['models'].get(module,''))
    return {'name':model_tag(module),'model':model_tag(module),'modified_at':meta.get('activated_at',''),
            'size':path.stat().st_size if path.exists() else 0,'digest':meta.get('sha256',''),
            'details':{'family':'aurora-rl-flagship-council','parameter_size':'80B+32B+27B-MoA','quantization_level':'Flagship-MoA-DPO',
                       'module':module,'label':LABELS[module],'adapter_path':str(path),
                       'flagship_specialist':flagship,
                       'mean':meta.get('Candidate mean'),'delta':meta.get('Delta vs baseline')}}


def available_models(state_dir=None):
    items=[]
    for module in CHAT_MODULES:
        c=defaults(module)
        if state_dir:c['state_dir']=str(state_dir)
        entry=selected_entry(c)
        if entry:items.append(entry)
    return {'models':items}


def unload():
    if CACHE['model'] is not None:
        del CACHE['model'],CACHE['tokenizer']
        CACHE.update({'module':None,'signature':None,'tokenizer':None,'model':None})
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():torch.cuda.empty_cache()
        except Exception:
            pass


def _load(c):
    path=active_path(c)
    if not path:
        raise RuntimeError(f'Aucun adaptateur validé pour {LABELS[c["module"]]}')
    sig=(c['module'],str(path),path.stat().st_mtime_ns)
    if CACHE['signature']==sig and CACHE['model'] is not None:
        return CACHE['tokenizer'],CACHE['model'],path
    unload()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig
    name=c['models'][c['module']]
    tok=AutoTokenizer.from_pretrained(name)
    if tok.pad_token is None:tok.pad_token=tok.eos_token
    q=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    base=AutoModelForCausalLM.from_pretrained(name,quantization_config=q,device_map={'':0},torch_dtype=torch.bfloat16,low_cpu_mem_usage=True)
    model=PeftModel.from_pretrained(base,str(path),is_trainable=False).eval()
    CACHE.update({'module':c['module'],'signature':sig,'tokenizer':tok,'model':model})
    return tok,model,path


def generate_chat(c,messages,options=None):
    options=options or {}
    # By default, route reinforced requests through the Flagship Mixture-of-Agents Council
    # (80B Qwen3-Coder-Next / 80B Qwen-Cyber / 32B DeepSeek-R1 / 30B Qwen3-VL / 27B Qwen3.8-Uncensored)
    # enriched with the module's distilled DPO/RL invariants, unless raw PEFT tensor test is forced.
    if not options.get('use_local_peft_only'):
        try:
            from agi_core.flagship_council import run_moa_council
            has_images=any(isinstance(m,dict) and m.get('images') for m in messages)
            res=run_moa_council(
                '',
                messages=messages,
                module=c['module'],
                depth=str(options.get('depth') or 'max'),
                require_vision=has_images,
                temperature=float(options.get('temperature',c['generation'].get('temperature',0.3))),
                num_ctx=max(int(options.get('num_ctx') or 32768),32768),
                num_predict=max(int(options.get('num_predict') or c['generation'].get('max_new_tokens',16384)),8192),
            )
            if res.get('ok') and res.get('content'):
                return res['content'],res.get('model') or c['module']
        except Exception:
            pass

    import torch
    with LOCK,reserve_gpu(c,'serve',c['module']):
        tok,model,path=_load(c)
        rendered=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        tokens=tok(rendered,return_tensors='pt').to('cuda')
        maximum=min(int(options.get('num_predict',c['generation']['max_new_tokens'])),4096)
        temperature=float(options.get('temperature',c['generation']['temperature']))
        sample=temperature>0
        kwargs={'max_new_tokens':maximum,'do_sample':sample,'pad_token_id':tok.pad_token_id,'eos_token_id':tok.eos_token_id}
        if sample:kwargs.update({'temperature':temperature,'top_p':float(options.get('top_p',c['generation']['top_p']))})
        with torch.inference_mode():
            out=model.generate(**tokens,**kwargs)
        text=tok.decode(out[0][tokens['input_ids'].shape[1]:],skip_special_tokens=True).strip()
        return text,path


def create_app(state_dir=None):
    app=Flask(__name__)
    @app.get('/health')
    def health():
        return jsonify({'ok':True,'service':'aurora-rl-serve','port':SERVE_PORT,'mode':'flagship-moa-council'})
    @app.get('/api/models/council-roster')
    def council_roster():
        from agi_core.flagship_council import get_all_modules_flagship_roster
        return jsonify(get_all_modules_flagship_roster())
    @app.get('/api/tags')
    def tags():
        return jsonify(available_models(state_dir))
    @app.post('/api/chat')
    def chat():
        data=request.get_json(force=True,silent=True) or {}
        module=parse_tag(data.get('model'))
        if not module:
            return jsonify({'error':'Modèle entraîné inconnu'}),404
        c=defaults(module)
        if state_dir:c['state_dir']=str(state_dir)
        messages=data.get('messages') or ([{'role':'user','content':data.get('prompt','')}] if data.get('prompt') else [])
        if not messages:
            return jsonify({'error':'Messages requis'}),400
        opts=data.get('options') or {}
        stream=bool(data.get('stream',False))
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        if stream and not opts.get('use_local_peft_only'):
            from agi_core.flagship_council import stream_moa_council_ollama_format
            return Response(
                stream_with_context(
                    stream_moa_council_ollama_format(
                        messages,
                        requested_model=data.get('model'),
                        module=module,
                        options=opts,
                        enable_reasoner_prepass=True,
                    )
                ),
                mimetype='application/x-ndjson',
            )
        text,_=generate_chat(c,messages,opts)
        body={'model':model_tag(module),'created_at':now,'message':{'role':'assistant','content':text},'done':True}
        if stream:
            return Response(json.dumps(body,ensure_ascii=False)+'\n',mimetype='application/x-ndjson')
        return jsonify(body)
    @app.post('/api/generate')
    def generate():
        data=request.get_json(force=True,silent=True) or {}
        module=parse_tag(data.get('model'))
        if not module:
            return jsonify({'error':'Modèle entraîné inconnu'}),404
        c=defaults(module)
        if state_dir:c['state_dir']=str(state_dir)
        prompt=str(data.get('prompt') or '')
        sys_msg=str(data.get('system') or '')
        msgs=[]
        if sys_msg:
            msgs.append({'role':'system','content':sys_msg})
        msgs.append({'role':'user','content':prompt})
        text,_=generate_chat(c,msgs,data.get('options'))
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        body={'model':model_tag(module),'created_at':now,'response':text,'done':True}
        if data.get('stream'):
            return Response(json.dumps(body,ensure_ascii=False)+'\n',mimetype='application/x-ndjson')
        return jsonify(body)
    return app


if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=SERVE_PORT,threaded=True)
