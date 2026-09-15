#!/bin/bash
export RUN_ID="caine_tadc_final"
export OUTDIR="application/output/3d/conversations/$RUN_ID"
mkdir -p "$OUTDIR/personnage"
mkdir -p "$OUTDIR/paysage"
python3 application/python-services/aurora_3d_pipeline.py "Caine de The Amazing Digital Circus (TADC), le personnage complet (mâchoire avec des yeux à l'intérieur, costume rouge), pose en A" "$RUN_ID" --output-dir "$OUTDIR/personnage" --no-scene --purpose "personnage" --json > "$OUTDIR/personnage.json" 2> "$OUTDIR/personnage.log" &
python3 application/python-services/aurora_3d_pipeline.py "un immense paysage rocailleux de type canyon désertique avec des formations rocheuses. Rendu réaliste, haute fidélité." "$RUN_ID" --output-dir "$OUTDIR/paysage" --no-scene --purpose "paysage" --json > "$OUTDIR/paysage.json" 2> "$OUTDIR/paysage.log" &
