"""Reviewed stress cases and richer media briefs; no final-audit labels in training."""
import copy
import inspect
from .storage import digest


def harder_inputs(family, values, rng):
    extra=[]
    if family=='scheduling':extra=[[[i,i+3,(i%7)-2] for i in range(64)],[[0,100,99],[0,50,55],[50,100,55]]]
    elif family=='inversions':extra=[list(range(128,-1,-1)),[0,-1,0,1]*32]
    elif family in {'components','reachability','dependencies'}:
        extra=[{'n':48,'edges':[[i,i+1] for i in range(39)]+[[0,1],[1,2]]},
               {'n':32,'edges':[[i,(i+1)%24] for i in range(24)]+[[25,25]]}]
    elif family=='routes':extra=[{'n':40,'start':0,'edges':[[i,i+1,0] for i in range(30)]+[[0,1,5],[30,0,2],[1,29,10]]}]
    elif family=='intervals':extra=[[[i,i+1] for i in range(-64,64)]+[[0,0]],[[10**12,10**12+2],[-10**12,-10**12+1]]]
    elif family=='cache':extra=[{'capacity':3,'accesses':['a','b','c','a','d','b','d','e']*16},{'capacity':0,'accesses':['x']*64}]
    elif family=='windows':extra=[{'values':[4,-1,4,0]*32,'k':17},{'values':list(range(128)),'k':128}]
    elif family=='words':extra=['ÉCOLE e\u0301cole Straße STRASSE 東京; naïve\n' * 24]
    elif family=='json_paths':
        nested={'a/b':[None,False,{},[],{'~':'été'}]}
        for _ in range(20):nested={'':nested}
        extra=[nested]
    elif family=='rate_limit':extra=[{'times':[0]*10+[1]*10+[10]*10+[11]*10+[100],'window':10,'limit':3}]
    elif family=='decimal':extra=[['999999999999999.995','-999999999999999.995','0.0000000001','2.675','2.685']]
    elif family=='logs':extra=[[{'id':str(i%11),'level':['ERROR','INFO','error'][i%3],'service':['api','db','worker'][i%3]} for i in range(96)]]
    elif family=='network':extra=[{'networks':['::1/128','10.0.0.1/31','192.0.2.5/32'],'addresses':['::','::1','::2','10.0.0.0','10.0.0.1','10.0.0.2','192.0.2.5','192.0.2.6','bad']}]
    elif family=='permissions':extra=[list(range(512))]
    elif family=='csv':extra=['account,cents\n"multi\nline",5\n"multi\nline",-7\n"a,b",999999999\n"a,b",-999999999\n']
    else:extra=[['ab'*64,'ba'*64],['é'*64,'e\u0301'*64]]
    # Keep boundary cases and add independently generated ordinary cases.
    from .curriculum import inputs
    return copy.deepcopy(values+inputs(family,rng)+extra)


def oracle_program(task):
    if task.get('split')!='train':raise ValueError('Une référence ne peut être produite pour l’audit')
    from .curriculum import SPECS
    oracle=next(f for family,_,f in SPECS if family==task['family'])
    code=inspect.getsource(oracle).replace('def '+oracle.__name__+'(', 'def solve(',1)
    imports='import copy, csv, heapq, io, ipaddress, json, random, re, unicodedata\nfrom collections import OrderedDict, defaultdict\n'
    return imports+code


MEDIA_TRAIN=[
 ('mechanism','An open brass clockwork bird with overlapping gears, two articulated wings, rivets and fine engraved metal.'),
 ('ceramic','A handmade ceramic teapot, curved hollow spout, one intact loop handle, raised floral relief and subtle glaze.'),
 ('fabric','A pleated red garment draped over a carved wooden chair, visible seams and folds.'),
 ('glass','A transparent laboratory vessel with a narrow neck, nested visible liquid surfaces and embossed measurement marks.'),
 ('organic','An intricately textured pine cone with overlapping scales and a twisted branch.'),
 ('architecture','A miniature brick bridge with three arches, detailed masonry and intact railings.'),
 ('tool','A folding precision tool with distinct hinges, textured grips and aligned metal jaws.'),
 ('plant','A potted flowering plant with thin stems, overlapping leaves, veins and textured soil.'),
 ('animal','A fox curled beside a fallen branch, four paws, layered fur, a visible tail and anatomically coherent ears.'),
 ('scene','A tiny market stall diorama with an awning, three crates, pottery and a readable ground plane.'),
 ('instrument','A detailed string instrument with tuning pegs, thin strings, sound holes and a carved bridge.'),
 ('shell','A spiral seashell with ridges, a continuous lip and a visible hollow opening.')]
