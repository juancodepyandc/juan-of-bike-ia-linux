"""Fixed, disjoint generation briefs; no audit feedback enters optimization."""
from .curriculum import validate_tasks

VIDEO = [
    ('train','water','A small waterfall flows over dark rocks, steady locked camera.'),
    ('train','bird','A sparrow flaps its wings and flies from a wooden fence, daylight.'),
    ('train','cloth','A red flag waves slowly in the wind against a blue sky.'),
    ('audit','bicycle','A cyclist rides from left to right along a quiet street, locked camera.'),
    ('audit','horse','A brown horse walks across a grassy field, full body side view.'),
    ('audit','boat','A small sailing boat moves across a calm lake with gentle ripples.'),
    ('audit','candle','A candle flame flickers gently in a dark room, close view.'),
    ('audit','ball','A red ball bounces on a wooden floor, static camera.'),
    ('audit','train','A toy train moves along a curved track in a bright room.'),
    ('audit','fish','A goldfish swims through clear water with aquatic plants.'),
    ('audit','cloud','White clouds drift over green hills in soft daylight.'),
]
ANIMATION = [
    ('train','walk','A person walks forward naturally.', 'travel'),
    ('train','wave','A person stands and waves with the right hand.', 'hands'),
    ('train','squat','A person slowly squats down and stands up.', 'vertical'),
    ('audit','run','A person runs forward.', 'travel'),
    ('audit','jump','A person jumps upward and lands on both feet.', 'vertical'),
    ('audit','clap','A person stands and claps both hands.', 'hands'),
    ('audit','sidestep','A person takes several steps sideways.', 'travel'),
    ('audit','punch','A person throws alternating punches in front of the body.', 'hands'),
    ('audit','bend','A person bends down to pick an object up and rises.', 'vertical'),
    ('audit','backwards','A person walks backwards carefully.', 'travel'),
    ('audit','stretch','A person raises both arms overhead and lowers them.', 'hands'),
]

STYLE_DIRECTIVES = [
    ('realistic', 'natural physically grounded motion with realistic lighting and proportions'),
    ('cartoon', 'readable cel-shaded cartoon motion with clear silhouettes and expressive timing'),
    ('anime', 'anime-inspired motion with deliberate poses, clean arcs and controlled anticipation'),
    ('stylized', 'stylized low-poly motion with stable topology and no shape popping'),
    ('clay', 'clay stop-motion look with tangible sculpted surfaces and intentionally stepped timing'),
    ('comic', 'comic-book staging with strong poses, clear contour readability and coherent contacts')]


def build_tasks(c):
    if c.get('curriculum_version') in {'radical-v2','radical-v3'}:return complex_tasks(c)
    source=VIDEO if c['module']=='video' else ANIMATION
    tasks=[]
    for split,n in [('train',c['train_tasks']),('audit',c['eval_tasks'])]:
        pool=[t for t in source if t[0]==split]
        if n>len(pool):
            raise ValueError(f"Curriculum {c['module']} : {len(pool)} sujets {split} disponibles ; ajouter des briefs distincts avant d'augmenter le profil.")
        for entry in pool[:n]:
            _,family,prompt,*motion=entry
            tasks.append({'id':split+'_'+family,'family':family,'split':split,'prompt':prompt,
                          'origin':'synthetic_temporal_brief','motion':motion[0] if motion else 'visible',
                          'frames':c['generation']['frames'], 'duration':c['generation']['duration']})
    validate_tasks(tasks,c)
    return tasks


def complex_tasks(c):
    video_train=VIDEO[:3]+[
        ('train','pendulum','A brass pendulum swings repeatedly, the support remains stationary.'),
        ('train','rotor','A wind turbine rotates continuously; three separate blades remain attached.'),
        ('train','stream','Water pours into a glass; ripples and the rising liquid surface remain coherent.')]
    animation_train=ANIMATION[:3]+[
        ('train','turn','A person turns around slowly, shifting weight naturally between both feet.','travel'),
        ('train','reach','A person reaches up with the left hand, pauses, and lowers the arm.','hands'),
        ('train','kneel','A person lowers onto one knee with controlled balance, then rises.','vertical')]
    train=video_train if c['module']=='video' else animation_train
    audit=VIDEO[3:] if c['module']=='video' else ANIMATION[3:]
    details=(['Maintain identity, shape and direction in every frame; locked wide camera.',
              'Preserve occluded parts, shadows and material details through the motion.',
              'Show consistent contacts, smooth acceleration and uninterrupted object structure.']
             if c['module']=='video' else
             ['Use natural acceleration and a stable torso; avoid foot sliding.',
              'Maintain balance, joint lengths and continuous shoulder and hip motion.',
              'Start and finish smoothly; preserve ground contact and anatomical joint limits.'])
    tasks=[]
    for split,n,pool in [('train',c['train_tasks'],train),('audit',c['eval_tasks'],audit)]:
        for i in range(n):
            _,family,prompt,*motion=pool[i%len(pool)]
            style,style_prompt=STYLE_DIRECTIVES[i%len(STYLE_DIRECTIVES)]
            tasks.append({'id':f'{split}_{family}_{i:03d}','family':family,'split':split,
                          'style':style,'audit_group':f'{family}:{style}',
                          'prompt':prompt+' Style target: '+style_prompt+'. '+details[(i//len(pool))%3],
                          'motion':motion[0] if motion else 'visible','duration':c['generation']['duration'],
                          'frames':c['generation']['frames'],'difficulty':['continuity','detail','contacts'][(i//len(pool))%3],
                          'suite_version':c.get('curriculum_version','radical-v3'),'origin':'reviewed_temporal_brief'})
    validate_tasks(tasks,c)
    return tasks
