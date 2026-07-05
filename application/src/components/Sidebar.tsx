import { motion } from 'framer-motion'
import {
  Box,
  Code2,
  GraduationCap,
  Image,
  MessageCircle,
  Mic,
  Paintbrush,
  Shield,
  Video,
} from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import type { ModuleId } from '../types/app'

const MODULES: Array<{
  id: ModuleId
  label: string
  icon: typeof MessageCircle
  gradient: string
  signature: string
}> = [
  { id: 'conversation', label: 'Copilote', icon: MessageCircle, gradient: 'from-cyan-400 to-blue-500', signature: '#22d3ee' },
  { id: 'image', label: 'Image', icon: Image, gradient: 'from-violet-400 to-fuchsia-500', signature: '#a78bfa' },
  { id: 'code', label: 'Code', icon: Code2, gradient: 'from-emerald-400 to-teal-500', signature: '#34d399' },
  { id: 'video', label: 'Vidéo', icon: Video, gradient: 'from-orange-400 to-rose-500', signature: '#fb923c' },
  { id: 'drawing', label: 'Dessin', icon: Paintbrush, gradient: 'from-pink-400 to-rose-500', signature: '#ec4899' },
  { id: '3d', label: '3D', icon: Box, gradient: 'from-indigo-400 to-violet-500', signature: '#6366f1' },
  { id: 'cyber', label: 'Cyber', icon: Shield, gradient: 'from-red-500 to-rose-600', signature: '#ef4444' },
  { id: 'learning', label: 'Académie', icon: GraduationCap, gradient: 'from-yellow-400 to-orange-400', signature: '#fde047' },
]

function ServiceDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className="flex items-center gap-1.5 text-[10px] text-white/40 shrink-0 font-medium"
      title={`${label}: ${ok ? 'actif' : 'hors ligne'}`}
    >
      <span className={`relative h-2 w-2 rounded-full transition-colors ${ok ? 'bg-emerald-400' : 'bg-white/15'}`}>
        {ok && <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-60" />}
      </span>
      {label}
    </span>
  )
}

export default function Sidebar() {
  const { activeModule, setActiveModule, services, runtimeServices } = useAppStore()

  const ollamaOk = services?.ollama || runtimeServices?.ollama?.running || false
  const comfyOk = services?.comfyui || runtimeServices?.comfyui?.running || false

  return (
    <div className="glass-strong px-2 py-2 sm:px-3 sm:py-3 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 aurora-mesh opacity-30" />
      <div className="relative flex items-center gap-1.5 overflow-x-auto no-scrollbar sm:gap-2 pb-0.5">
        {MODULES.map((module) => {
          const Icon = module.icon
          const isActive = module.id === activeModule

          return (
            <motion.button
              key={module.id}
              whileHover={{ y: -3, scale: 1.02 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setActiveModule(module.id)}
              className={`relative shrink-0 rounded-2xl border px-2.5 py-2 transition-all sm:px-3 sm:py-2.5 ${
                isActive
                  ? 'border-white/20 text-white shadow-2xl'
                  : 'border-white/8 bg-white/[0.03] text-aurora-text-muted hover:border-white/16 hover:text-aurora-text hover:bg-white/[0.06]'
              }`}
              style={
                isActive
                  ? {
                      background: `linear-gradient(135deg, ${module.signature}26, rgba(255,255,255,0.06))`,
                      boxShadow: `0 0 0 1px ${module.signature}55, 0 12px 28px ${module.signature}33, 0 0 40px ${module.signature}22`,
                    }
                  : undefined
              }
            >
              {isActive && (
                <motion.span
                  layoutId="sidebar-active-glow"
                  className="absolute -inset-px rounded-2xl pointer-events-none"
                  style={{ boxShadow: `0 0 30px ${module.signature}66, inset 0 1px 0 rgba(255,255,255,0.18)` }}
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
              <div className="relative flex items-center gap-2 sm:gap-2.5">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-xl transition-all ${
                    isActive ? 'shadow-inner' : 'border border-white/10 bg-white/[0.04]'
                  }`}
                  style={
                    isActive
                      ? { background: `linear-gradient(135deg, ${module.signature}, ${module.signature}99)` }
                      : undefined
                  }
                >
                  <Icon size={15} className={isActive ? 'text-white drop-shadow' : ''} />
                </div>
                <div className="pr-1 text-left">
                  <p className={`text-xs font-semibold sm:text-sm ${isActive ? 'text-white' : ''}`}>{module.label}</p>
                </div>
              </div>
            </motion.button>
          )
        })}

        <div className="ml-auto flex shrink-0 items-center gap-3 pl-3 pr-2 border-l border-white/[0.07]">
          <ServiceDot ok={ollamaOk} label="Ollama" />
          <ServiceDot ok={comfyOk} label="ComfyUI" />
        </div>
      </div>
    </div>
  )
}
