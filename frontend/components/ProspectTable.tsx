'use client'

import { useState, useEffect } from 'react'
import { listProspects, composeEmail, sendEmail, type Prospect } from '@/lib/api'
import { Mail, Send, Edit, Filter } from 'lucide-react'

export default function ProspectTable() {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [limit] = useState(50)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [hasEmailFilter, setHasEmailFilter] = useState<string>('')
  const [composing, setComposing] = useState<string | null>(null)
  const [sending, setSending] = useState<string | null>(null)

  const loadProspects = async () => {
    setLoading(true)
    try {
      const data = await listProspects(
        skip,
        limit,
        statusFilter || undefined,
        undefined,
        hasEmailFilter === 'true' ? true : hasEmailFilter === 'false' ? false : undefined
      )
      setProspects(data.prospects)
      setTotal(data.total)
    } catch (error) {
      console.error('Error loading prospects:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProspects()
    const interval = setInterval(loadProspects, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, statusFilter, hasEmailFilter])

  const handleCompose = async (prospectId: string) => {
    setComposing(prospectId)
    try {
      await composeEmail(prospectId)
      await loadProspects()
      alert('Email composed successfully!')
    } catch (error: any) {
      alert(`Failed to compose email: ${error.message}`)
    } finally {
      setComposing(null)
    }
  }

  const handleSend = async (prospectId: string) => {
    if (!confirm('Send email to this prospect?')) return
    setSending(prospectId)
    try {
      await sendEmail(prospectId)
      await loadProspects()
      alert('Email sent successfully!')
    } catch (error: any) {
      alert(`Failed to send email: ${error.message}`)
    } finally {
      setSending(null)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Prospects</h2>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setSkip(0)
              }}
              className="px-2 py-1 border border-gray-300 rounded-md text-sm"
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="sent">Sent</option>
              <option value="replied">Replied</option>
            </select>
            <select
              value={hasEmailFilter}
              onChange={(e) => {
                setHasEmailFilter(e.target.value)
                setSkip(0)
              }}
              className="px-2 py-1 border border-gray-300 rounded-md text-sm"
            >
              <option value="">All</option>
              <option value="true">Has Email</option>
              <option value="false">No Email</option>
            </select>
          </div>
        </div>
        <div className="text-sm text-gray-600">
          Total: {total} prospects
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">Loading...</div>
      ) : prospects.length === 0 ? (
        <div className="p-8 text-center text-gray-500">No prospects found</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Domain</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {prospects.map((prospect) => (
                <tr key={prospect.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">
                    <div className="font-medium text-gray-900">{prospect.domain}</div>
                    {prospect.page_title && (
                      <div className="text-xs text-gray-500">{prospect.page_title}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {prospect.contact_email || (
                      <span className="text-gray-400">No email</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className="font-medium">{prospect.score?.toFixed(1) || 'N/A'}</span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`px-2 py-1 rounded-full text-xs ${
                      prospect.outreach_status === 'sent' ? 'bg-green-100 text-green-800' :
                      prospect.outreach_status === 'replied' ? 'bg-blue-100 text-blue-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {prospect.outreach_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      {!prospect.draft_subject && (
                        <button
                          onClick={() => handleCompose(prospect.id)}
                          disabled={composing === prospect.id}
                          className="p-1 text-blue-600 hover:text-blue-800 disabled:opacity-50"
                          title="Compose email"
                        >
                          <Mail className="w-4 h-4" />
                        </button>
                      )}
                      {prospect.draft_subject && prospect.contact_email && (
                        <button
                          onClick={() => handleSend(prospect.id)}
                          disabled={sending === prospect.id}
                          className="p-1 text-green-600 hover:text-green-800 disabled:opacity-50"
                          title="Send email"
                        >
                          <Send className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > limit && (
        <div className="p-4 border-t border-gray-200 flex items-center justify-between">
          <button
            onClick={() => setSkip(Math.max(0, skip - limit))}
            disabled={skip === 0}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">
            Showing {skip + 1}-{Math.min(skip + limit, total)} of {total}
          </span>
          <button
            onClick={() => setSkip(skip + limit)}
            disabled={skip + limit >= total}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

