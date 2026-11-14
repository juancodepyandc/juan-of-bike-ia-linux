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

TRAIN_TEMPORAL_STYLES = STYLE_DIRECTIVES + [
    ('biomechanical_mocap', 'high-precision optical motion-capture biomechanics with zero foot skate and exact pelvic weight transfer'),
    ('heavy_armored_inertia', 'high-mass armored locomotion with deep knee flexion, delayed momentum follow-through and grounded impacts'),
    ('acrobatic_wushu_fluid', 'fluid martial wushu kinematics with whip-like spinal torque, crisp snap-holds and balanced single-foot landings'),
    ('robotic_trapezoidal_servo', 'precision industrial harmonic-drive servo kinematics with S-curve jerk-limited acceleration profiles'),
    ('underwater_hydrodynamic_drag', 'submerged hydrodynamic motion with viscous fluid resistance, delayed limb recovery and buoyancy suspension'),
    ('low_gravity_lunar_bound', '0.16g lunar ballistic locomotion with extended flight phase, slow-motion apex and deep shock-absorbing landing'),
    ('stealth_tactical_crouch', 'low-center-of-mass tactical infiltration gait with silent heel-to-toe roll and stabilized upper torso'),
    ('contemporaneous_dance_arcs', 'expressive contemporary dance choreography with spiral torso counter-rotation and continuous momentum flow'),
    ('stop_motion_12fps_puppet', 'hand-animated 12fps armatures with tactile pose-to-pose holds and crisp silhouette changes'),
    ('ukiyo_e_kabuki_mie', 'dramatic Japanese kabuki stage timing culminating in a frozen crystalline mie dynamic equilibrium pose'),
    ('clockwork_automaton_geared', '18th-century mechanical automaton kinematics driven by cam-and-lever sinusoidal phase couplings'),
    ('asymmetrical_heavy_load', 'encumbered biomechanical gait compensating for an off-center 40kg load with lateral spinal lean'),
    ('ice_low_friction_recovery', 'low-friction ice surface locomotion with micro-corrective arm windmilling and ankle stabilization'),
    ('high_wind_aerodynamic_lean', 'forward-leaning locomotion bracing against a 90 km/h headwind with shielded head posture'),
    ('zero_g_microgravity_twist', 'conservation-of-angular-momentum cat-righting reflex in microgravity without external ground impulse'),
    ('elastic_squash_stretch_rig', 'classic golden-age animation anticipation, overshoot and damped harmonic settle without bone-length distortion'),
    ('elderly_cane_assisted_gait', 'careful three-point stability gait with shortened stride length and deliberate weight shifting'),
    ('explosive_plyometric_burst', 'maximal fast-twitch plyometric triple-extension from deep crouch to full vertical reach'),
]

EXTRA_VIDEO_TRAIN = [
    ('train','pendulum','A brass pendulum swings repeatedly, the support remains stationary.'),
    ('train','rotor','A wind turbine rotates continuously; three separate blades remain attached.'),
    ('train','stream','Water pours into a glass; ripples and the rising liquid surface remain coherent.'),
    ('train','tourbillon_gears','A macro mechanical tourbillon cage rotates smoothly while the escapement wheel ticks in phase.'),
    ('train','ferrofluid_peaks','A magnetic ferrofluid dome forms symmetric harmonic spikes under a rotating neodymium field.'),
    ('train','silk_vortex','An iridescent silk ribbon spirals in a laminar air current without tearing or self-intersecting.'),
    ('train','glass_caustics','Sunlight refracts through a rotating dichromatic Murano glass prism onto a stone table.'),
    ('train','molten_gold_kintsugi','Liquid 24-karat gold flows along a porcelain fracture seam and solidifies with specular sheen.'),
    ('train','bridge_arch_load','A parabolic steel arch bridge carries a moving tram while river ripples reflect the trusses.'),
    ('train','origami_deploy','A rigid-origami Miura-ori solar array unfolds smoothly from compact stack to flat plane.'),
    ('train','biolum_jellyfish','A translucent deep-sea jellyfish pulses its bell rhythmically with trailing bioluminescent tentacles.'),
    ('train','lathe_chip_curl','A carbide tool cuts a rotating brass cylinder on a precision lathe, forming a continuous spiral chip.'),
    ('train','smoke_vortex_ring','A toroidal smoke ring travels left to right through still air while preserving its vortex core.'),
    ('train','rain_lotus_hydrophobic','Water droplets bead and roll off a superhydrophobic lotus leaf, merging on contact.'),
    ('train','newton_cradle_5ball','Five chrome spheres in a Newton cradle transfer momentum through elastic collisions.'),
    ('train','aurora_magnetosphere','Charged green and violet aurora curtains undulate above a snow-covered observatory dome.'),
    ('train','ceramic_wheel_throw','Wet clay rises symmetrically into a slender vase on a spinning potter wheel under steady hands.'),
    ('train','steam_piston_valve','A polished brass Walschaerts steam locomotive linkage reciprocates with synchronized valve gear.'),
    ('train','chladni_sand_resonance','Fine quartz sand on a vibrating brass plate migrates into a symmetric Chladni nodal pattern.'),
    ('train','kelp_underwater_swell','Giant underwater kelp fronds sway in phase with a long-period ocean swell and sunbeams.'),
]

