#!/bin/bash
export RUN_ID="caine_tadc_paysage"
export OUTDIR="application/output/3d/conversations/$RUN_ID"
mkdir -p "$OUTDIR"
python3 application/python-services/scene_orchestrator.py \
  --prompt "Caine de The Amazing Digital Circus (TADC), le personnage complet (mâchoire avec des yeux à l'intérieur, costume rouge), pose en A, se tenant sur un immense paysage rocailleux de type canyon désertique avec des formations rocheuses. Rendu réaliste, haute fidélité." \
  --run-id "$RUN_ID" \
  --output-dir "$OUTDIR" > "$OUTDIR/scene.log" 2>&1
