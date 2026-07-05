# Cinema — temps de generation indicatifs

Mesures sur la machine cible (RTX 5070 Ti 16 GB, Ryzen 32c, Windows 11) avec
Wan2.2 GGUF Q4_K_M en mode equilibre, sortie multi-resolutions (le pipeline
genere a une resolution interne plus basse puis upscale x1.5 ou x2).

Les temps sont **par plan de ~5 secondes** (24 fps, 121 frames). Pour estimer
une scene de 30 s on multiplie par 6, pour 1 min 10 par 14.

| Style              | Sans dialogue 720p | 1080p   | 1440p   | Avec dialogue 720p | 1080p   | 1440p   |
|--------------------|--------------------|---------|---------|--------------------|---------|---------|
| Cartoon (Pixar)    | ~22 min            | ~28 min | ~35 min | ~25 min            | ~31 min | ~38 min |
| Anime (Ghibli)     | ~18 min            | ~24 min | ~30 min | ~21 min            | ~27 min | ~33 min |
| Realiste 35mm      | ~28 min            | ~36 min | ~45 min | ~31 min            | ~39 min | ~48 min |
| Manga / encre      | ~18 min            | ~24 min | ~30 min | ~21 min            | ~27 min | ~33 min |
| Documentaire       | ~28 min            | ~36 min | ~45 min | ~31 min            | ~39 min | ~48 min |
| Noir contraste     | ~25 min            | ~32 min | ~40 min | ~28 min            | ~35 min | ~43 min |
| Watercolor         | ~24 min            | ~30 min | ~38 min | ~27 min            | ~33 min | ~41 min |

Le surcout "avec dialogue" (~3 min par plan) couvre :
- synthese XTTS-v2 / F5-TTS (10–25 s)
- lipsync SadTalker sur la premiere frame du plan (~2 min)
- mux ffmpeg

## Tableau pour quelques durees totales

Style cartoon Pixar, 1080p :

| Duree finale  | Plans (5 s) | Avec dialogue | Sans dialogue |
|---------------|-------------|---------------|---------------|
| 5 s           | 1           | ~31 min       | ~28 min       |
| 30 s          | 6           | ~3 h 06       | ~2 h 48       |
| 1 min 10      | 14          | ~7 h 14       | ~6 h 32       |

> Astuce : pour un test rapide, vise 720p sans dialogue (~22 min pour 5 s).
> Pour la qualite max (1440p avec dialogue, anime ou realiste), prevois plusieurs heures.

## Mecanique de l ETA temps reel

`cinema_pipeline.py` emet, apres chaque plan, une ligne :

```
PROGRESS:eta:{"elapsed_s": 1320.5, "done": 3, "total": 8, "remaining_s": 2200.6, "stage": "plan 3 ok"}
```

Cette ligne est captee par le bridge (`/api/python/progress`) et lue par
`MangaVideoView` qui met a jour l ETA affiche sur l ecran de cinema.
L estimation initiale s appuie sur le tableau ci-dessus, puis bascule
progressivement vers une mesure reelle (`elapsed_s / done * (total - done)`)
des le premier plan termine.

## Conditions de mesure

- ComfyUI charge prealablement le modele Wan2.2 GGUF Q4_K_M (~7 GB VRAM)
- Le LLM Ollama (storyboard) est decharge avant la generation pour liberer
  la VRAM (geree automatiquement par `useManagedRuntime`)
- Aucune autre application GPU-bound active
- Storage local SSD NVMe (les frames intermediaires PNG passent par
  `application/temp/cinema/job_<id>/`)
