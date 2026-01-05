'use client'

import { useEffect, useState } from 'react'
import { Mail, ExternalLink, RefreshCw, Send, X, Loader2, FileText, CheckCircle, Eye, Edit2, Download } from 'lucide-react'
import { 
  listSocialProfiles, 
  draftSocialProfiles, 
  sendSocialProfiles,
  exportSocialProfilesCSV,
  updateSocialProfileDraft,
  geminiChat,
  type GeminiChatResponse
} from '@/lib/api'
import GeminiChatPanel from '@/components/GeminiChatPanel'

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
  draft_subject?: string
  draft_body?: string
  created_at: string
}

type Platform = 'all' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok'

export default function SocialLeadsTable() {
  const [profiles, setProfiles] = useState<SocialProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('all')

  const [activeProspect, setActiveProspect] = useState<SocialProfile | null>(null)
  const [draftSubject, setDraftSubject] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit')

  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState(false)

  const loadProfiles = async () => {
    try {
      setLoading(true)
      setError(null)
      const platform = selectedPlatform === 'all' ? undefined : selectedPlatform
      // List only approved profiles (Social Leads)
      const response = await listSocialProfiles(skip, limit, platform, 'leads')
      setProfiles(response.data || [])
      setTotal(response.total || 0)
    } catch (err: any) {
      console.error('Failed to load social leads:', err)
      setError(err.message || 'Failed to load social leads')
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProfiles()
  }, [skip, selectedPlatform])

  const handleSelect = (id: string) => {
    const newSelected = new Set(selected)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelected(newSelected)
  }

  const handleCompose = (profile: SocialProfile) => {
    setActiveProspect(profile)
    setDraftSubject(profile.draft_subject || '')
    setDraftBody(profile.draft_body || '')
    setIsComposing(true)
    setActiveTab('edit')
  }

  const handleSaveDraft = async () => {
    if (!activeProspect) return

    try {
      // Update draft directly (manual editing)
      await updateSocialProfileDraft(activeProspect.id, {
        subject: draftSubject,
        body: draftBody
      })
      await loadProfiles()
      setIsComposing(false)
      setActiveProspect(null)
    } catch (err: any) {
      setError(err.message || 'Failed to save draft')
    }
  }

  const handleSend = async (profileId?: string) => {
    const ids = profileId ? [profileId] : Array.from(selected)
    if (ids.length === 0) {
      setError('Please select at least one profile to send')
      return
    }

    if (!confirm(`Send messages to ${ids.length} profile(s)?`)) {
      return
    }

    setIsSending(true)
    setError(null)
    try {
      await sendSocialProfiles(ids)
      setSelected(new Set())
      await loadProfiles()
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
      }
      if (profileId) {
        setIsComposing(false)
        setActiveProspect(null)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to send messages')
    } finally {
      setIsSending(false)
    }
  }

  const handleDraftAdopted = (subject: string, body: string) => {
    setDraftSubject(subject)
    setDraftBody(body)
    if (activeProspect) {
      // Update the active prospect's draft fields
      setActiveProspect({
        ...activeProspect,
        draft_subject: subject,
        draft_body: body
      })
    }
  }

  if (loading && profiles.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-olive-600" />
        <p className="text-xs text-gray-600 mt-2">Loading social leads...</p>
      </div>
    )
  }

  const platforms = [
    { id: 'all' as Platform, label: 'All Platforms' },
    { id: 'linkedin' as Platform, label: 'LinkedIn' },
    { id: 'instagram' as Platform, label: 'Instagram' },
    { id: 'facebook' as Platform, label: 'Facebook' },
    { id: 'tiktok' as Platform, label: 'TikTok' },
  ]

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Social Leads</h2>
          <p className="text-xs text-gray-500 mt-1">Accepted profiles ready for outreach. Draft and send messages here.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {selected.size > 0 && (
            <>
              <button
                onClick={() => handleSend()}
                disabled={actionLoading || isSending}
                className="px-3 py-1.5 text-xs bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 flex items-center gap-1"
              >
                <Send className="w-3 h-3" />
                Send ({selected.size})
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
                a.download = `social_leads_${new Date().toISOString().split('T')[0]}.csv`
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

      {/* Platform Filter */}
      <div className="mb-4 flex flex-wrap gap-2">
        {platforms.map((platform) => (
          <button
            key={platform.id}
            onClick={() => setSelectedPlatform(platform.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
              selectedPlatform === platform.id
                ? 'bg-olive-600 text-white shadow-md'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {platform.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          {error}
        </div>
      )}

      {profiles.length === 0 ? (
        <div className="text-center py-12">
          <CheckCircle className="w-12 h-12 mx-auto text-gray-400 mb-2" />
          <p className="text-sm text-gray-600">No social leads found.</p>
          <p className="text-xs text-gray-500 mt-1">Accept discovered profiles to add them to Social Leads.</p>
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
                <th className="text-left py-2 px-3">Draft Status</th>
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
                    {profile.draft_subject && profile.draft_body ? (
                      <span className="inline-flex items-center gap-1 text-blue-600">
                        <FileText className="w-3 h-3" />
                        Drafted
                      </span>
                    ) : (
                      <span className="text-gray-500 text-xs">No draft</span>
                    )}
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex items-center gap-2">
                      {!profile.draft_subject && (
                        <button
                          onClick={() => handleCompose(profile)}
                          className="p-1 text-blue-600 hover:text-blue-800"
                          title="Compose message"
                        >
                          <Mail className="w-4 h-4" />
                        </button>
                      )}
                      {profile.draft_subject && (
                        <button
                          onClick={() => handleCompose(profile)}
                          className="p-1 text-gray-400 hover:text-gray-600"
                          title="Edit draft"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                      )}
                      {profile.draft_subject && (
                        <button
                          onClick={() => handleSend(profile.id)}
                          disabled={isSending}
                          className="p-1 text-olive-600 hover:text-olive-800 disabled:opacity-50"
                          title="Send message"
                        >
                          <Send className="w-4 h-4" />
                        </button>
                      )}
                      <a
                        href={profile.profile_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-olive-600 hover:text-olive-700"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Compose/Edit Modal */}
      {isComposing && activeProspect && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-7xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold text-gray-900">
                {activeProspect.draft_subject ? 'Edit Draft' : 'Compose Message'} - @{activeProspect.username}
              </h3>
              <button
                onClick={() => {
                  setIsComposing(false)
                  setActiveProspect(null)
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-hidden flex">
              {/* Left: Gemini Chat */}
              <div className="w-1/3 border-r flex flex-col">
                <GeminiChatPanel
                  prospectId={activeProspect.id}
                  currentSubject={draftSubject}
                  currentBody={draftBody}
                  onDraftAdopted={handleDraftAdopted}
                />
              </div>

              {/* Right: Draft Editor */}
              <div className="flex-1 flex flex-col">
                <div className="flex border-b">
                  <button
                    onClick={() => setActiveTab('edit')}
                    className={`px-4 py-2 text-sm font-medium ${
                      activeTab === 'edit'
                        ? 'border-b-2 border-olive-600 text-olive-600'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => setActiveTab('preview')}
                    className={`px-4 py-2 text-sm font-medium ${
                      activeTab === 'preview'
                        ? 'border-b-2 border-olive-600 text-olive-600'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Preview
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-4">
                  {activeTab === 'edit' ? (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Subject
                        </label>
                        <input
                          type="text"
                          value={draftSubject}
                          onChange={(e) => setDraftSubject(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
                          placeholder="Message subject..."
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Message Body
                        </label>
                        <textarea
                          value={draftBody}
                          onChange={(e) => setDraftBody(e.target.value)}
                          rows={15}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
                          placeholder="Write your message here..."
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Subject:</h4>
                        <p className="text-sm text-gray-900">{draftSubject || '(No subject)'}</p>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Body:</h4>
                        <div className="text-sm text-gray-900 whitespace-pre-wrap">{draftBody || '(No body)'}</div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-t p-4 flex items-center justify-end gap-2">
                  <button
                    onClick={() => {
                      setIsComposing(false)
                      setActiveProspect(null)
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveDraft}
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                  >
                    Save Draft
                  </button>
                  {draftSubject && draftBody && (
                    <button
                      onClick={() => handleSend(activeProspect.id)}
                      disabled={isSending}
                      className="px-4 py-2 text-sm font-medium text-white bg-olive-600 rounded-lg hover:bg-olive-700 disabled:opacity-50 flex items-center gap-2"
                    >
                      {isSending ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Sending...
                        </>
                      ) : (
                        <>
                          <Send className="w-4 h-4" />
                          Send
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

