import { useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

type Order = {
  id: number; code: string; customer_name: string; phone?: string; status: string; order_type: string;
  total: number; rental_monthly_total: number; instalment_monthly_amount: number; outstanding_estimate: number;
}

export default function Ops() {
  const [orders, setOrders] = useState<Order[]>([])
  const [q, setQ] = useState('')

  const load = async () => {
    const u = new URL(`${API}/orders`)
    if (q) u.searchParams.set('q', q)
    const res = await fetch(u.toString())
    const data = await res.json()
    setOrders(data)
  }

  useEffect(() => { load() }, [])

  const pay = async (id: number) => {
    const amount = prompt('Amount diterima (RM)?')
    if (!amount) return
    const method = prompt('Method? CASH/TRANSFER/TNG/CHEQUE/CARD/OTHER', 'CASH') || 'CASH'
    const ref = prompt('Reference (optional)') || undefined
    const res = await fetch(`${API}/orders/${id}/payments`, { method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ amount: parseFloat(amount), method, reference: ref })
    })
    if (res.ok) load()
  }

  const invoice = (id: number) => {
    window.open(`${API}/orders/${id}/invoice.pdf`, '_blank')
  }

  const exportCash = async () => {
    const start = prompt('Start date (YYYY-MM-DD)')
    const end = prompt('End date (YYYY-MM-DD)')
    if (!start || !end) return
    window.open(`${API}/export/cash.xlsx?start=${start}&end=${end}`, '_blank')
  }

  return (
    <div>
      <h1>Operasi – Orders & Payments</h1>
      <div className="card">
        <input placeholder="Cari nama/phone/order code" value={q} onChange={e=>setQ(e.target.value)} />
        <button onClick={load}>Cari</button>
        <button onClick={exportCash} style={{ float: 'right' }}>Export Cash-basis (Excel)</button>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr><th>Code</th><th>Customer</th><th>Type</th><th>Status</th><th>Total</th><th>Outstanding (est)</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {orders.map(o => (
              <tr key={o.id}>
                <td>{o.code}</td>
                <td>{o.customer_name}<div className="badge">{o.phone}</div></td>
                <td>{o.order_type}</td>
                <td>{o.status}</td>
                <td>{o.total.toFixed(2)}</td>
                <td><b>{o.outstanding_estimate.toFixed(2)}</b></td>
                <td className="actions">
                  <button onClick={()=>pay(o.id)}>Record Payment</button>
                  <button onClick={()=>invoice(o.id)}>Invoice</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <a href="/">← Kembali ke Intake</a>
      </div>
    </div>
  )
}
