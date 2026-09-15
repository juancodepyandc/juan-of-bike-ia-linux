import { motion } from 'framer-motion'
import { Box, CheckCircle2, CircleDashed, Download, AlertTriangle } from 'lucide-react'
import type { ModuleAssetPackState, ModuleAssetStatus } from '../types/app.ts'

function statusLabel(status: ModuleAssetStatus) {
  switch (status) {
    case 'scanning':
      return 'scan'
    case 'downloading':
      return 'download'
    case 'warming':
      return 'warm'
    case 'ready':
      return 'pret'
    case 'error':
      return 'erreur'
    default:
      return 'idle'
  }
}

function statusTone(status: ModuleAssetStatus) {
  if (status === 'ready') {
    return 'border-aurora-green/25 bg-aurora-green/10 text-aurora-green'
  }

  if (status === 'error') {
    return 'border-aurora-red/25 bg-aurora-red/10 text-aurora-red'
  }

  if (status === 'downloading' || status === 'warming' || status === 'scanning') {
    return 'border-aurora-yellow/25 bg-aurora-yellow/10 text-aurora-yellow'
  }

  return 'border-white/10 bg-white/[0.05] text-aurora-text-dim'
}

function StatusIcon({ status }: { status: ModuleAssetStatus }) {
  if (status === 'ready') {
    return <CheckCircle2 size={14} />
  }

  if (status === 'error') {
    return <AlertTriangle size={14} />
  }

  if (status === 'downloading') {
    return <Download size={14} />
  }

  return <CircleDashed size={14} />
}

export default function ModuleAssetPackCard({
  pack,
}: {
  pack: ModuleAssetPackState
}) {
  return (
    <div className="glass p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="mono-kicker text-[9px] text-aurora-text-dim">{pack.title || 'Pack modele'}</p>
          <p className="mt-2 text-sm text-aurora-text">{pack.detail}</p>
        </div>

        <div className="status-orb flex h-12 w-12 items-center justify-center text-white">
          <Box size={18} />
        </div>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.08]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pack.progress}%` }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="h-full rounded-full bg-[linear-gradient(90deg,#74e8ff,#ff6b3d)]"
        />
      </div>

      <div className="mt-4 space-y-2">
        {pack.assets.length > 0 ? pack.assets.map((asset) => (
          <div key={asset.id} className="rounded-2xl border border-aurora-border/35 bg-aurora-surface/60 px-3 py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm text-aurora-text">{asset.label}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-aurora-text-dim">{asset.detail}</p>
              </div>

              <div className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${statusTone(asset.status)}`}>
                <StatusIcon status={asset.status} />
                <span>{statusLabel(asset.status)}</span>
              </div>
            </div>

            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${asset.progress}%` }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
                className="h-full rounded-full bg-[linear-gradient(90deg,#74e8ff,#ff6b3d)]"
              />
            </div>

            <p className="mt-2 text-[11px] leading-relaxed text-aurora-text-dim">{asset.path || asset.target}</p>
            {(asset.error || asset.status !== 'idle') && (
              <p className={`mt-1 text-[11px] leading-relaxed ${asset.status === 'error' ? 'text-aurora-red' : 'text-aurora-text-dim'}`}>
                {asset.error || asset.detail}
              </p>
            )}
          </div>
        )) : (
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-3 text-xs text-aurora-text-dim">
            Le scan du pack modele se lancera a la premiere vraie generation de cette session.
          </div>
        )}
      </div>
    </div>
  )
}