MEDIA_AUDIT=[
 ('bicycle','A complete cargo bicycle with two circular wheels, spokes, pedals, chain, cables and an empty front basket.'),
 ('scorpion','An articulated mechanical scorpion with eight legs, two pincers and a segmented curled tail.'),
 ('cathedral','A gothic crystal cathedral with pointed arches, flying buttresses and symmetric stained glass windows.'),
 ('sailing_ship','An antique sailing ship with rigging, separate masts, folded sails and detailed wooden planks.'),
 ('owl','An owl with both wings spread, layered feathers, two talons and a coherent symmetric body.'),
 ('chair','A bentwood rocking chair with four supports, two continuous rockers and a woven seat.'),
 ('helmet','An ornate helmet with a hinged visor, eye slits, engraved metal and an open underside.'),
 ('camera','A vintage camera with concentric lens rings, textured bellows, a shutter button and metal latches.')]

# Every media cycle sees the same structural briefs through several visual
# domains.  The style is part of the prompt and of the audit group, so a
# photorealistic win cannot hide a regression on cartoon or low-poly work.
VISUAL_STYLES=[
 ('photorealistic','photorealistic studio capture with physically plausible PBR materials and natural proportions'),
 ('cartoon','high quality cel-shaded cartoon with clean ink outlines, readable silhouettes and expressive but coherent forms'),
 ('anime','anime-inspired cel shading with controlled linework, stylized proportions and fully separated parts'),
 ('low_poly','intentional low-poly art with clean planar facets, preserved topology and no accidental holes'),
 ('clay','clay stop-motion miniature with soft sculpted surfaces, visible fingerprints and stable proportions'),
 ('comic','inked comic-book illustration rendered as a solid 3D object, bold contour lines and controlled halftone accents')]


