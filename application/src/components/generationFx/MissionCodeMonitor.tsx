import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useCodeStreamStore } from '../../stores/codeStreamStore.ts'
import type { FxCodeFeed } from './fxBus.ts'

const keys = Array.from('1234567890AZERTYUIOPQSDFGHJKLMWXCVBN,;:!')

export default function MissionCodeMonitor({ feed, startedAt, status }: {
  feed?: FxCodeFeed; startedAt: number; status: string
}) {
  const runAt = useCodeStreamStore(s => s.genStartedAt)
  const running = useCodeStreamStore(s => s.streaming)
  const currentRun = !feed && runAt != null && runAt >= startedAt - 1500
  const output = useCodeStreamStore(s => currentRun ? s.streamOutput.slice(-4800) : '')
  const events = useCodeStreamStore(s => currentRun ? s.events : undefined)
  const recent = useMemo(() => events?.slice().reverse(), [events])
  const written = recent?.find(e => e.kind === 'file.written')
  const test = recent?.find(e => e.kind === 'test.result')
  const file = feed?.file ?? written?.path
  const source = feed?.source || written?.content?.slice(-4800) || output
  const consoleText = feed?.console || (test
    ? [test.summary, ...test.failedLabels].join('\n')
    : status)
  const [panel, setPanel] = useState<'code' | 'console' | null>(null)
  const visible = panel ?? (test || feed?.console ? 'console' : 'code')
  const text = visible === 'code' ? source || status : consoleText
  const previous = useRef(source)
  const [key, setKey] = useState('')
  const writing = Boolean(feed) || running
  const screen = useRef<HTMLPreElement>(null)
  const follow = useRef(true)

  useLayoutEffect(() => {
    if (follow.current && screen.current) screen.current.scrollTop = screen.current.scrollHeight
  }, [text])

  useEffect(() => {
    if (source !== previous.current && writing) {
      previous.current = source
      setKey(source.trimEnd().slice(-1).toUpperCase())
      const id = window.setTimeout(() => setKey(''), 220)
      return () => window.clearTimeout(id)
    }
  }, [source, writing])

  return <section className="mission-monitor" aria-label="Poste Code">
    <div className="mission-monitor__bar">
      <strong title={file}>{file || 'Poste Code'}</strong>
      <button type="button" aria-pressed={visible==='code'} onClick={()=>{follow.current = true; setPanel('code')}}>Code</button>
      <button type="button" aria-pressed={visible==='console'} onClick={()=>{follow.current = true; setPanel('console')}}>Console</button>
    </div>
    <pre ref={screen} tabIndex={0} aria-label={visible==='code' ? 'Code de la mission' : 'Sortie de la mission'}
      onScroll={({currentTarget: el}) => { follow.current = el.scrollHeight - el.scrollTop - el.clientHeight <= 8 }}>
      {visible==='code' ? <code>{text}</code> : text}
    </pre>
    <div className="mission-monitor__keys" aria-hidden="true">
      {keys.map(letter=><span key={letter} data-pressed={letter===key}>{letter}</span>)}
    </div>
  </section>
}
