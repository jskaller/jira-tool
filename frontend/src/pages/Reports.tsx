import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Link } from 'react-router-dom'

export default function Reports() {
  const qc = useQueryClient()
  const { data: reports } = useQuery({
    queryKey: ['reports'],
    queryFn: async () => (await axios.get('/api/reports', { withCredentials: true })).data
  })

  const create = useMutation({
    mutationFn: async () => (await axios.post('/api/reports', { title: 'Sample Report' }, { withCredentials: true })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] })
  })

  const del = useMutation({
    mutationFn: async (rid: number) => (await axios.delete('/api/reports/'+rid, { withCredentials: true })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] })
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Reports</h1>
        <button onClick={()=>create.mutate()} className="px-4 py-2 rounded bg-green-600 text-white">Create Sample Report</button>
      </div>

      <div className="bg-white rounded-xl shadow divide-y">
        {(reports || []).map((r:any)=>(
          <div key={r.id} className="p-4 flex items-center justify-between">
            <div>
              <div className="font-medium">{r.title}</div>
              <div className="text-xs text-gray-500">{new Date(r.created_at).toLocaleString()} • {r.time_mode}</div>
            </div>
            <div className="flex items-center gap-3">
              <Link to={`/reports/${r.id}`} className="px-3 py-1 rounded bg-blue-600 text-white">Open</Link>
              <button onClick={()=>del.mutate(r.id)} className="px-3 py-1 rounded bg-gray-200">Delete</button>
            </div>
          </div>
        ))}
        {(!reports || reports.length===0) && <div className="p-4 text-sm text-gray-500">No reports yet.</div>}
      </div>
    </div>
  )
}