def visual_briefs(c):
    rows=[]
    detail=['Neutral studio lighting; preserve all thin parts and occluded connections.',
            'Three-quarter view; emphasize fine surface relief, cavities and distinct materials.',
            'Side view; preserve exact counts, contact points and physically continuous structure.']
    for split,n,pool in [('train',c['train_tasks'],MEDIA_TRAIN),('audit',c['eval_tasks'],MEDIA_AUDIT)]:
        for i in range(n):
            family,prompt=pool[i%len(pool)]
            style,style_prompt=VISUAL_STYLES[i%len(VISUAL_STYLES)]
            rows.append({'id':f'{split}_{family}_{i:03d}','split':split,'family':family,
                         'style':style,'audit_group':f'{family}:{style}',
                         'prompt':prompt+' Style target: '+style_prompt+'. '+detail[(i//len(pool))%3],
                         'difficulty':['structural','fine_detail','occlusion'][(i//len(pool))%3],
                         'suite_version':c.get('curriculum_version','radical-v3'),'origin':'reviewed_complex_brief'})
    return rows


def prepare_visual(c,root,check):
    from pathlib import Path
    from .config import ROOT
    from .storage import atomic_json,file_hash,read_json
    tasks=visual_briefs(c)
    materialize_references(c,tasks,check,training_only=c.get('defer_audit_references',False))
    from .curriculum import validate_tasks
    return validate_tasks(tasks,c)


def materialize_references(c,tasks,check,training_only=False):
    from pathlib import Path
    from .config import ROOT
    from .storage import atomic_json,file_hash,read_json
    if c['module']=='3d':
        import sys
        sys.path.insert(0,str(ROOT/'application/python-services'))
        from flux_reference_synth import build_workflow,post_prompt,poll_history,output_path_from_history,fetch_to
        from PIL import Image
        for task in tasks:
            if training_only and task.get('split')=='audit':continue
            if task.get('image'):continue
            check()
            folder=Path(c['state_dir'])/'radical_references'/digest({'prompt':task['prompt'],'version':c.get('curriculum_version','radical-v3')})
            folder.mkdir(parents=True,exist_ok=True);path=folder/'reference.png'
            saved=read_json(folder/'reference.json',{})
            if path.exists():
                if saved.get('sha256')!=file_hash(path):raise ValueError('Référence de test modifiée')
            else:
                graph=build_workflow(task['prompt'],width=768,height=768,steps=20,
                                     filename_prefix='aurora_rl_refs/'+task['id'],trained_adapter=False)
                job=post_prompt(graph);entry=poll_history(job,timeout_s=1800)
                temporary=path.with_suffix('.pending.png')
                try:
                    fetch_to(output_path_from_history(entry),temporary)
                    with Image.open(temporary) as image:image.verify()
                    temporary.replace(path)
                finally:
                    # A failed reference download must never leave a file that
                    # the next cycle mistakes for a complete asset.
                    temporary.unlink(missing_ok=True)
                atomic_json(folder/'reference.json',{'prompt':task['prompt'],'sha256':file_hash(path),'generator':'official_flux2','comfy_prompt_id':job})
            task.update(image=str(path),reference_sha256=file_hash(path))
    return tasks


def audio_briefs(c):
    train=[
        'Les scientifiques réexaminent attentivement les hypothèses avant de publier leurs résultats.',
        'Une musicienne ajuste délicatement les cordes de son instrument dans une salle silencieuse.',
        'La bibliothécaire classe les manuscrits anciens sans effacer leurs annotations originales.',
        'Ce mécanisme exige une synchronisation précise entre les engrenages et les leviers.',
        'Les promeneurs distinguent les reflets du ciel parmi les branches des saules.',
        'Après chaque expérience, les élèves expliquent leurs observations et leurs incertitudes.',
        'Le pâtissier prépare une crème légère, puis incorpore doucement les noisettes concassées.',
        'Veuillez enregistrer les modifications avant de fermer définitivement cette fenêtre.',
        'Une collection de coquillages révèle des formes spiralées, striées et asymétriques.',
        'Le jardinier protège les jeunes pousses lorsque les températures deviennent fraîches.',
        'La dessinatrice vérifie les perspectives, les proportions et les ombres portées.',
        'Le navigateur corrige son cap dès que le vent change brusquement de direction.']
    audit=[
        ('liaisons','Les anciens étudiants ont échangé avec leurs nouveaux interlocuteurs.'),
        ('homophones','Ces verres verts, vers lesquels il se dirige, appartiennent à sa sœur.'),
        ('questions','Pourquoi distinguer une observation précise d’une simple impression ?'),
        ('technical','La photosynthèse et la phosphorylation oxydative utilisent des mécanismes biochimiques distincts.'),
        ('punctuation','Attention : faites une pause, relisez la consigne, puis poursuivez calmement.'),
        ('rare_words','Le chrysanthème, le rhododendron et l’achillée poussent près du vieux puits.'),
        ('long_context','Lorsque les résultats se contredisent, l’équipe reprend chaque étape du protocole afin d’identifier les conditions qui expliquent réellement cette différence.'),
        ('contrast','Il faut expliquer ce qui a été mesuré, ce qui a été estimé et ce qui reste inconnu.')]
    endings=[' La précision de chaque mot compte.',' Gardez une diction naturelle et régulière.',' Évitez de confondre les termes employés.']
    prosody=[('neutral','intonation naturelle, articulation nette et débit régulier'),
             ('warm','intonation chaleureuse, pauses respirées et articulation nette'),
             ('technical','diction technique précise, accentuation des termes importants et débit stable'),
             ('dramatic','intonation expressive mais intelligible, sans exagérer les voyelles'),
             ('calm','voix calme, respiration régulière et transitions douces'),
             ('broadcast','voix de présentation claire, dynamique contrôlée et consonnes distinctes')]
    result=[]
    for split,n in [('train',c['train_tasks']),('audit',c['eval_tasks'])]:
        for i in range(n):
            family,text=(f'train_topic_{i%len(train)}',train[i%len(train)]) if split=='train' else audit[i%len(audit)]
            style,style_prompt=prosody[i%len(prosody)]
            result.append({'id':f'{split}_{family}_{i:03d}','family':family,'split':split,
                           'style':style,'audit_group':f'{family}:{style}',
                           'prompt':text+endings[(i//(len(train) if split=='train' else len(audit)))%3]+' Style vocal: '+style_prompt+'.',
                           'language':'fr','difficulty':'long_phonetic_detail','suite_version':c.get('curriculum_version','radical-v3')})
    return result
