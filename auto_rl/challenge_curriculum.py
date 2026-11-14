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
    elif family=='business_waterfall':
        extra=[
            {'gross_cents': 0, 'direct_cost_cents': 5000, 'cac_cents': 2000, 'fixed_cost_cents': 10000, 'reserve_yield_bps': 450, 'dso_lag_cents': 0, 'tax_bps': 2500},
            {'gross_cents': 10000000, 'direct_cost_cents': 1500000, 'cac_cents': 800000, 'fixed_cost_cents': 500000, 'reserve_yield_bps': 375, 'dso_lag_cents': 2500000, 'tax_bps': 3000},
            {'gross_cents': 500000, 'direct_cost_cents': 100000, 'cac_cents': 50000, 'fixed_cost_cents': 50000, 'reserve_yield_bps': 400, 'dso_lag_cents': 50000, 'tax_bps': 2500},
        ]
    elif family=='cyber_alloc_guard':
        extra=[
            {'count': 0xFFFFFFFF, 'stride': 1, 'header': 0, 'max_bytes': 0xFFFFFFFF},
            {'count': 0x10000, 'stride': 0x10000, 'header': 0, 'max_bytes': 0xFFFFFFFF},
            {'count': 255, 'stride': 16, 'header': 1, 'max_bytes': 4096},
            {'count': 255, 'stride': 16, 'header': 1, 'max_bytes': 4095},
        ]
    elif family=='os_vfs_canonical':
        extra=[
            {'path': '/a/b/c/../../../../root/./secret//file'},
            {'path': '////'},
            {'path': './.././../etc/./shadow'},
        ]
    elif family=='os_aging_scheduler':
        extra=[
            {'aging_factor': 10, 'processes': [
                {'pid': 99 - i, 'base_priority': 1, 'wait_ticks': i} for i in range(32)
            ]},
            {'aging_factor': 0, 'processes': [
                {'pid': i, 'base_priority': 50, 'wait_ticks': i * 10} for i in range(16, 0, -1)
            ]},
        ]
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
 ('shell','A spiral seashell with ridges, a continuous lip and a visible hollow opening.'),
 ('arch_villa','A three-story contemporary architectural villa with cantilevered reinforced concrete slabs, load-bearing columns, spiral staircase and structural glass facade.'),
 ('cad_turret','An articulated robotic turret assembly with NEMA17 motor bay, planetary gear ring, LiDAR optical dome and M3 bolted inspection hatches.'),
 ('horology','An open skeleton tourbillon pocket watch movement with concentric balance wheel, escapement anchor, ruby bearings and guilloche bridges.'),
 ('abyssal_bio','A deep-sea bioluminescent cephalopod with translucent mantle, eight distinct curled tentacles, internal photophores and fin membranes.')]
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

# Training covers 646 styles across 4 epistemic regimes:
# - 6 Known Canonical styles (VISUAL_STYLES)
# - 160 Rare / Under-Trained Long-Tail Optical, Cultural & Architectural styles (20 rare media × 8 optical micro-regimes)
# - 480 Unknown / Hybrid Out-of-Distribution Physics-Composed styles (24 structural matrices × 20 exotic secondary physics)
_RARE_OPTICAL_MEDIA = [
    ("kintsugi_24k_porcelain", "glazed white porcelain with dipole subsurface scattering and 24-karat gold kintsugi veins"),
    ("volcanic_black_opal", "volcanic black opal with thin-film Bragg diffraction fire and obsidian matrix"),
    ("dichromatic_murano_glass", "dichromatic Murano glass with Cauchy wavelength dispersion and internal caustics"),
    ("ukiyo_e_carved_keyaki", "carved Japanese keyaki woodblock ukiyo-e relief with mineral indigo pigments"),
    ("damascene_wootz_gold", "acid-etched Wootz Damascus steel with wavy carbide bands and 24k gold koftgari inlay"),
    ("brutalist_concrete_corten", "board-formed architectural brutalist concrete with weathered Corten steel trusses"),
    ("cloisonne_guilloche_enamel", "grand-feu translucent cloisonne enamel over engine-turned silver guilloche"),
    ("bioluminescent_abyssal_chitin", "translucent deep-sea chitin with subsurface turquoise bioluminescence"),
    ("pietra_dura_lapis_inlay", "Florentine pietra dura inlaid marble with lapis lazuli, malachite and porphyry"),
    ("mokume_gane_laminate", "Japanese mokume-gane forged mixed-metal wood-grain laminate of copper, shakudo and silver"),
    ("urushi_maki_e_lacquer", "mirror-polished black Urushi lacquer with sprinkled maki-e gold and platinum powder"),
    ("tiffany_favrile_stained_glass", "iridescent Favrile leaded stained glass with soldered copper-foil botanical seams"),
    ("anodized_interference_titanium", "electro-anodized grade-5 titanium with thin-oxide interference rainbow spectrum"),
    ("imperial_celadon_nephrite", "carved imperial celadon nephrite jade with waxy subsurface translucency and fine relief"),
    ("zellige_carved_muqarnas", "hand-cut glazed Moroccan zellige tilework with carved cedar and stucco muqarnas"),
    ("rayleigh_silica_aerogel", "ultralight nanoporous silica aerogel with opalescent Rayleigh blue scattering"),
    ("limoges_champleve_enamel", "carved bronze champleve cells filled with vitreous cobalt and ruby kiln-fired enamel"),
    ("raden_mother_of_pearl", "iridescent abalone nacre raden inlay set into dark carved ebony wood"),
    ("verdigris_foundry_bronze", "lost-wax cast architectural bronze with oxidized turquoise verdigris patina in cavities"),
    ("twill_carbon_kevlar_weave", "aerospace 2x2 twill carbon-aramid hybrid weave under high-gloss automotive clearcoat"),
]

