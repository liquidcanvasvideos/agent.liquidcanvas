'use client'

import { useEffect, useState } from 'react'
import { FileText, RefreshCw, ExternalLink, Send, Edit, X } from 'lucide-react'
import { listSocialDrafts, sendSocialProfiles, type SocialProfile } from '@/lib/api'

export default function SocialDraftsTable() {
  const [profiles, setProfiles] = useState<SocialProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState(false)
  const [editingProfile, setEditingProfile] = useState<string | null>(null)
  const [editSubject, setEditSubject] = useState('')
  const [editBody, setEditBody] = useState('')

  const loadDrafts = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await listSocialDrafts(skip, limit)
      const profilesData = Array.isArray(response?.data) ? response.data : []
      setProfiles(profilesData)
      setTotal(response?.total ?? 0)
      setError(null)
    } catch (error: any) {
      console.error('Failed to load drafts:', error)
      setError(error?.message || 'Failed to load drafts')
      setProfiles([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDrafts()
    const interval = setInterval(loadDrafts, 15000)
    
    const handleJobCompleted = () => {
      loadDrafts()
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

  const handleSend = async () => {
    if (selected.size === 0) {
      setError('Please select at least one draft')
      return
    }

    if (!confirm(`Send ${selected.size} draft(s)?`)) {
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      await sendSocialProfiles(Array.from(selected))
      setSelected(new Set())
      await loadDrafts()
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to send messages')
    } finally {
      setActionLoading(false)
    }
  }

  const handleEdit = (profile: SocialProfile) => {
    setEditingProfile(profile.id)
    setEditSubject(profile.draft_subject || '')
    setEditBody(profile.draft_body || '')
  }

  const handleSaveEdit = async () => {
    if (!editingProfile) return
    
    setActionLoading(true)
    setError(null)
    try {
      // TODO: Add API endpoint to update draft
      // For now, just close the editor
      setEditingProfile(null)
      await loadDrafts()
    } catch (err: any) {
      setError(err.message || 'Failed to update draft')
    } finally {
      setActionLoading(false)
    }
  }

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selected)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelected(newSelected)
  }

  const toggleSelectAll = () => {
    if (selected.size === profiles.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(profiles.map(p => p.id)))
    }
  }

  return (
    <div className="glass rounded-xl shadow-lg p-4 animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-bold text-gray-900">Drafted Messages</h2>
        <div className="flex items-center space-x-2">
          <button
            onClick={async () => {
              try {
                const blob = await exportSocialDraftsCSV()
                const url = window.URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `social_drafts_${new Date().toISOString().split('T')[0]}.csv`
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
            onClick={loadDrafts}
            disabled={loading}
            className="flex items-center space-x-1 px-2 py-1 bg-olive-600 text-white rounded-lg hover:bg-olive-700 text-xs font-medium transition-all duration-200"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          {selected.size > 0 && (
            <button
              onClick={handleSend}
              disabled={actionLoading}
              className="flex items-center space-x-1 px-2 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 text-xs font-medium transition-all duration-200 disabled:opacity-50"
            >
              <Send className="w-3 h-3" />
              <span>Send Selected ({selected.size})</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-600 text-xs">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-olive-600 border-t-transparent"></div>
          <p className="text-gray-500 mt-2 text-xs">Loading drafts...</p>
        </div>
      ) : profiles.length === 0 ? (
        <div className="text-center py-8">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-2" />
          <p className="text-gray-500 text-xs">No drafts found</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3">
                    <input
                      type="checkbox"
                      checked={selected.size === profiles.length && profiles.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded"
                    />
                  </th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Platform</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Profile</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Subject</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Preview</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Created</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3">
                      <input
                        type="checkbox"
                        checked={selected.has(profile.id)}
                        onChange={() => toggleSelect(profile.id)}
                        className="rounded"
                      />
                    </td>
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
                      {formatDate(profile.created_at)}
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex items-center space-x-1">
                        <button
                          onClick={() => handleEdit(profile)}
                          className="text-blue-600 hover:text-blue-700 text-xs font-medium"
                        >
                          <Edit className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => sendSocialProfiles([profile.id])}
                          disabled={actionLoading}
                          className="text-green-600 hover:text-green-700 text-xs font-medium disabled:opacity-50"
                        >
                          <Send className="w-3 h-3" />
                        </button>
                      </div>
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

      {/* Edit Modal */}
      {editingProfile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-gray-900">Edit Draft</h3>
              <button
                onClick={() => setEditingProfile(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                <input
                  type="text"
                  value={editSubject}
                  onChange={(e) => setEditSubject(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Body</label>
                <textarea
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  rows={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <button
                  onClick={() => setEditingProfile(null)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={actionLoading}
                  className="px-4 py-2 bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 text-sm font-medium"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

