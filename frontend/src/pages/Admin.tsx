import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useState } from 'react'

export default function Admin() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => (await axios.get('/api/admin/settings', { withCredentials: true })).data
  })

  const [form, setForm] = useState<any>({})
  const update = (k: string, v: any) => setForm((f:any)=>({ ...f, [k]: v }))

  const mutation = useMutation({
    mutationFn: async () => (await axios.put('/api/admin/settings', { ...data, ...form }, { withCredentials: true })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] })
  })

  if (isLoading) return <div>Loading…</div>
  if (error) return <div className="text-red-700">Not authorized or error.</div>

  const s = data || {}

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Admin Settings</h1>
      <div className="bg-white rounded-xl shadow p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-sm">Jira Base URL</span>
            <input className="w-full border rounded px-3 py-2" defaultValue={s.jira_base_url || ''} onChange={e=>update('jira_base_url', e.target.value)} />
          </label>
          <label className="block">
            <span className="text-sm">Jira Email</span>
            <input className="w-full border rounded px-3 py-2" defaultValue={s.jira_email || ''} onChange={e=>update('jira_email', e.target.value)} />
          </label>
          <label className="block col-span-2">
            <span className="text-sm">Jira API Token {s.has_token ? '(stored)' : ''}</span>
            <input type="password" className="w-full border rounded px-3 py-2" placeholder="••••••••" onChange={e=>update('jira_api_token', e.target.value)} />
          </label>
          <label className="block">
            <span className="text-sm">Default Window Days</span>
            <input type="number" className="w-full border rounded px-3 py-2" defaultValue={s.default_window_days} onChange={e=>update('default_window_days', parseInt(e.target.value))} />
          </label>
          <label className="block">
            <span className="text-sm">Timezone</span>
            <input className="w-full border rounded px-3 py-2" defaultValue={s.timezone} onChange={e=>update('timezone', e.target.value)} />
          </label>
          <label className="block">
            <span className="text-sm">Business Start (HH:MM)</span>
            <input className="w-full border rounded px-3 py-2" defaultValue={s.business_hours_start} onChange={e=>update('business_hours_start', e.target.value)} />
          </label>
          <label className="block">
            <span className="text-sm">Business End (HH:MM)</span>
            <input className="w-full border rounded px-3 py-2" defaultValue={s.business_hours_end} onChange={e=>update('business_hours_end', e.target.value)} />
          </label>
          <label className="block col-span-2">
            <span className="text-sm">Business Days (comma-separated)</span>
            <input className="w-full border rounded px-3 py-2" defaultValue={s.business_days} onChange={e=>update('business_days', e.target.value)} />
          </label>
        </div>
        <button onClick={()=>mutation.mutate()} className="px-4 py-2 rounded bg-blue-600 text-white">Save</button>
      </div>
    </div>
  )
}
