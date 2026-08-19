# PROMPT MASTER : REFONTE INTÉGRALE DU MODULE CONVERSATION (AURORA IA)

**Rôle de l'IA :** Tu es un Architecte Logiciel, Expert en UI/UX Frontend (React/TypeScript/Framer Motion) et Spécialiste en Systèmes Agentiques Multimodaux. 

**Objectif :** Concevoir, structurer et développer la refonte totale du "Module Conversation" (actuellement `ConversationView.tsx` / `AuroraV4ChatView.tsx`). Ce module ne doit pas être un simple chat, mais le **Hub Central Omnipotent** de l'application, capable de tout faire passer par son UI sans aucune restriction (conçu pour un usage personnel absolu).

---

## 1. VISION ET PHILOSOPHIE DU MODULE
Le Module Conversation est le cœur de l'interaction utilisateur. Il doit comprendre intrinsèquement à quoi il sert : **être l'interface universelle entre l'utilisateur et la machine**.
- **Zéro Limite :** Étant destiné à un usage personnel, il ne doit y avoir aucune restriction par défaut (taille de fichier, types d'actions, profondeur d'analyse).
- **Tout passe par l'UI :** La console, la production de médias, la recherche, tout doit être pilotable et visualisable depuis la conversation.
- **Contexte Réel et Persistant :** L'historique n'est pas juste du texte, c'est une base de données vectorielle/temporelle. Le module doit maintenir un suivi de conversation absolu, se souvenant des fichiers partagés, des modifications demandées et du contexte global des sessions précédentes.

## 2. GESTION MULTIMÉDIA ET FICHIERS (IN-LINE PREVIEW)
L'inclusion de fichiers doit être **organique et naturelle**. Avant tout téléchargement ou traitement externe, le fichier doit vivre au sein du chat.
- **Photos / Images :** Galeries intelligentes, zoom, édition légère intégrée, analyse et reconnaissance d'image.
- **Vidéos (MP4, WebM, etc.) :** Lecteur vidéo natif premium dans la bulle de chat, avec extraction de frames, transcription automatique et chapitrage.
- **Audio (MP3, WAV, etc.) :** Lecteur audio stylisé (waveform visuel), reconnaissance vocale et transcription directe.
- **Documents (PDF, Word, Excel) :** Visionneuse intégrée. Pour les PDF : extraction de texte (OCR si besoin), résumé instantané, navigation par pages.
- **3D (GLTF, OBJ, FBX) :** Mini-viewer WebGL/Three.js intégré directement dans le message pour tourner, zoomer et inspecter l'objet 3D avant de le télécharger ou de l'envoyer au module 3D.
- **Code & Scripts :** Editeur Monaco/CodeMirror intégré en read-only ou live-edit dans le chat avec coloration syntaxique.

## 3. FONCTIONNALITÉS COGNITIVES ET D'ACTION
Le module ne doit louper aucune "feature" moderne :
- **Recherche Globale (RAG & Web) :** Capacité à chercher dans les fichiers locaux de l'utilisateur, dans l'historique du chat ou sur le web, et de restituer les résultats avec des citations claires.
- **Reconnaissance :** Analyse automatique des fichiers glissés-déposés (Drag & Drop universel). L'IA décrit le contenu d'un PDF, d'une image ou d'un audio dès son insertion.
- **Production et Génération :** Si l'utilisateur demande une image, une vidéo ou un code, le résultat apparaît nativement dans le flux.
- **Actions Contextuelles :** Sur chaque message/fichier, des boutons d'actions rapides : "Traduire", "Résumer", "Convertir", "Ouvrir dans le module dédié".

## 4. PERFORMANCES ET OPTIMISATION TECHNIQUE
La conversation va devenir lourde (beaucoup de médias, historique infini). La technique doit être irréprochable :
- **Virtualisation (Windowing) :** Utilisation de listes virtuelles (ex: `@tanstack/react-virtual` ou `react-window`) pour garantir 60 FPS constants, même avec 10 000 messages contenant des rendus 3D.
- **Lazy Loading & Suspense :** Les viewers lourds (PDF, 3D) ne se chargent que lorsqu'ils sont visibles à l'écran.
- **Gestion de la Mémoire :** Nettoyage des WebGL contexts (3D) et des ObjectURLs quand les messages sortent du viewport pour éviter les fuites de mémoire (Memory Leaks).
- **State Management :** Séparation claire entre le state UI (local) et le state Données/Historique (Zustand + Persistance IndexedDB).

## 5. ESTHÉTIQUE ET DESIGN PREMIUM (EFFET WOW)
L'UI doit être spectaculaire, digne des meilleurs outils professionnels de 2026 :
- **Glassmorphism & Flou :** Panneaux translucides avec des effets de flou d'arrière-plan (backdrop-blur) très qualitatifs.
- **Micro-Animations (Framer Motion) :** 
  - Apparition fluide des bulles de chat (spring physics).
  - Transitions douces (layout animations) lorsque la taille d'un message change (ex: expansion d'un code snippet ou chargement d'un lecteur 3D).
- **Feedback Visuel :** Indicateurs de statut de l'agent (réflexion, génération de média, recherche dans les fichiers) avec des loaders futuristes (effets de particules, glowing Aurora).
- **Typographie et Espacement :** Interlignage parfait, polices modernes (Inter, Roboto ou spécifiques), lisibilité maximale même pour les blocs de code complexes.
- **Thème Visuel (Dark Mode) :** Couleurs profondes, bordures subtiles (white/10), accents néon propres à l'identité "Aurora" (Cyan, Violet, Fuchsia) selon le ton de la conversation.

---

**Livrables attendus suite à ce prompt :**
1. **Architecture Globale :** Plan d'architecture des composants React (ex: `MessageBubble`, `MediaViewer`, `ThreeDViewerInChat`, `VirtualMessageList`).
2. **Implémentation Technique :** Le code TypeScript/React complet, incluant la logique de virtualisation et de rendu conditionnel des médias.
3. **Logique de Contexte :** Le code des hooks et du store pour maintenir l'historique et envoyer le bon contexte aux LLMs (gestion multimodale).
4. **CSS/Styles :** L'intégration des classes (Tailwind/CSS) pour l'esthétique premium et les animations Framer Motion.
