'use client'

import { useState, useEffect } from 'react'
import { RefreshCw, ExternalLink, CheckCircle, XCircle, FileText, Send, Eye, Download } from 'lucide-react'
import { 
  listSocialProfiles, 
  draftSocialProfiles, 
  sendSocialProfiles,
  reviewSocialProfiles,
  createSocialFollowupsPipeline
} from '@/lib/api'

interface SocialProfile {
  id: string
  platform: string
  username: string
  full_name?: string
  profile_url: string
  bio?: string
  followers_count: number
  location?: string
  category?: string
  engagement_score: number
  discovery_status: string
  outreach_status: string
  created_at: string
}

export default function SocialProfilesTable() {
  const [profiles, setProfiles] = useState<SocialProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState(false)

  const loadProfiles = async () => {
    try {
      setLoading(true)
      setError(null)
      console.log('📊 [SOCIAL PROFILES] Loading social profiles...')
      const response = await listSocialProfiles()
      console.log('📊 [SOCIAL PROFILES] API Response:', {
        dataLength: response?.data?.length,
        total: response?.total,
        hasData: !!response?.data,
        isArray: Array.isArray(response?.data),
        firstItem: response?.data?.[0]
      })
      
      // CRITICAL: If backend says there's data but we got empty array, this is an error
      if (response?.total > 0 && (!response?.data || response.data.length === 0)) {
        const errorMsg = `Backend reports ${response.total} social profiles but returned empty data array. This indicates a data visibility issue.`
        console.error(`❌ [SOCIAL PROFILES] ${errorMsg}`)
        setError(errorMsg)
        setProfiles([])
        return
      }
      
      setProfiles(response.data || [])
      console.log(`✅ [SOCIAL PROFILES] Loaded ${response.data?.length || 0} profiles (total: ${response.total || 0})`)
    } catch (err: any) {
      // CRITICAL: Do not suppress errors - log them clearly
      console.error('❌ [SOCIAL PROFILES] Failed to load profiles:', err)
      console.error('❌ [SOCIAL PROFILES] Error details:', {
        message: err?.message,
        stack: err?.stack,
        response: err?.response,
        status: err?.status
      })
      
      let errorMessage = err?.message || 'Failed to load social profiles. Check if backend is running.'
      
      // In development, show full error
      if (process.env.NODE_ENV === 'development') {
        errorMessage = `${errorMessage} (Full error: ${err?.message || 'Unknown error'})`
      }
      
      setError(errorMessage)
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProfiles()
  }, [])

  const handleSelect = (id: string) => {
    const newSelected = new Set(selected)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelected(newSelected)
  }

  const handleReview = async (action: 'qualify' | 'reject') => {
    if (selected.size === 0) {
      setError('Please select at least one profile')
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      await reviewSocialProfiles(Array.from(selected), action)
      setSelected(new Set())
      await loadProfiles()
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
      }
    } catch (err: any) {
      setError(err.message || `Failed to ${action} profiles`)
    } finally {
      setActionLoading(false)
    }
  }

  const handleCreateDrafts = async () => {
    if (selected.size === 0) {
      setError('Please select at least one profile')
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      await draftSocialProfiles(Array.from(selected), false)
      setSelected(new Set())
      await loadProfiles()
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to create drafts')
    } finally {
      setActionLoading(false)
    }
  }

  const handleSend = async () => {
    if (selected.size === 0) {
      setError('Please select at least one profile')
      return
    }

    if (!confirm(`Send messages to ${selected.size} profile(s)?`)) {
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      await sendSocialProfiles(Array.from(selected))
      setSelected(new Set())
      await loadProfiles()
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to send messages')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCreateFollowups = async () => {
    if (selected.size === 0) {
      setError('Please select at least one profile')
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      await createSocialFollowupsPipeline(Array.from(selected))
      setSelected(new Set())
      await loadProfiles()
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to create follow-ups')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-olive-600" />
        <p className="text-xs text-gray-600 mt-2">Loading profiles...</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Social Profiles</h2>
        <div className="flex items-center gap-2 flex-wrap">
          {selected.size > 0 && (
            <>
              <button
                onClick={() => handleReview('qualify')}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-1"
              >
                <CheckCircle className="w-3 h-3" />
                Qualify ({selected.size})
              </button>
              <button
                onClick={() => handleReview('reject')}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-1"
              >
                <XCircle className="w-3 h-3" />
                Reject ({selected.size})
              </button>
              <button
                onClick={handleCreateDrafts}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
              >
                <FileText className="w-3 h-3" />
                Draft ({selected.size})
              </button>
              <button
                onClick={handleSend}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 flex items-center gap-1"
              >
                <Send className="w-3 h-3" />
                Send ({selected.size})
              </button>
              <button
                onClick={handleCreateFollowups}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" />
                Follow-up ({selected.size})
              </button>
            </>
          )}
          <button
            onClick={async () => {
              try {
                const blob = await exportSocialProfilesCSV()
                const url = window.URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `social_profiles_${new Date().toISOString().split('T')[0]}.csv`
                document.body.appendChild(a)
                a.click()
                window.URL.revokeObjectURL(url)
                document.body.removeChild(a)
              } catch (error: any) {
                alert(`Failed to export CSV: ${error.message}`)
              }
            }}
            className="px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-1"
          >
            <Download className="w-3 h-3" />
            Download CSV
          </button>
          <button
            onClick={loadProfiles}
            className="px-3 py-1.5 text-xs bg-gray-600 text-white rounded-lg hover:bg-gray-700 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          {error}
        </div>
      )}

      {profiles.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-sm text-gray-600">No profiles found. Start discovering to find profiles.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-3">
                  <input
                    type="checkbox"
                    checked={selected.size === profiles.length && profiles.length > 0}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelected(new Set(profiles.map(p => p.id)))
                      } else {
                        setSelected(new Set())
                      }
                    }}
                  />
                </th>
                <th className="text-left py-2 px-3">Platform</th>
                <th className="text-left py-2 px-3">Username</th>
                <th className="text-left py-2 px-3">Name</th>
                <th className="text-left py-2 px-3">Category</th>
                <th className="text-left py-2 px-3">Followers</th>
                <th className="text-left py-2 px-3">Discovery Status</th>
                <th className="text-left py-2 px-3">Outreach Status</th>
                <th className="text-left py-2 px-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((profile) => (
                <tr key={profile.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 px-3">
                    <input
                      type="checkbox"
                      checked={selected.has(profile.id)}
                      onChange={() => handleSelect(profile.id)}
                    />
                  </td>
                  <td className="py-2 px-3 capitalize">{profile.platform}</td>
                  <td className="py-2 px-3 font-medium">@{profile.username}</td>
                  <td className="py-2 px-3">{profile.full_name || '-'}</td>
                  <td className="py-2 px-3">{profile.category || '-'}</td>
                  <td className="py-2 px-3">{profile.followers_count.toLocaleString()}</td>
                  <td className="py-2 px-3">
                    {profile.discovery_status === 'qualified' ? (
                      <span className="inline-flex items-center gap-1 text-green-600">
                        <CheckCircle className="w-3 h-3" />
                        Qualified
                      </span>
                    ) : profile.discovery_status === 'rejected' ? (
                      <span className="inline-flex items-center gap-1 text-red-600">
                        <XCircle className="w-3 h-3" />
                        Rejected
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-gray-600">
                        <Eye className="w-3 h-3" />
                        {profile.discovery_status || 'Discovered'}
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3">
                    {profile.outreach_status === 'sent' ? (
                      <span className="inline-flex items-center gap-1 text-green-600">
                        <Send className="w-3 h-3" />
                        Sent
                      </span>
                    ) : profile.outreach_status === 'drafted' ? (
                      <span className="inline-flex items-center gap-1 text-blue-600">
                        <FileText className="w-3 h-3" />
                        Drafted
                      </span>
                    ) : (
                      <span className="text-gray-600 text-xs">{profile.outreach_status || 'Pending'}</span>
                    )}
                  </td>
                  <td className="py-2 px-3">
                    <a
                      href={profile.profile_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-olive-600 hover:text-olive-700"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

