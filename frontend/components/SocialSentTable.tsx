'use client'

import { useEffect, useState } from 'react'
import { Mail, RefreshCw, ExternalLink, CheckCircle, XCircle, Download } from 'lucide-react'
import { listSocialSent, exportSocialSentCSV, type SocialProfile } from '@/lib/api'

export default function SocialSentTable() {
  const [profiles, setProfiles] = useState<SocialProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50

  const loadSent = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await listSocialSent(skip, limit)
      const profilesData = Array.isArray(response?.data) ? response.data : []
      setProfiles(profilesData)
      setTotal(response?.total ?? 0)
      setError(null)
    } catch (error: any) {
      console.error('Failed to load sent messages:', error)
      setError(error?.message || 'Failed to load sent messages')
      setProfiles([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSent()
    const interval = setInterval(loadSent, 15000)
    
    const handleJobCompleted = () => {
      loadSent()
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('jobsCompleted', handleJobCompleted)
    }
    
    return () => {
      clearInterval(interval)
      if (typeof window !== 'undefined') {
        window.removeEventListener('jobsCompleted', handleJobCompleted)
      }
    }
  }, [skip])

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return 'N/A'
    }
  }

  return (
    <div className="glass rounded-xl shadow-lg p-4 animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-bold text-gray-900">Sent Messages</h2>
        <button
          onClick={async () => {
            try {
              const blob = await exportSocialSentCSV()
              const url = window.URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `social_sent_${new Date().toISOString().split('T')[0]}.csv`
              document.body.appendChild(a)
              a.click()
              window.URL.revokeObjectURL(url)
              document.body.removeChild(a)
            } catch (error: any) {
              alert(`Failed to export CSV: ${error.message}`)
            }
          }}
          className="flex items-center space-x-1 px-2 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 text-xs font-medium transition-all duration-200"
        >
          <Download className="w-3 h-3" />
          <span>Download CSV</span>
        </button>
        <button
          onClick={loadSent}
          disabled={loading}
          className="flex items-center space-x-1 px-2 py-1 bg-olive-600 text-white rounded-lg hover:bg-olive-700 text-xs font-medium transition-all duration-200"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-600 text-xs">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-olive-600 border-t-transparent"></div>
          <p className="text-gray-500 mt-2 text-xs">Loading sent messages...</p>
        </div>
      ) : profiles.length === 0 ? (
        <div className="text-center py-8">
          <Mail className="w-12 h-12 text-gray-300 mx-auto mb-2" />
          <p className="text-gray-500 text-xs">No sent messages found</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Platform</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Profile</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Subject</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Preview</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Sent At</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Follow-ups</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Status</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3">
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 capitalize">
                        {profile.platform || 'Unknown'}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-gray-900">{profile.full_name || profile.username || 'N/A'}</span>
                        {profile.profile_url && (
                          <a
                            href={profile.profile_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-olive-600 hover:text-olive-700"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-gray-900 font-medium">{profile.draft_subject || 'No subject'}</span>
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-gray-600 line-clamp-2">
                        {profile.draft_body ? (profile.draft_body.length > 100 ? profile.draft_body.substring(0, 100) + '...' : profile.draft_body) : 'No body'}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-xs text-gray-600">
                      {formatDate(profile.last_sent)}
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-gray-900 text-xs">{profile.followups_sent || 0}</span>
                    </td>
                    <td className="py-2 px-3">
                      <span className="inline-flex items-center gap-1 text-green-600">
                        <CheckCircle className="w-3 h-3" />
                        Sent
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-3">
            <p className="text-xs text-gray-600">
              Showing {skip + 1}-{Math.min(skip + limit, total)} of {total}
            </p>
            <div className="flex space-x-2">
              <button
                onClick={() => setSkip(Math.max(0, skip - limit))}
                disabled={skip === 0}
                className="px-2 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 text-xs font-medium"
              >
                Previous
              </button>
              <button
                onClick={() => setSkip(skip + limit)}
                disabled={skip + limit >= total}
                className="px-2 py-1.5 bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 text-xs font-medium"
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

