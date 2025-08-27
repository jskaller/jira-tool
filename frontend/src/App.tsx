import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

export default function App() {
  const nav = useNavigate()
  const { data: me, refetch } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await axios.get('/api/me', { withCredentials: true })
      return res.data
    },
    retry: false
  })

  const logout = async () => {
    await axios.post('/api/auth/logout', {}, { withCredentials: true })
    refetch()
    nav('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="font-bold">Jira Tools</Link>
            {me && <Link to="/admin" className="text-sm text-blue-700">Admin</Link>}
          </div>
          <div>
            {me ? (
              <div className="flex items-center gap-3 text-sm">
                <span>{me.email}</span>
                <button onClick={logout} className="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300">Logout</button>
              </div>
            ) : (
              <Link to="/login" className="text-sm">Login</Link>
            )}
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto p-4">
        <Outlet />
      </main>
    </div>
  )
}