EXTRA_ANIMATION_TRAIN = [
    ('train','turn','A person turns around slowly, shifting weight naturally between both feet.','travel'),
    ('train','reach','A person reaches up with the left hand, pauses, and lowers the arm.','hands'),
    ('train','kneel','A person lowers onto one knee with controlled balance, then rises.','vertical'),
    ('train','stair_ascent','A person climbs four imaginary steps with exact foot plant heights and knee drive.','vertical'),
    ('train','heavy_box_lift','A person squats with straight back, grips a heavy crate with both hands, lifts to waist height and sets it down.','vertical'),
    ('train','fencing_lunge','A fencer executes an explosive forward lunge with right arm extension and recovers to en-garde stance.','travel'),
    ('train','spinning_hook_kick','A martial artist pivots on the planted support foot, executes a 360-degree spinning hook kick and lands balanced.','travel'),
    ('train','parkour_kong_vault','A traceur approaches an obstacle, plants both hands, tucks the knees through and lands in a stride.','travel'),
    ('train','orchestra_conducting','A conductor leads a 4/4 crescendo with expressive right-hand baton arcs and left-hand phrasing cues.','hands'),
    ('train','blacksmith_anvil_strike','A blacksmith raises a two-handed hammer overhead, strikes an anvil with rebound and resets.','hands'),
    ('train','archery_draw_release','An archer nocks an arrow, draws the bowstring to anchor point with scapular tension, aims and releases.','hands'),
    ('train','stealth_pivot_peek','A person crouches low, advances three silent steps, peeks around a corner and pulls back.','travel'),
    ('train','balance_beam_walk','A gymnast walks along a narrow beam with arms extended laterally for micro-balance corrections.','travel'),
    ('train','box_jump_soft_land','An athlete swings arms back, jumps onto a raised platform, absorbs impact in a squat and stands tall.','vertical'),
    ('train','violin_solo_bowing','A violinist holds the instrument under the chin while the right arm executes rapid spiccato and long legato bow strokes.','hands'),
    ('train','rope_pull_hand_over_hand','A person pulls a heavy rope horizontally hand-over-hand while bracing with a wide staggered stance.','hands'),
    ('train','tai_chi_cloud_hands','A practitioner shifts weight smoothly between left and right legs while tracing circular cloud-hands trajectories.','travel'),
    ('train','slip_and_recover','A walking person experiences a brief right-foot slip, counter-rotates the arms and regains stable upright posture.','travel'),
    ('train','overhead_medicine_slam','An athlete lifts a heavy ball overhead onto tiptoes and slams it forcefully toward the ground.','vertical'),
    ('train','figure_skate_spiral','A figure skater glides forward on one outside edge while extending the free leg into a horizontal arabesque.','travel'),
]


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
    video_train=VIDEO[:3]+EXTRA_VIDEO_TRAIN
    animation_train=ANIMATION[:3]+EXTRA_ANIMATION_TRAIN
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
        style_pool = TRAIN_TEMPORAL_STYLES if (split == 'train' and c.get('all_regime_styles', True)) else STYLE_DIRECTIVES
        for i in range(n):
            _,family,prompt,*motion=pool[i%len(pool)]
            style,style_prompt=style_pool[i%len(style_pool)]
            tasks.append({'id':f'{split}_{family}_{i:03d}','family':family,'split':split,
                          'style':style,'audit_group':f'{family}:{style}',
                          'prompt':prompt+' Style target: '+style_prompt+'. '+details[(i//len(pool))%3],
                          'motion':motion[0] if motion else 'visible','duration':c['generation']['duration'],
                          'frames':c['generation']['frames'],'difficulty':['continuity','detail','contacts'][(i//len(pool))%3],
                          'suite_version':c.get('curriculum_version','radical-v3'),'origin':'reviewed_temporal_brief'})
    validate_tasks(tasks,c)
    return tasks
