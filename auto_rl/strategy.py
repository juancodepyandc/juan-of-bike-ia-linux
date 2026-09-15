"""Stricter research profile, within the real Kaggle and local engine limits."""
from .config import TEXT_MODULES


RECIPES = {
    '3d': {
        'trainer': 'flow_matching_preference_dpo',
        'data': 'TRELLIS-500K-compatible structural briefs plus measured hard-negative replay',
        'reward_stack': ['watertight/topology', 'multi-view geometry', 'prompt/style alignment', 'worst-view guard'],
        'selection': 'two Kaggle trials with independent validation subjects; strict zero-regression audit'},
    'image': {
        'trainer': 'active_pairwise_low_rank_surrogate_es',
        'data': 'photorealistic, cartoon, anime, low-poly, clay and comic prompts',
        'reward_stack': ['CLIP alignment', 'aesthetic score', 'contrast/edge sanity', 'extreme-pixel guard'],
        'selection': 'coordinate search around measured candidates with PC re-audit'},
    'video': {
        'trainer': 'active_temporal_surrogate_es',
        'data': 'motion, identity, material and stylized temporal briefs',
        'reward_stack': ['CLIP per sampled frame', 'optical-flow continuity', 'warp error', 'flicker guard'],
        'selection': 'measured candidate proposals, then held-out multi-seed audit'},
    'animation': {
        'trainer': 'active_kinematic_surrogate_es',
        'data': 'action families with realistic, cartoon, anime, low-poly, clay and comic timing',
        'reward_stack': ['action proxy', 'bone-length stability', 'jerk', 'foot contacts/ground penetration'],
        'selection': 'bounded weight subspace search with held-out kinematic audit'},
    'audio': {
        'trainer': 'measured_evolution_with_asr_gate',
        'data': 'French phonetic edge cases with six prosody targets',
        'reward_stack': ['WER', 'clipping', 'RMS', 'dynamic-range proxy'],
        'selection': 'held-out sentences and deterministic seeds'},
    'code': {
        'trainer': 'oracle_supervised_dpo',
        'data': 'disjoint algorithm families, adversarial boundaries and Unicode/numerical cases',
        'reward_stack': ['sandbox execution', 'independent oracle cases', 'failure replay'],
        'selection': 'exact pass gate with parent/base regression checks'},
    'conversation': {
        'trainer': 'structured_oracle_dpo',
        'data': 'multi-input structured reasoning with exact JSON verification',
        'reward_stack': ['schema validity', 'exact values', 'complete answer count'],
        'selection': 'held-out problem families and zero-regression gate'},
    'cyber': {
        'trainer': 'sandboxed_agent_preference_dpo',
        'data': 'safe offline command/task simulations with adversarial edge cases',
        'reward_stack': ['sandbox exit status', 'expected output', 'failure replay'],
        'selection': 'no real host/network side effects; exact held-out checks'},
    'cowork': {
        'trainer': 'sandboxed_agent_preference_dpo',
        'data': 'multi-step tool plans with explicit completion contracts',
        'reward_stack': ['sandbox execution', 'expected output', 'failure replay'],
        'selection': 'held-out workflows and zero-regression gate'},
    'learning': {
        'trainer': 'structured_oracle_dpo',
        'data': 'progressive exercises with cross-checks and misconception replay',
        'reward_stack': ['exact result', 'verification field', 'difficulty progression'],
        'selection': 'held-out skills and zero-regression gate'}}


def apply(c):
    c.update(curriculum_version='radical-v3',strict_audit=True,audit_by_family=True,
             regression_tolerance=0.0,eval_tasks=24,eval_seeds=[41,137,271,911],
             auto_min_tasks=8,max_hours=24,training_start=c.get('training_start','best'),
             reference_policy='parent',coordinate_search=True,
             failure_replay_tasks=6,
             train_learning_rate=.00002,early_stopping_patience=5,
             kaggle_parallel_trials=True,minimum_preference_pairs=8,
             minimum_validation_pairs=2,minimum_training_pairs=2,
             # Kaggle's dual T4 is the largest accelerator available to this
             # account. A radical cycle may consume the selected session quota;
             # the UI still lets the user choose a shorter explicit budget.
             kaggle_accelerator='gpu_t4_x2',kaggle_max_session=True,
             # The selected Kaggle budget is the actual training time.  The
             # worker adds six minutes for upload/download and uses every
             # remaining second of that budget on the candidate.
             kaggle_timeout_seconds=min(39600, max(1200, c.get('training_budget_seconds', 1800)+600)),
             reuse_rollouts=True, adapter_seed=20260912, defer_audit_references=True,
             # Activation checkpoints may be offloaded to host RAM. This is
             # slower but keeps the T4×2 job recoverable instead of failing on
             # a transient peak while preserving the full model and objective.
             offload_saved_tensors=True, local_step_timeout_seconds=1200,
             local_preparation_seconds=3600,
             optimization_recipe=RECIPES.get(c['module'], RECIPES['3d']))
    if c['module'] in TEXT_MODULES:
        c.update(train_tasks=12,rollouts_per_task=3,oracle_teaching=True,sft_weight=.5,
                 training_context_length=6144)
        c['generation'].update(max_new_tokens=1536)
    elif c['module']=='3d':
        # Twelve disjoint, style-balanced prompts with three candidates each
        # provide enough hard negatives for preference learning.  The local
        # machine still renders only this training slice; the 24-subject audit
        # remains held out and is evaluated after Kaggle.
        c.update(train_tasks=12,rollouts_per_task=3,minimum_preference_pairs=8,
                 auto_refill=True,sft_weight=.05)
    else:
        c.update(train_tasks=12,local_epochs=1,directions=2)
    if c['module']=='audio':c['quality_metrics']={'wer':'lower','clipping_fraction':'lower'}
    if c['module']=='3d':c['quality_metrics']={
        'nonmanifold_edge_fraction':'lower','degenerate_face_fraction':'lower',
        'clip_worst_view':'higher','clip_mean':'higher'}
    if c['module']=='image':c['quality_metrics']={
        'clip_cosine':'higher','laion_aesthetic_0_10':'higher','extreme_pixels':'lower'}
    if c['module']=='video':c['quality_metrics']={
        'clip_mean':'higher','motion_compensated_error':'lower'}
    if c['module']=='animation':c['quality_metrics']={
        'bone_length_cv':'lower','ground_penetration_m':'lower','foot_slide_m_s':'lower'}
    return c
