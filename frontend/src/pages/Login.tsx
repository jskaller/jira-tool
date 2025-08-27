import { useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'

export default function Login() {
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('admin123')
  const [error, setError] = useState<string | null>(null)
  const nav = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await axios.post('/api/auth/login', { email, password }, { withCredentials: true })
      nav('/')
    } catch (e:any) {
      setError(e?.response?.data?.detail || 'Login failed')
    }
  }

  return (
    <div className="max-w-md mx-auto bg-white rounded-xl shadow p-6">
      <h1 className="text-xl font-semibold mb-4">Login</h1>
      {error && <div className="mb-3 text-red-700 text-sm">{error}</div>}
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="block text-sm">Email</label>
          <input className="w-full border rounded px-3 py-2" value={email} onChange={e=>setEmail(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm">Password</label>
          <input type="password" className="w-full border rounded px-3 py-2" value={password} onChange={e=>setPassword(e.target.value)} />
        </div>
        <button className="w-full py-2 rounded bg-blue-600 text-white">Sign in</button>
      </form>
      <p className="text-xs text-gray-500 mt-3">Default admin user is created on first backend run. Change the password in the DB later.</p>
    </div>
  )
}
