'use client'

import { useEffect, useMemo, useState } from 'react'
import { Mail, ExternalLink, RefreshCw, Send, X, Loader2, FileText, CheckCircle, Eye, Edit2, Download, AlertTriangle } from 'lucide-react'
import { 
  listSocialProfiles, 
  draftSocialProfiles, 
  sendSocialProfiles,
  exportSocialProfilesCSV,
  updateSocialProfileDraft,
  geminiChat,
  scrapeSocialProfiles,
  type GeminiChatResponse
} from '@/lib/api'
import GeminiChatPanel from '@/components/GeminiChatPanel'
import RichEmailEditor from '@/components/RichEmailEditor'
import FloatingComposeWindow from '@/components/FloatingComposeWindow'

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
  contact_email?: string
  external_links?: string[]
  scraped_at?: string | null
  is_eligible?: boolean
  discovery_status: string
  outreach_status: string
  draft_subject?: string
  draft_body?: string
  created_at: string
}

type Platform = 'all' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok'

const platformIcons = {
  linkedin: '💼',
  instagram: '📷',
  facebook: '👥',
  tiktok: '🎵',
}

export default function SocialLeadsTable() {
  const [profiles, setProfiles] = useState<SocialProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('all')
  const [searchCategory, setSearchCategory] = useState('')
  const [searchUsername, setSearchUsername] = useState('')

  const [activeProspect, setActiveProspect] = useState<SocialProfile | null>(null)
  const [draftSubject, setDraftSubject] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [draftBodyHtml, setDraftBodyHtml] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit')
  const [isSavingDraft, setIsSavingDraft] = useState(false)
  const [composeMinimized, setComposeMinimized] = useState(false)
  const [composeMaximized, setComposeMaximized] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState(false)

  const loadProfiles = async () => {
    try {
      setLoading(true)
      setError(null)
      const platform = selectedPlatform === 'all' ? undefined : selectedPlatform
      // List only approved profiles (Social Leads)
      const response = await listSocialProfiles(
        skip, 
        limit, 
        platform, 
        'leads', 
        searchCategory || undefined, 
        searchUsername || undefined
      )
      
      // CRITICAL DIAGNOSTIC LOGGING
      console.log('🔍 [SOCIAL LEADS TAB] RAW API RESPONSE:', response)
      console.log('🔍 [SOCIAL LEADS TAB] response.data:', response.data)
      console.log('🔍 [SOCIAL LEADS TAB] typeof response.data:', typeof response.data)
      console.log('🔍 [SOCIAL LEADS TAB] Array.isArray(response.data):', Array.isArray(response.data))
      console.log('🔍 [SOCIAL LEADS TAB] response.data?.length:', response.data?.length)
      console.log('🔍 [SOCIAL LEADS TAB] response.total:', response.total)
      console.log('🔍 [SOCIAL LEADS TAB] response keys:', response && Object.keys(response))
      if (response.data && response.data.length > 0) {
        console.log('🔍 [SOCIAL LEADS TAB] First item:', response.data[0])
      }

      const profilesArray: SocialProfile[] = Array.isArray((response as any)?.data)
        ? ((response as any).data as SocialProfile[])
        : Array.isArray((response as any)?.data?.data)
          ? (((response as any).data.data) as SocialProfile[])
          : Array.isArray((response as any)?.data?.profiles)
            ? (((response as any).data.profiles) as SocialProfile[])
            : []

      setProfiles(profilesArray)
      setTotal((response as any)?.total || (response as any)?.data?.total || profilesArray.length || 0)
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
  }, [skip, selectedPlatform, searchCategory, searchUsername])

  // Listen for refresh events
  useEffect(() => {
    const handleRefresh = () => {
      console.log('🔄 [SOCIAL LEADS] Refresh event received, reloading profiles...')
      loadProfiles()
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('refreshSocialLeads', handleRefresh)
      return () => {
        window.removeEventListener('refreshSocialLeads', handleRefresh)
      }
    }
  }, [])

  const getPlatformRules = (platform?: string) => {
    const p = (platform || '').toLowerCase()
    // These are UX constraints; backend will still enforce sending rules.
    // Keep conservative defaults.
    if (p === 'linkedin') {
      return { subjectUsed: false, maxChars: 3000, label: 'LinkedIn DM' }
    }
    if (p === 'instagram') {
      return { subjectUsed: false, maxChars: 1000, label: 'Instagram DM' }
    }
    if (p === 'facebook') {
      return { subjectUsed: false, maxChars: 2000, label: 'Facebook Message' }
    }
    if (p === 'tiktok') {
      return { subjectUsed: false, maxChars: 500, label: 'TikTok DM' }
    }
    return { subjectUsed: false, maxChars: 1000, label: 'Social Message' }
  }

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
    const nextBody = profile.draft_body || ''
    setDraftBody(nextBody)
    setDraftBodyHtml(nextBody)
    setIsComposing(true)
    setActiveTab('edit')
    setError(null)
    setComposeMinimized(false)
    setComposeMaximized(false)
  }

  const handleSaveDraft = async () => {
    if (!activeProspect) return

    try {
      setIsSavingDraft(true)
      // Update draft directly (manual editing)
      await updateSocialProfileDraft(activeProspect.id, {
        subject: draftSubject,
        body: draftBody
      })
      await loadProfiles()
      setIsComposing(false)
      setActiveProspect(null)
      setComposeMinimized(false)
      setComposeMaximized(false)
    } catch (err: any) {
      setError(err.message || 'Failed to save draft')
    } finally {
      setIsSavingDraft(false)
    }
  }

  const handleScrape = async () => {
    const ids = Array.from(selected)
    if (ids.length === 0) {
      setError('Please select at least one profile to scrape')
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      const result = await scrapeSocialProfiles(ids)
      setSelected(new Set())
      await loadProfiles()
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
        // Refresh jobs to show the new scraping job
        window.dispatchEvent(new CustomEvent('jobsCompleted'))
      }
      setError(`✅ Scraping job started for ${result.profiles_count} profile(s). Check job log for progress.`)
      setTimeout(() => setError(null), 5000)
    } catch (err: any) {
      setError(err.message || 'Failed to scrape profiles')
    } finally {
      setActionLoading(false)
    }
  }

  const handleSend = async (profileId?: string) => {
    const ids = profileId ? [profileId] : Array.from(selected)
    if (ids.length === 0) {
      setError('Please select at least one profile to send')
      return
    }

    // For single-send from compose modal: save draft first to avoid sending stale content.
    if (profileId && activeProspect && activeProspect.id === profileId) {
      const rules = getPlatformRules(activeProspect.platform)
      const body = (draftBody || '').trim()
      if (!body) {
        setError('Please write a message before sending.')
        return
      }
      if (body.length > rules.maxChars) {
        setError(`Message is too long for ${rules.label}. Limit is ${rules.maxChars} characters.`)
        return
      }

      try {
        setIsSavingDraft(true)
        await updateSocialProfileDraft(activeProspect.id, {
          subject: draftSubject,
          body: draftBody,
        })
      } catch (err: any) {
        setError(err?.message || 'Failed to save draft before sending')
        return
      } finally {
        setIsSavingDraft(false)
      }
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

  const platforms = [
    { id: 'all' as Platform, label: 'All Platforms' },
    { id: 'linkedin' as Platform, label: 'LinkedIn' },
    { id: 'instagram' as Platform, label: 'Instagram' },
    { id: 'facebook' as Platform, label: 'Facebook' },
    { id: 'tiktok' as Platform, label: 'TikTok' },
  ]

  const categoryOptions = useMemo(() => {
    const normalized = profiles
      .map(p => (p.category || '').trim())
      .filter(Boolean)
    return Array.from(new Set(normalized)).sort((a, b) => a.localeCompare(b))
  }, [profiles])

  if (loading && profiles.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-olive-600" />
        <p className="text-xs text-gray-600 mt-2">Loading social leads...</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            Social Leads
            <span className="text-[10px] bg-olive-100 text-olive-700 px-2 py-0.5 rounded-full font-medium uppercase tracking-wider border border-olive-200 underline decoration-dotted">Live Engine v2.2</span>
          </h2>
          <p className="text-xs text-gray-500 mt-1">Accepted profiles ready for outreach. Draft and send messages here.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {selected.size > 0 && (
            <>
              <button
                onClick={handleScrape}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
                title="Scrape selected profiles to get real follower counts, engagement rates, and emails"
              >
                <RefreshCw className="w-3 h-3" />
                Scrape ({selected.size})
              </button>
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

      {/* Filters and Search */}
      <div className="mb-4 grid grid-cols-1 md:grid-cols-3 gap-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
        <div>
          <label className="block text-[10px] font-bold text-olive-700 uppercase mb-1">Platform</label>
          <div className="flex items-center space-x-1 border-b border-olive-200 bg-white p-1 rounded">
            {platforms.map((platform) => (
              <button
                key={platform.id}
                onClick={() => setSelectedPlatform(platform.id)}
                className={`px-2 py-1 text-[10px] font-semibold transition-all rounded ${
                  selectedPlatform === platform.id
                    ? 'text-white bg-olive-600'
                    : 'text-gray-600 hover:text-olive-700 hover:bg-olive-50'
                }`}
              >
                {platform.id === 'all' ? platform.label : platformIcons[platform.id as keyof typeof platformIcons]}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-[10px] font-bold text-olive-700 uppercase mb-1">Category</label>
          <select
            value={searchCategory}
            onChange={(e) => {
              setSkip(0)
              setSearchCategory(e.target.value)
            }}
            className="w-full px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500 outline-none bg-white"
          >
            <option value="">All Categories</option>
            {categoryOptions.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[10px] font-bold text-olive-700 uppercase mb-1">Handle / Username</label>
          <input
            type="text"
            placeholder="Search username..."
            value={searchUsername}
            onChange={(e) => {
              setSkip(0)
              setSearchUsername(e.target.value)
            }}
            className="w-full px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500 outline-none bg-white"
          />
        </div>
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

      {/* Compose/Edit Window */}
      {isComposing && activeProspect && (
        <FloatingComposeWindow
          title="New Message"
          subtitle={`@${activeProspect.username} — ${activeProspect.platform}`}
          minimized={composeMinimized}
          maximized={composeMaximized}
          onMinimize={() => setComposeMinimized((v) => !v)}
          onMaximize={() => setComposeMaximized((v) => !v)}
          onClose={() => {
            setIsComposing(false)
            setActiveProspect(null)
            setComposeMinimized(false)
            setComposeMaximized(false)
          }}
          footer={
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={handleSaveDraft}
                disabled={isSavingDraft || isSending}
                className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {isSavingDraft ? 'Saving...' : 'Save Draft'}
              </button>
              {!!draftBody.trim() && (
                <button
                  onClick={() => handleSend(activeProspect.id)}
                  disabled={isSending || isSavingDraft || (draftBody || '').length > getPlatformRules(activeProspect.platform).maxChars}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-olive-600 rounded-lg hover:bg-olive-700 disabled:opacity-50 flex items-center gap-1.5"
                >
                  {isSending ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="w-3 h-3" />
                      Send
                    </>
                  )}
                </button>
              )}
            </div>
          }
        >
          <div className="h-full flex min-h-0">
            <div className={composeMaximized ? 'w-[380px] border-r flex flex-col min-h-0' : 'w-[260px] border-r flex flex-col min-h-0'}>
              <GeminiChatPanel
                prospectId={activeProspect.id}
                currentSubject={draftSubject}
                currentBody={draftBody}
                onDraftAdopted={(subject, body) => {
                  setDraftSubject(subject)
                  setDraftBody(body)
                  setDraftBodyHtml(body)
                }}
              />
            </div>

            <div className="flex-1 flex flex-col min-h-0">
              {(() => {
                const rules = getPlatformRules(activeProspect.platform)
                const bodyLen = (draftBody || '').length
                const over = bodyLen > rules.maxChars
                return (
                  <div className="px-3 py-2 border-b bg-gray-50 text-xs text-gray-700 flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-semibold">{rules.label}</span>
                      {activeProspect.contact_email ? (
                        <span className="text-olive-700 font-medium truncate">Email found: {activeProspect.contact_email}</span>
                      ) : null}
                    </div>
                    <div className={`font-mono ${over ? 'text-red-700' : 'text-gray-600'}`}>
                      {bodyLen}/{rules.maxChars}
                    </div>
                  </div>
                )
              })()}

              <div className="flex border-b">
                <button
                  onClick={() => setActiveTab('edit')}
                  className={`px-3 py-1.5 text-xs font-medium ${
                    activeTab === 'edit'
                      ? 'border-b-2 border-olive-600 text-olive-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Edit
                </button>
                <button
                  onClick={() => setActiveTab('preview')}
                  className={`px-3 py-1.5 text-xs font-medium ${
                    activeTab === 'preview'
                      ? 'border-b-2 border-olive-600 text-olive-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  Preview
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-3">
                {activeTab === 'edit' ? (
                  <div className="space-y-3">
                    {getPlatformRules(activeProspect.platform).subjectUsed ? (
                      <div>
                        <input
                          type="text"
                          value={draftSubject}
                          onChange={(e) => setDraftSubject(e.target.value)}
                          className="w-full px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
                          placeholder="Subject"
                        />
                      </div>
                    ) : null}
                    <div>
                      <RichEmailEditor
                        value={draftBodyHtml}
                        onChange={(html, plainText) => {
                          setDraftBodyHtml(html)
                          setDraftBody((plainText ?? '').trimEnd())
                        }}
                        placeholder="Write your message here..."
                        className={composeMaximized ? 'min-h-[420px]' : undefined}
                      />
                      {(() => {
                        const rules = getPlatformRules(activeProspect.platform)
                        const bodyLen = (draftBody || '').length
                        if (bodyLen <= rules.maxChars) return null
                        return (
                          <div className="mt-2 text-xs text-red-700 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" />
                            Message exceeds the {rules.maxChars} character limit for {rules.label}.
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {getPlatformRules(activeProspect.platform).subjectUsed ? (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-700 mb-1">Subject:</h4>
                        <p className="text-xs text-gray-900">{draftSubject || '(No subject)'}</p>
                      </div>
                    ) : null}
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700 mb-1">Body:</h4>
                      <div className="text-xs text-gray-900 whitespace-pre-wrap">{draftBody || '(No body)'}</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </FloatingComposeWindow>
      )}
    </div>
  )
}