_OPTICAL_SURFACE_REGIMES = [
    ("anisotropic_ggx", "anisotropic micro-brushed GGX specular lobes with directional tangent highlights"),
    ("dipole_sss_translucent", "deep dipole subsurface scattering with grazing-angle Fresnel rim glow"),
    ("bragg_thin_film", "nanometric thin-film interference shifting hue across viewing angles"),
    ("cauchy_prismatic", "high-Abbe Cauchy chromatic dispersion with crisp internal refraction"),
    ("acid_micro_relief", "high-frequency Scharr-Sobel micro-etched relief and cavity ambient occlusion"),
    ("faceted_planimetric", "chiseled planimetric facets with razor-sharp dihedral edges and zero smoothing blur"),
    ("mirror_clearcoat_dual", "dual-layer dielectric mirror clearcoat over rough metallic substrate"),
    ("archaeological_patina", "selective cavity oxidation with polished high-contact wear ridges"),
]

_HYBRID_PRIMARY_MATRICES = [
    ("aerogel_matrix", "translucent Rayleigh-scattering silica aerogel structural ribs"),
    ("widmanstatten_meteorite", "octahedral etched Gibeon iron-nickel meteorite lattice"),
    ("piezo_bismuth_hopper", "stepped iridescent hopper-crystal bismuth terraces"),
    ("basalt_columnar_hex", "hexagonal fractured volcanic basalt prisms"),
    ("mycelium_biopolymer", "grown fibrous acoustic mycelium biopolymer shell"),
    ("sintered_inconel_gyroid", "laser-sintered Inconel 718 minimal-surface TPMS gyroid lattice"),
    ("yakisugi_charred_cedar", "kiln-charred alligator-skin Yakisugi cedar timber"),
    ("borosilicate_lab_coil", "blown scientific borosilicate glass condenser tubing"),
    ("nitinol_shape_memory_mesh", "woven superelastic Nitinol wire-mesh actuator skin"),
    ("travertine_roman_tufa", "porous Roman travertine limestone with natural calcitic cavities"),
    ("silicon_wafer_photolith", "nanometer photolithography etched monocrystalline silicon wafer"),
    ("vulcanized_ebonite_brass", "turn-of-the-century vulcanized black ebonite and knurled instrument brass"),
    ("bone_china_lithophane", "ultra-thin translucent porcelain lithophane relief"),
    ("electroformed_dendritic_copper", "fractal electroformed dendritic copper growth"),
    ("dichroic_boron_nitride", "hexagonal boron nitride ceramic with vacuum-deposited dichroic prism coating"),
    ("fossil_ammonite_pyrite", "pyritized iridescent chambered ammonite fossil matrix"),
    ("woven_basalt_fiber", "golden-brown volcanic basalt fiber composite weave"),
    ("cast_slag_vitreous", "industrial vitreous blue-green smelted iron slag stone"),
    ("carved_boxwood_netsuke", "micro-carved dense boxwood netsuke sculpture with natural satin oil finish"),
    ("forged_beryllium_copper", "non-sparking brushed beryllium-copper alloy precision housing"),
    ("crystalline_osmium_ruthenium", "ultra-dense crystalline platinum-group osmium-ruthenium alloy"),
    ("folded_origami_tyvek", "rigid-origami Miura-ori folded fibrous Tyvek membrane"),
    ("acoustic_metamaterial_labyrinth", "sub-wavelength Helmholtz labyrinthine acoustic metamaterial"),
    ("glacial_firn_blue_ice", "compressed high-pressure glacial blue ice with trapped micro-bubbles"),
]

