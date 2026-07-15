import { useState } from 'react'
import MachineConnectionsPanel from '../components/MachineConnectionsPanel'

export function MachinePanelSection() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 16 }}>
      <button onClick={() => setOpen(o => !o)} style={{
        background: 'rgba(94,124,222,.2)', color: '#e6e8eb',
        border: '1px solid rgba(94,124,222,.4)', borderRadius: 6,
        padding: '6px 12px', fontSize: 12, cursor: 'pointer',
      }}>{open ? '▾' : '▸'} Connexions machines (SSH / Pi / VPS)</button>
      {open && <div style={{ marginTop: 8 }}><MachineConnectionsPanel embed /></div>}
    </div>
  )
}
