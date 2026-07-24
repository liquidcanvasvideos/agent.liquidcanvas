'use client'

import { useEffect, useMemo, useState, useCallback } from 'react'
import { Mail, RefreshCw, Send, X, Loader2, ExternalLink, CheckCircle, AlertTriangle } from 'lucide-react'
import {
  listSocialProfiles,
  updateProspectDraft,
  sendEmail,
  manualVerify,
  type SocialProfile,
} from '@/lib/api'
import RichEmailEditor from '@/components/RichEmailEditor'
import GeminiChatPanel from '@/components/GeminiChatPanel'

type Platform = 'all' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok'

const platformIcons = {
  linkedin: '💼',
  instagram: '📷',
  facebook: '👥',
  tiktok: '🎵',
}

export default function SocialProfileEmailsTable() {
  const [profiles, setProfiles] = useState<SocialProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('all')
  const [searchCategory, setSearchCategory] = useState('')
  const [searchUsername, setSearchUsername] = useState('')

  const [page, setPage] = useState(0)
  const pageSize = 50

  const [activeProspect, setActiveProspect] = useState<SocialProfile | null>(null)
  const [draftSubject, setDraftSubject] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isVerifying, setIsVerifying] = useState(false)

  const handleDraftAdopted = (subject: string, body: string) => {
    setDraftSubject(subject)
    setDraftBody(body)
  }

  const loadProfiles = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const platform = selectedPlatform === 'all' ? undefined : selectedPlatform
      const res = await listSocialProfiles(
        0,
        1000,
        platform,
        'leads',
        searchCategory || undefined,
        searchUsername || undefined
      )

      const data = Array.isArray(res?.data) ? res.data : []
      const withEmails = data.filter((p) => (p.contact_email || '').trim().length > 0)

      setProfiles(withEmails)
    } catch (err: any) {
      console.error('Failed to load profile emails:', err)
      setError(err?.message || 'Failed to load profile emails')
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }, [selectedPlatform, searchCategory, searchUsername])

  useEffect(() => {
    loadProfiles()
  }, [loadProfiles])

  useEffect(() => {
    setPage(0)
  }, [selectedPlatform, searchCategory, searchUsername])

  const categoryOptions = useMemo(() => {
    const normalized = profiles
      .map((p) => (p.category || '').trim())
      .filter(Boolean)
    return Array.from(new Set(normalized)).sort((a, b) => a.localeCompare(b))
  }, [profiles])

  const pagedProfiles = useMemo(() => {
    const start = page * pageSize
    return profiles.slice(start, start + pageSize)
  }, [profiles, page])

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(profiles.length / pageSize))
  }, [profiles.length])

  const openCompose = (profile: SocialProfile) => {
    setActiveProspect(profile)
    setDraftSubject(profile.draft_subject || '')
    setDraftBody(profile.draft_body || '')
    setIsComposing(true)
    setError(null)
  }

  const closeCompose = () => {
    setIsComposing(false)
    setActiveProspect(null)
    setDraftSubject('')
    setDraftBody('')
    setIsSaving(false)
    setIsSending(false)
    setIsVerifying(false)
  }

  const handleSaveDraft = async () => {
    if (!activeProspect) return

    try {
      setIsSaving(true)
      setError(null)
      await updateProspectDraft(activeProspect.id, {
        subject: draftSubject,
        body: draftBody,
      })
      await loadProfiles()
      closeCompose()
    } catch (err: any) {
      setError(err?.message || 'Failed to save draft')
    } finally {
      setIsSaving(false)
    }
  }

  const handleVerify = async () => {
    if (!activeProspect?.contact_email) return

    try {
      setIsVerifying(true)
      setError(null)
      await manualVerify({ email: activeProspect.contact_email })
      await loadProfiles()
      setError('✅ Verification requested. Refreshing...')
      setTimeout(() => setError(null), 3000)
    } catch (err: any) {
      setError(err?.message || 'Failed to verify email')
    } finally {
      setIsVerifying(false)
    }
  }

  const handleSend = async () => {
    if (!activeProspect) return

    if (!draftSubject.trim() || !draftBody.trim()) {
      setError('Please provide both a subject and a message body before sending.')
      return
    }

    try {
      setIsSending(true)
      setError(null)

      await updateProspectDraft(activeProspect.id, {
        subject: draftSubject,
        body: draftBody,
      })

      await sendEmail(activeProspect.id)
      await loadProfiles()
      closeCompose()
    } catch (err: any) {
      setError(err?.message || 'Failed to send email')
    } finally {
      setIsSending(false)
    }
  }

  const platforms = [
    { id: 'all' as Platform, label: 'All Platforms' },
    { id: 'linkedin' as Platform, label: 'LinkedIn' },
    { id: 'instagram' as Platform, label: 'Instagram' },
    { id: 'facebook' as Platform, label: 'Facebook' },
    { id: 'tiktok' as Platform, label: 'TikTok' },
  ]

  if (loading && profiles.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-olive-600" />
        <p className="text-xs text-gray-600 mt-2">Loading profile emails...</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            Profile Emails
            <span className="text-[10px] bg-olive-100 text-olive-700 px-2 py-0.5 rounded-full font-medium uppercase tracking-wider border border-olive-200">
              Social
            </span>
          </h2>
          <p className="text-xs text-gray-500 mt-1">Social profiles with extracted emails (from scraping).</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={loadProfiles}
            className="px-3 py-1.5 text-xs bg-gray-600 text-white rounded-lg hover:bg-gray-700 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      </div>

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
                {platform.id === 'all'
                  ? platform.label
                  : platformIcons[platform.id as keyof typeof platformIcons]}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-[10px] font-bold text-olive-700 uppercase mb-1">Category</label>
          <select
            value={searchCategory}
            onChange={(e) => setSearchCategory(e.target.value)}
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
            onChange={(e) => setSearchUsername(e.target.value)}
            className="w-full px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500 outline-none bg-white"
          />
        </div>
      </div>

      {error && (
        <div
          className={`mb-4 p-3 rounded-lg text-xs border ${
            error.includes('✅') ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          {error}
        </div>
      )}

      {profiles.length === 0 ? (
        <div className="text-center py-12">
          <CheckCircle className="w-12 h-12 mx-auto text-gray-400 mb-2" />
          <p className="text-sm text-gray-600">No profile emails found.</p>
          <p className="text-xs text-gray-500 mt-1">Scrape social leads to extract emails.</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3">Platform</th>
                  <th className="text-left py-2 px-3">Username</th>
                  <th className="text-left py-2 px-3">Email</th>
                  <th className="text-left py-2 px-3">Category</th>
                  <th className="text-left py-2 px-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedProfiles.map((p) => (
                  <tr key={p.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3 capitalize">{p.platform}</td>
                    <td className="py-2 px-3 font-medium">@{p.username}</td>
                    <td className="py-2 px-3">{p.contact_email}</td>
                    <td className="py-2 px-3">{p.category || '-'}</td>
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openCompose(p)}
                          className="p-1 text-blue-600 hover:text-blue-800"
                          title="Compose email"
                        >
                          <Mail className="w-4 h-4" />
                        </button>
                        {p.profile_url && (
                          <a
                            href={p.profile_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-olive-600 hover:text-olive-700"
                            title="Open social profile"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex items-center justify-between text-xs text-gray-600">
            <div>
              Page {page + 1} / {totalPages} ({profiles.length} profiles)
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-2 py-1 text-olive-600 hover:text-olive-700 hover:underline disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-2 py-1 text-olive-600 hover:text-olive-700 hover:underline disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}

      {isComposing && activeProspect && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col border border-white/20">
            <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200/50 bg-gradient-to-r from-liquid-50/50 to-purple-50/30">
              <div>
                <h3 className="text-base font-bold liquid-gradient-text">Compose Email</h3>
                <p className="text-xs text-gray-600 mt-0.5 font-medium">
                  @{activeProspect.username} — {activeProspect.contact_email}
                </p>
              </div>
              <button
                onClick={closeCompose}
                className="p-1.5 rounded-lg hover:bg-white/80 text-gray-500 transition-all duration-200 hover:scale-110"
              >
                <X className="w-4 h-4" />
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
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                <div className="px-3 py-2 text-xs border border-amber-200 bg-amber-50 text-amber-900 rounded-lg flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 mt-0.5" />
                  <div>
                    This will send a real email using the website outreach email sender. If verification is required, verify first.
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Subject</label>
                  <input
                    type="text"
                    value={draftSubject}
                    onChange={(e) => setDraftSubject(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
                    placeholder="Email subject..."
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Message Body</label>
                  <RichEmailEditor value={draftBody} onChange={(html) => setDraftBody(html)} placeholder="Write your email..." />
                </div>
              </div>
            </div>

            <div className="border-t p-2.5 flex items-center justify-end gap-2">
              <button
                onClick={closeCompose}
                className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleVerify}
                disabled={isVerifying || !activeProspect.contact_email}
                className="px-3 py-1.5 text-xs font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {isVerifying ? 'Verifying...' : 'Verify Email'}
              </button>
              <button
                onClick={handleSaveDraft}
                disabled={isSaving || isSending}
                className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save to Draft'}
              </button>
              <button
                onClick={handleSend}
                disabled={isSending}
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
