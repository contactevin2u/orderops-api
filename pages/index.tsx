import { useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

export default function Intake() {
  const [text, setText] = useState('')
  const [parsed, setParsed] = useState<any>(null)
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState<string>('')

  const parse = async () => {
    setMessage('Parsing...')
    const res = await fetch(`${API}/parse`, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: text })
    if (!res.ok) { setMessage('Parse failed'); return }
    const data = await res.json()
    setParsed(data)
    setMessage('Parsed ✓  Semak & edit sebelum simpan.')
  }

  const createOrder = async () => {
    setCreating(true)
    const res = await fetch(`${API}/orders`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parsed })
    })
    setCreating(false)
    if (!res.ok) { setMessage('Gagal simpan order'); return }
    const data = await res.json()
    setMessage(`Order ${data.code} created ✓`)
  }

  return (
    <div>
      <h1>Order Intake (Paste → Parse → Save)</h1>
      <div className="card">
        <label>WhatsApp message (Salin & Tampal)</label>
        <textarea value={text} onChange={e => setText(e.target.value)} placeholder="Paste message di sini..." />
        <div style={{ marginTop: 8 }}>
          <button className="big" onClick={parse}>Parse</button>
        </div>
      </div>

      {parsed && (
        <div className="card">
          <h3>Hasil Parse (Boleh Edit)</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(parsed, null, 2)}</pre>
          <button disabled={creating} className="big" onClick={createOrder}>Simpan Order</button>
        </div>
      )}

      {message && <div className="card">{message}</div>}
      <div className="card">
        <a href="/ops">Pergi ke Operasi (Orders & Payments)</a>
      </div>
    </div>
  )
}
