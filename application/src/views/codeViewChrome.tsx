import { Code2 } from 'lucide-react'
import type { ComponentProps } from 'react'
import { StudioHero } from '../components/StudioHero.tsx'

type CodeViewChromeProps = {
  activeModel: string
  diagnostics: ComponentProps<typeof StudioHero>['diagnostics']
  filesCount: number
  ollamaAvailable: boolean
  ollamaLabel: string
  ollamaRunning: boolean
  projectLabel?: string
}

export function CodeViewChrome({
  activeModel,
  diagnostics,
  filesCount,
  ollamaAvailable,
  ollamaLabel,
  ollamaRunning,
  projectLabel,
}: CodeViewChromeProps) {
  return (
    <>
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden opacity-70">
        <div
          className="absolute -top-40 -left-40 h-[40rem] w-[40rem] rounded-full"
          style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--aura-code, var(--ft-accent, #e63412)) 35%, transparent) 0%, transparent 65%)', filter: 'blur(80px)' }}
        />
        <div
          className="absolute -bottom-32 right-[-10%] h-[34rem] w-[34rem] rounded-full"
          style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--accent, var(--ft-accent-2, #f78324)) 30%, transparent) 0%, transparent 65%)', filter: 'blur(90px)' }}
        />
        <div
          className="absolute top-1/3 right-[20%] h-[22rem] w-[22rem] rounded-full"
          style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--aura-code, var(--ft-accent-3, #ffd24a)) 28%, transparent) 0%, transparent 70%)', filter: 'blur(70px)' }}
        />
      </div>
      <StudioHero
        icon={Code2}
        eyebrow="Atelier code"
        title="Pipeline code expert, auto-correction controlee, preview live."
        description="Classification projet → planning architecture → generation modele expert → sandbox isole → gates qualite → boucle auto-correction avec recherche web → dev server preview responsive."
        diagnostics={diagnostics}
        stats={[
          { label: 'Modele', value: activeModel, tone: ollamaAvailable ? 'good' : 'warn' },
          { label: 'Ollama', value: ollamaLabel, tone: ollamaRunning ? 'good' : ollamaAvailable ? 'default' : 'warn' },
          { label: 'Fichiers', value: `${filesCount}` },
          ...(projectLabel ? [{ label: 'Projet', value: projectLabel }] : []),
        ]}
      />
    </>
  )
}
