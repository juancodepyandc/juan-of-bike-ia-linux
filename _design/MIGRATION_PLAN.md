# Aurora UI migration plan

Source: `Downloads/design_aurora (1).zip` extracted to `_design/`. Two
designs to support, switched via Settings → "UI complète":

- **`aurora_v1`** — Editorial Computing (`Aurora.html`, `screens/`,
  `lib/app-shell.jsx`, `lib/aurora-sphere.jsx`, `lib/tokens.css`).
  Shared shell, sphère 3D centrale, ember accent.
- **`aurora_v3`** — Ricochet (`Aurora_v3.html`, `v3/screens-1..5.jsx`).
  11 esthétiques radicales, une par module, zéro shell partagé.

Code in the zip is **fictitious / mock**. Each ported view must wire
the existing services (`useTauri`, store hooks, `application/src/services/*`)
to the new shell so behaviour is preserved 1:1 with the current Manga
views; only the surface changes.

## Plumbing already in place

- `application/src/utils/uiSkin.ts` — `'manga' | 'aurora_v1' | 'aurora_v3'`
  with `applyUiSkin()` setting `data-ui-skin` on `<html>` + persisting
  to localStorage. Mirror of the existing `theme.ts` pattern.
- `application/src/main.tsx` — `installUiSkin()` runs at boot before
  React mounts, so the chosen skin is in effect from first paint.
- `application/src/components/SettingsPanel.tsx` — new "UI complète"
  section with the 3-way toggle (manga / aurora_v1 / aurora_v3).
- `_design/aurora_design_lib/` + `_design/aurora_design_screens_v1/` +
  `_design/aurora_design_screens_v3/` — design source under VCS.

## Remaining work — per-module migration grid

| Module       | Manga (current) | aurora_v1 (Editorial) | aurora_v3 (Ricochet)         |
|--------------|-----------------|-----------------------|------------------------------|
| Conversation | MangaChatView   | screens/chat.jsx      | v3/screens-1.jsx · ChatV3    |
| Cowork       | (n/a)           | screens/cowork.jsx    | v3/screens-1.jsx · CoworkV3  |
| Image        | MangaImageView  | screens/modules.jsx · ImageScreen | v3/screens-2.jsx · ImageV3 |
| Vidéo        | MangaVideoView  | screens/modules.jsx · VideoScreen | v3/screens-3.jsx · VideoV3 |
| 3D           | MangaModelView  | screens/modules.jsx · ThreeDScreen | v3/screens-3.jsx · ThreeV3 |
| Drawing      | MangaDrawingView| screens/modules.jsx · DrawScreen | v3/screens-4.jsx · DrawV3  |
| Academy      | MangaAcademyView| screens/modules.jsx · AcademyScreen | v3/screens-4.jsx · AcademyV3 |
| Code         | MangaCodeView   | screens/modules.jsx · CodeScreen | v3/screens-5.jsx · CodeV3  |
| Cyber        | MangaCyberView  | screens/modules.jsx · CyberScreen | v3/screens-5.jsx · CyberV3 |
| Voice        | VoiceCopilotView| screens/modules.jsx · VoiceScreen | v3/screens-2.jsx · VoiceV3 |
| Mobile shell | MobileGrimoire  | screens/mobile.jsx · MobileGrimoire | v3/screens-5.jsx · MobileV3 |

Each cell that says "screens/…" is currently a mock React component.
Porting = (a) translate JSX/CSS into a real `.tsx` view file under
`application/src/views/`, (b) replace mock data with real store/service
calls, (c) keep prop-compatibility with how App.tsx wires the lazy
import.

## Per-module port checklist

For every module port:

1. Read the design source file (in `_design/aurora_design_screens_v{1,3}/`).
2. Identify the data the design displays — map each piece to an existing
   store selector or service call.
3. Create `application/src/views/Aurora{V1|V3}{Module}View.tsx`.
   Keep the same default-export contract as the manga view it replaces.
4. In `App.tsx`, replace the hardcoded
   `lazy(() => import('./views/Manga{Module}View'))` with a switch on
   `readUiSkin()`:
   ```ts
   const skin = readUiSkin()
   const ChatView = skin === 'aurora_v1'
     ? lazy(() => import('./views/AuroraV1ChatView'))
     : skin === 'aurora_v3'
     ? lazy(() => import('./views/AuroraV3ChatView'))
     : lazy(() => import('./views/MangaChatView'))
   ```
   Better: extract this dispatch into `application/src/utils/uiSkinViews.ts`
   so each module is a single line.
5. Add a unit test: render the new view with mocked store, assert it
   surfaces the same critical actions/IDs as the manga version.

## Token assets

`_design/aurora_design_lib/tokens.css` is the V1 design token sheet
(oklch palette, font stack, radii, ease curves). To activate when
`uiSkin === 'aurora_v1'`:

- Either: globals.css conditionally `@import` it under
  `html[data-ui-skin="aurora_v1"]` selector (preferred — single sheet).
- Or: each AuroraV1*View imports it via `import './aurora_v1.css'`
  (more granular but risks duplication).

V3 has per-module token blocks scattered across `v3/screens-*.jsx`
inline; extract them into `aurora_v3_tokens.css` during the V3 port.

## Mobile

The current mobile shell is `MobileGrimoire.tsx`. The design provides
**two** mobile shells:

- V1 mobile (`screens/mobile.jsx · MobileGrimoire`) — same name, but
  reimagined under V1 tokens.
- V3 mobile (`v3/screens-5.jsx · MobileV3`) — anthology, one panel per
  module aesthetic stacked vertically.

The skin-switching logic must respect device: when on mobile and skin
≠ manga, route to the matching mobile shell.

## Anti-regression

- Each PR per ported module must keep all selftest gates green.
- TS suite (gate ts_tests) catches type breakage from view contract changes.
- Visit the route on the tunnel after deployment to confirm the live
  bundle picks up the new skin.

## Rollback

`localStorage.setItem('aurora-ui-skin', 'manga')` then reload — instant
fallback to the existing UI without touching code. Same pattern as the
existing theme switcher.
