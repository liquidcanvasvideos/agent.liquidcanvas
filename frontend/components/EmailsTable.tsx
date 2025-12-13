'use client'

import { useEffect, useState } from 'react'
import { Mail, CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react'
import { listProspects, type Prospect } from '@/lib/api'

export default function EmailsTable() {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50

  const loadSentEmails = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await listProspects(skip, limit, 'sent')
      setProspects(response.data)
      setTotal(response.total)
      if (response.data.length === 0 && response.total === 0) {
        setError('No sent emails found. Send emails to prospects to see them here.')
      }
    } catch (error: any) {
      console.error('Failed to load sent emails:', error)
      const errorMessage = error?.message || 'Failed to load sent emails. Check if backend is running.'
      setError(errorMessage)
      setProspects([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSentEmails()
    const interval = setInterval(loadSentEmails, 15000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip])

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-900">Sent Emails</h2>
        <button
          onClick={loadSentEmails}
          className="flex items-center space-x-2 px-3 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
        >
          <RefreshCw className="w-4 h-4" />
          <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
        </button>
      </div>

      {loading && prospects.length === 0 ? (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-olive-600 border-t-transparent"></div>
          <p className="text-gray-500 mt-2">Loading sent emails...</p>
        </div>
      ) : error ? (
        <div className="text-center py-8">
          <p className="text-red-600 mb-2 font-semibold">Error loading sent emails</p>
          <p className="text-gray-600 text-sm">{error}</p>
          <button
            onClick={loadSentEmails}
            className="mt-4 px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
          >
            Retry
          </button>
        </div>
      ) : prospects.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-500 mb-2">No sent emails found</p>
          <p className="text-gray-400 text-sm">Send emails to prospects from the Leads tab to see them here.</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Recipient</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Subject</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Sent At</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Follow-ups</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map((prospect) => (
                  <tr key={prospect.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <Mail className="w-4 h-4 text-gray-400" />
                        <span className="text-gray-900">{prospect.contact_email || 'N/A'}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-900">{prospect.draft_subject || 'No subject'}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        prospect.outreach_status === 'replied' ? 'bg-blue-100 text-blue-800' :
                        prospect.outreach_status === 'sent' ? 'bg-green-100 text-green-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {prospect.outreach_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {formatDate(prospect.last_sent)}
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-900">{prospect.followups_sent || 0}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-600">
              Showing {skip + 1}-{Math.min(skip + limit, total)} of {total}
            </p>
            <div className="flex space-x-2">
              <button
                onClick={() => setSkip(Math.max(0, skip - limit))}
                disabled={skip === 0}
                className="px-3 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setSkip(skip + limit)}
                disabled={skip + limit >= total}
                className="px-3 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