_HYBRID_SECONDARY_ACCENTS = [
    ("amber_encapsulation", "encapsulating fossilized Baltic amber optical conduits"),
    ("gold_24k_kintsugi", "joined by 24-karat brushed gold kintsugi structural seams"),
    ("superconducting_niobium_coils", "threaded with cryogenic niobium-titanium inductive coils"),
    ("emerald_beryl_prisms", "set with hexagonal chromium-doped emerald beryl crystal joints"),
    ("bioluminescent_luciferin_veins", "pulsing with subsurface abyssal luciferin vascular channels"),
    ("verdigris_copper_rivets", "fastened with hand-hammered verdigris patinated copper rivets"),
    ("opalized_fluorite_nodes", "anchored by UV-fluorescent cubic purple fluorite nodes"),
    ("damascus_wootz_flexures", "articulated via compliant Wootz Damascus steel flexure hinges"),
    ("cloisonne_enamel_filigree", "bordered by silver wire cloisonne grand-feu enamel filigree"),
    ("tourmaline_piezo_bridges", "bridged by polychrome watermelon tourmaline tension rods"),
    ("anodized_niobium_scales", "armored with interference-anodized overlapping niobium scales"),
    ("obsidian_conchoidal_blades", "edged with knapped conchoidal-fracture volcanic obsidian"),
    ("nacre_abalone_lamellae", "lined with brick-and-mortar aragonite nacre abalone lamellae"),
    ("corten_weathered_gussets", "reinforced by oxidized Corten steel structural gusset plates"),
    ("sapphire_corundum_bearings", "pivoting on synthetic monocrystalline ruby-sapphire bearings"),
    ("mokume_gane_collars", "clamped with twisted mokume-gane copper-silver locking collars"),
    ("urushi_gold_maki_e_seals", "sealed with black Urushi lacquer and maki-e gold dust gaskets"),
    ("radium_phosphor_dials", "inlaid with vintagehorological green zinc-sulfide phosphor markers"),
    ("zellige_geometric_tesserae", "tessellated with interlocking glazed zellige star polygons"),
    ("ferrofluid_magnetic_spikes", "crowned with frozen neodymium-stabilized ferrofluid harmonic peaks"),
]


def build_exhaustive_style_taxonomy():
    styles = list(VISUAL_STYLES)
    for m_key, m_desc in _RARE_OPTICAL_MEDIA:
        for o_key, o_desc in _OPTICAL_SURFACE_REGIMES:
            styles.append((f"rare_{m_key}_{o_key}", f"{m_desc}, rendered with {o_desc}"))
    for p_key, p_desc in _HYBRID_PRIMARY_MATRICES:
        for s_key, s_desc in _HYBRID_SECONDARY_ACCENTS:
            styles.append((
                f"ood_hybrid_{p_key}_{s_key}",
                f"unknown out-of-distribution hybrid material combining {p_desc} {s_desc}",
            ))
    return styles


TRAIN_ALL_REGIME_STYLES = build_exhaustive_style_taxonomy()


