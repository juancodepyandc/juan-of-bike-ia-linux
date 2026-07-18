#!/bin/bash
# Boite noire anti-gel: echantillonne RAM/swap/VRAM/pression memoire+io toutes
# les 10 s sur DISQUE. Si la machine gele, les 30 dernieres lignes disent QUI.
L=/home/juan/AuroraIA/scratchpad/freeze_watch.log
while true; do
  {
    printf '%s ' "$(date +%H:%M:%S)"
    awk '/MemAvailable/{printf "ramLibre=%.1fG ", $2/1048576}' /proc/meminfo
    awk '/SwapFree/{sf=$2} /SwapTotal/{st=$2} END{printf "swapUse=%.1fG ", (st-sf)/1048576}' /proc/meminfo
    printf 'vram=%sM ' "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)"
    for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name 2>/dev/null)" = nvme ] && printf 'nvmeTemp=%s°C ' "$(($(cat $h/temp1_input)/1000))"; done
    printf 'psiMem=%s psiIo=%s ' "$(awk 'NR==1{print $2}' /proc/pressure/memory | cut -d= -f2)" "$(awk 'NR==1{print $2}' /proc/pressure/io | cut -d= -f2)"
    ps -eo rss,comm --sort=-rss | awk 'NR>1&&NR<5{printf "%s:%.1fG ", $2, $1/1048576}'
    echo
  } >> "$L" 2>/dev/null
  # rotation simple: garder ~5000 lignes
  [ "$(wc -l < "$L" 2>/dev/null)" -gt 6000 ] && tail -5000 "$L" > "$L.tmp" && mv "$L.tmp" "$L"
  sleep 10
done
