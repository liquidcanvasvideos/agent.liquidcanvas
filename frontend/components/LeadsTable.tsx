'use client'

import { useEffect, useState } from 'react'
import { Mail, ExternalLink, RefreshCw } from 'lucide-react'
import { listProspects, type Prospect } from '@/lib/api'

interface LeadsTableProps {
  emailsOnly?: boolean
}

export default function LeadsTable({ emailsOnly = false }: LeadsTableProps) {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50

  const loadProspects = async () => {
    try {
      setLoading(true)
      const response = await listProspects(
        skip,
        limit,
        undefined,
        undefined,
        emailsOnly ? true : undefined
      )
      setProspects(response.prospects)
      setTotal(response.total)
    } catch (error) {
      console.error('Failed to load prospects:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProspects()
    const interval = setInterval(loadProspects, 15000) // Refresh every 15 seconds
    return () => clearInterval(interval)
  }, [skip, emailsOnly])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-900">
          {emailsOnly ? 'Scraped Emails' : 'Leads'}
        </h2>
        <button
          onClick={loadProspects}
          className="flex items-center space-x-2 px-3 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh</span>
        </button>
      </div>

      {loading && prospects.length === 0 ? (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-olive-600 border-t-transparent"></div>
          <p className="text-gray-500 mt-2">Loading...</p>
        </div>
      ) : prospects.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No {emailsOnly ? 'emails' : 'leads'} found</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Domain</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Email</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Score</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Created</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map((prospect) => (
                  <tr key={prospect.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">{prospect.domain}</span>
                        {prospect.page_url && (
                          <a
                            href={prospect.page_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-olive-600 hover:text-olive-700"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {prospect.contact_email ? (
                        <div className="flex items-center space-x-2">
                          <Mail className="w-4 h-4 text-gray-400" />
                          <span className="text-gray-900">{prospect.contact_email}</span>
                        </div>
                      ) : (
                        <span className="text-gray-400">No email</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        prospect.outreach_status === 'sent' ? 'bg-green-100 text-green-800' :
                        prospect.outreach_status === 'replied' ? 'bg-blue-100 text-blue-800' :
                        prospect.outreach_status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {prospect.outreach_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-gray-900">{prospect.score?.toFixed(2) || 'N/A'}</span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {formatDate(prospect.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        {prospect.contact_email && (
                          <button className="text-olive-600 hover:text-olive-700 text-sm">
                            Compose
                          </button>
                        )}
                      </div>
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

