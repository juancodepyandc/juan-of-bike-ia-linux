#!/bin/bash
sed -i 's/remarkPlugins={\[remarkGfm\]}/remarkPlugins={remarkPlugins}/g' application/src/components/MarkdownPro.tsx
sed -i '/import remarkGfm from/a const remarkPlugins = [remarkGfm]' application/src/components/MarkdownPro.tsx

sed -i 's/remarkPlugins={\[remarkGfm\]}/remarkPlugins={remarkPlugins}/g' application/src/components/CoworkOverlay.tsx
sed -i '/import remarkGfm from/a const remarkPlugins = [remarkGfm]' application/src/components/CoworkOverlay.tsx

sed -i 's/remarkPlugins={\[remarkGfm\]}/remarkPlugins={remarkPlugins}/g' application/src/views/AuroraCoworkView.tsx
sed -i '/import remarkGfm from/a const remarkPlugins = [remarkGfm]' application/src/views/AuroraCoworkView.tsx
