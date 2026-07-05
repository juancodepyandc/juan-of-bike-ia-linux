import { AnimatePresence, motion } from 'framer-motion'
import { ShieldAlert, ShieldCheck, Zap } from 'lucide-react'
import type { HostPrivilegeStatus } from '../types/app'

type Props = {
  visible: boolean
  status: HostPrivilegeStatus | null
  isElevating: boolean
  error: string | null
  onElevate: () => void
  onClose: () => void
}

export default function PrivilegeBootstrapDialog({
  visible,
  status,
  isElevating,
  error,
  onElevate,
  onClose,
}: Props) {
  const devRelaunch = status?.detail?.toLowerCase().includes('mode developpement') ?? false

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[90] flex items-center justify-center bg-black/65 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="w-full max-w-xl rounded-[2rem] border border-white/10 bg-[#0b111b] p-6 text-aurora-text shadow-[0_30px_90px_rgba(0,0,0,0.45)]"
          >
            <div className="flex items-start gap-4">
              <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${status?.isAdmin ? 'bg-aurora-green/15 text-aurora-green' : 'bg-aurora-accent/15 text-aurora-accent'}`}>
                {status?.isAdmin ? <ShieldCheck size={22} /> : <ShieldAlert size={22} />}
              </div>
              <div className="min-w-0">
                <p className="mono-kicker text-[10px] text-aurora-text-dim">Autonomie systeme</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em]">
                  {status?.isAdmin
                    ? 'Mode admin actif'
                    : devRelaunch
                      ? 'Mode admin recommande pour la stack dev'
                      : 'Mode admin recommande'}
                </h2>
                <p className="mt-3 text-sm leading-relaxed text-aurora-text-muted">
                  {status?.isAdmin
                    ? 'L application dispose deja des droits eleves pour gerer les installations systeme sans reblocage local.'
                    : devRelaunch
                      ? 'Pour eviter les blocages en mode developpement, l elevation relancera la stack Tauri + Vite complete. Windows demandera encore un consentement UAC unique: c est une limite du systeme.'
                      : 'Pour eviter les blocages pendant les installations automatiques, le mode admin global est recommande. Windows demandera encore un consentement UAC unique: c est une limite du systeme, pas du module IA.'}
                </p>
              </div>
            </div>

            <div className="mt-5 rounded-[1.4rem] border border-white/10 bg-white/[0.04] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.2em] text-aurora-text-dim">Etat detecte</p>
              <p className="mt-3 text-sm text-aurora-text">{status?.detail || 'Diagnostic des privileges en attente.'}</p>
              {!status?.isAdmin && (
                <p className="mt-2 text-xs leading-relaxed text-aurora-text-muted">
                  Les installations de runtimes et SDK pourront ensuite se faire sans stopper la passe pour manque de droits applicatifs.
                </p>
              )}
              {error && (
                <p className="mt-3 rounded-xl border border-aurora-red/30 bg-aurora-red/10 px-3 py-2 text-sm text-aurora-red">
                  {error}
                </p>
              )}
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              {!status?.isAdmin && (
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-aurora-text-muted transition hover:bg-white/[0.08]"
                >
                  Continuer sans admin
                </button>
              )}
              <button
                type="button"
                onClick={status?.isAdmin ? onClose : onElevate}
                disabled={isElevating}
                className="inline-flex items-center gap-2 rounded-full border border-aurora-cyan/30 bg-aurora-cyan/15 px-5 py-2.5 text-sm font-medium text-aurora-text transition hover:bg-aurora-cyan/20 disabled:cursor-wait disabled:opacity-70"
              >
                <Zap size={16} />
                <span>
                  {status?.isAdmin
                    ? 'Fermer'
                    : isElevating
                      ? devRelaunch
                        ? 'Relance admin de la stack...'
                        : 'Passage en mode admin...'
                      : devRelaunch
                        ? 'Relancer la stack en admin'
                        : 'Passer en mode admin'}
                </span>
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
