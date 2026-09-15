import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from 'lucide-react'
import { useNotificationStore } from '../stores/notificationStore.ts'
import type { NotificationLevel } from '../stores/notificationStore.ts'

const LEVEL_CONFIG: Record<NotificationLevel, { icon: typeof Info; border: string; bg: string; text: string }> = {
  info:    { icon: Info,          border: 'border-aurora-border/40',  bg: 'bg-aurora-surface/90',   text: 'text-aurora-text' },
  success: { icon: CheckCircle2,  border: 'border-green-500/30',      bg: 'bg-green-500/10',         text: 'text-green-400' },
  warning: { icon: TriangleAlert, border: 'border-yellow-500/30',     bg: 'bg-yellow-500/10',        text: 'text-yellow-400' },
  error:   { icon: AlertCircle,   border: 'border-aurora-red/30',     bg: 'bg-aurora-red/10',        text: 'text-aurora-red' },
}

export default function ToastContainer() {
  const { notifications, dismiss } = useNotificationStore()

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[200] flex flex-col gap-2">
      <AnimatePresence mode="sync">
        {notifications.map((n) => {
          const cfg = LEVEL_CONFIG[n.level]
          const Icon = cfg.icon
          return (
            <motion.div
              key={n.id}
              initial={{ opacity: 0, x: 40, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.95 }}
              transition={{ duration: 0.22 }}
              className={`pointer-events-auto flex max-w-[20rem] items-start gap-3 rounded-2xl border ${cfg.border} ${cfg.bg} px-4 py-3 shadow-xl backdrop-blur-md`}
            >
              <Icon size={16} className={`mt-0.5 shrink-0 ${cfg.text}`} />
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-medium leading-snug ${cfg.text}`}>{n.message}</p>
                {n.detail && (
                  <p className="mt-0.5 text-xs leading-relaxed text-aurora-text-dim">{n.detail}</p>
                )}
              </div>
              <button
                onClick={() => dismiss(n.id)}
                className="shrink-0 text-aurora-text-dim hover:text-aurora-text transition-colors"
              >
                <X size={14} />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