def load_trellis_500k_curriculum(limit=48, seed=42):
    """Charge des sujets structurels haute esthétique depuis `modele/renforce/3d/datasets/TRELLIS-500K/` (504 006 objets)."""
    import csv
    import json
    import random
    from pathlib import Path
    from .config import ROOT

    pack_dir = ROOT / "modele" / "renforce" / "3d" / "datasets" / "TRELLIS-500K"
    if not pack_dir.is_dir():
        return []
    audit_forbidden = {"bicycle", "bike", "scorpion", "cathedral", "sailing ship", "ship", "owl", "rocking chair", "chair", "helmet", "camera"}
    candidates = []
    for csv_name, fam_tag in [
        ("Toys4k.csv", "trellis500k_toys4k"),
        ("ABO.csv", "trellis500k_abo"),
        ("3D-FUTURE.csv", "trellis500k_future"),
        ("HSSD.csv", "trellis500k_hssd"),
    ]:
        csv_path = pack_dir / csv_name
        if not csv_path.is_file():
            continue
        try:
            with csv_path.open("r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    if idx > 1500:
                        break
                    try:
                        score = float(row.get("aesthetic_score") or 0.0)
                    except ValueError:
                        continue
                    if score < 6.0:
                        continue
                    raw_caps = row.get("captions") or "[]"
                    try:
                        caps = json.loads(raw_caps)
                    except Exception:
                        continue
                    if not caps or not isinstance(caps, list):
                        continue
                    cap = str(caps[0]).strip()
                    if len(cap) < 60 or len(cap) > 280:
                        continue
                    lower = cap.lower()
                    if any(word in lower for word in audit_forbidden):
                        continue
                    candidates.append((fam_tag, cap, score))
        except OSError:
            continue
    candidates.sort(key=lambda x: (-x[2], x[1]))
    rng = random.Random(seed)
    top_pool = candidates[: max(limit * 4, 120)]
    rng.shuffle(top_pool)
    return [(fam, cap) for fam, cap, _ in top_pool[:limit]]


def visual_briefs(c):
    rows=[]
    detail=['Neutral studio lighting; preserve all thin parts and occluded connections.',
            'Three-quarter view; emphasize fine surface relief, cavities and distinct materials.',
            'Side view; preserve exact counts, contact points and physically continuous structure.']
    train_pool = list(MEDIA_TRAIN)
    if c.get('use_trellis_500k_pack') or int(c.get('train_tasks', 12)) > len(MEDIA_TRAIN):
        extra_500k = load_trellis_500k_curriculum(limit=max(24, int(c.get('train_tasks', 12))), seed=int(c.get('seed', 42)))
        if extra_500k:
            if c.get('use_trellis_500k_pack'):
                # Mix core verified briefs with TRELLIS-500K high-aesthetic briefs
                train_pool = train_pool[:8] + extra_500k
            else:
                train_pool = train_pool + extra_500k
    for split,n,pool in [('train',c['train_tasks'],train_pool),('audit',c['eval_tasks'],MEDIA_AUDIT)]:
        style_pool = TRAIN_ALL_REGIME_STYLES if (split == 'train' and c.get('all_regime_styles')) else VISUAL_STYLES
        for i in range(n):
            family,prompt=pool[i%len(pool)]
            style,style_prompt=style_pool[i%len(style_pool)]
            origin = 'trellis_500k_pack' if str(family).startswith('trellis500k_') else 'reviewed_complex_brief'
            rows.append({'id':f'{split}_{family}_{i:03d}','split':split,'family':family,
                         'style':style,'audit_group':f'{family}:{style}',
                         'prompt':prompt+' Style target: '+style_prompt+'. '+detail[(i//len(pool))%3],
                         'difficulty':['structural','fine_detail','occlusion'][(i//len(pool))%3],
                         'suite_version':c.get('curriculum_version','radical-v3'),'origin':origin})
    return rows



def prepare_visual(c,root,check,progress=None):
    from pathlib import Path
    from .config import ROOT
    from .storage import atomic_json,file_hash,read_json
    tasks=visual_briefs(c)
    materialize_references(c,tasks,check,training_only=c.get('defer_audit_references',False),progress=progress)
    from .curriculum import validate_tasks
    return validate_tasks(tasks,c)


def materialize_references(c,tasks,check,training_only=False,progress=None):
    from pathlib import Path
    from .config import ROOT
    from .storage import atomic_json,file_hash,read_json
    if c['module']=='3d':
        import sys
        sys.path.insert(0,str(ROOT/'application/python-services'))
        from flux_reference_synth import build_workflow,post_prompt,poll_history,output_path_from_history,fetch_to
        from PIL import Image
        for task in tasks:
            if task.get('image') and not Path(task['image']).exists():
                candidate_ref = Path(c['state_dir'])/'radical_references'/digest({'prompt':task['prompt'],'version':c.get('curriculum_version','radical-v3')})/'reference.png'
                if candidate_ref.exists():
                    task['image'] = str(candidate_ref)
                else:
                    task.pop('image', None)
        wanted=[t for t in tasks if not (training_only and t.get('split')=='audit')]
        pending=[]
        for task in wanted:
            if task.get('image') and Path(task['image']).exists():continue
            folder=Path(c['state_dir'])/'radical_references'/digest({'prompt':task['prompt'],'version':c.get('curriculum_version','radical-v3')})
            if (folder/'reference.png').exists():continue
            pending.append(task)
        # 27/09: le chien de garde (`auto_rl/control.py:339`) tue l'etape au
        # bout de `local_step_timeout_seconds` (1200 s) en mesurant
        # `time.time() - step_started_at`. Or `Status.update` ne rafraichit
        # `step_started_at` que si le MESSAGE change (storage.py:105) : la
        # synthese de 30 references FLUX.2 emet le meme message du debut a la
        # fin, donc un travail SAIN et long etait tue a 1200 s. Mesure: le
        # run 3d-20260915-064158 a ete SIGINT a 1200.2 s, a 2 %, GPU a 52 %,
        # en train de rendre les 30 references manquantes, sans aucun mesh
        # produit. On rapporte donc l'avancement reel, ce qui a la fois
        # rafraichit le chrono du chien de garde et rend la phase visible.
        if pending and progress:
            progress(len(pending),len(wanted),'prepare')
        for task in tasks:
            if training_only and task.get('split')=='audit':continue
            if task.get('image') and Path(task['image']).exists():continue
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
            if progress:
                done=sum(1 for t in wanted if t.get('image'))
                progress(done,len(wanted),'prepare')
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
