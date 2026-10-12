#!/bin/bash
echo "MarkdownPro:"
grep -n -C 2 "remarkPlugins=" application/src/components/MarkdownPro.tsx
echo "CoworkOverlay:"
grep -n -C 2 "remarkPlugins=" application/src/components/CoworkOverlay.tsx
echo "AuroraCoworkView:"
grep -n -C 2 "remarkPlugins=" application/src/views/AuroraCoworkView.tsx
