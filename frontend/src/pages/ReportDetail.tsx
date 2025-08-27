import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function ReportDetail() {
  const { id } = useParams()

  const { data, isLoading, error } = useQuery({
    queryKey: ['report', id],
    queryFn: async () => (await axios.get(`/api/reports/${id}`, { withCredentials: true })).data
  })

  if (isLoading) return <div>Loading…</div>
  if (error) return <div className="text-red-700">Error loading report.</div>

  const issues = data.issues as any[]
  const buckets = data.buckets as Record<string, Record<string, number>>
  const allBuckets = Array.from(new Set(Object.values(buckets).flatMap(b => Object.keys(b))))
  const chartData = issues.map(i => ({
    name: i.issue_key,
    ...Object.fromEntries(allBuckets.map(b => [b, (buckets[i.issue_key]||{})[b] || 0]))
  }))

  const download = (type: string) => {
    window.location.href = `/api/reports/${id}/csv?type=${type}`
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{data.report.title}</h1>
          <div className="text-xs text-gray-500">{new Date(data.report.created_at).toLocaleString()}</div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={()=>download('issues')} className="px-3 py-1 rounded bg-blue-600 text-white">Download Issues CSV</button>
          <button onClick={()=>download('transitions')} className="px-3 py-1 rounded bg-blue-600 text-white">Download Transitions CSV</button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-4">
        <h2 className="font-medium mb-2">Time in Status (seconds)</h2>
        <div style={{ width: '100%', height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              {allBuckets.map(b => <Bar key={b} dataKey={b} stackId="a" />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-4">
        <h2 className="font-medium mb-2">Issues</h2>
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead><tr>
              <th className="text-left p-2">Key</th>
              <th className="text-left p-2">Type</th>
              <th className="text-left p-2">Summary</th>
              <th className="text-left p-2">Epic</th>
              <th className="text-left p-2">Parent</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Assignee</th>
            </tr></thead>
            <tbody>
              {issues.map(i=> (
                <tr key={i.issue_key} className="border-t">
                  <td className="p-2">{i.issue_key}</td>
                  <td className="p-2">{i.type}</td>
                  <td className="p-2">{i.summary}</td>
                  <td className="p-2">{i.epic_key || ''}</td>
                  <td className="p-2">{i.parent_key || ''}</td>
                  <td className="p-2">{i.current_status}</td>
                  <td className="p-2">{i.assignee || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
