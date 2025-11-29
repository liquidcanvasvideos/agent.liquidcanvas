'use client'

import { useEffect, useState } from 'react'
import { Mail, ExternalLink, RefreshCw, Send, X, Loader2 } from 'lucide-react'
import { listProspects, composeEmail, sendEmail, type Prospect } from '@/lib/api'

interface LeadsTableProps {
  emailsOnly?: boolean
}

export default function LeadsTable({ emailsOnly = false }: LeadsTableProps) {
  const [prospects, setProspects] = useState<Prospect[]>([])
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 50

  const [activeProspect, setActiveProspect] = useState<Prospect | null>(null)
  const [draftSubject, setDraftSubject] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const [isSending, setIsSending] = useState(false)

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, emailsOnly])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const openComposeModal = async (prospect: Prospect) => {
    if (!prospect.contact_email) {
      alert('This lead does not have an email address yet. Please enrich first.')
      return
    }

    setIsComposing(true)
    try {
      const result = await composeEmail(prospect.id)

      // Use returned draft, falling back to existing values
      const draftSub = result.subject || prospect.draft_subject || ''
      const draftBdy = result.body || prospect.draft_body || ''

      setActiveProspect({ ...prospect, draft_subject: draftSub, draft_body: draftBdy })
      setDraftSubject(draftSub)
      setDraftBody(draftBdy)
    } catch (error: any) {
      console.error('Failed to compose email:', error)
      alert(error.message || 'Failed to compose email')
    } finally {
      setIsComposing(false)
    }
  }

  const closeComposeModal = () => {
    setActiveProspect(null)
    setDraftSubject('')
    setDraftBody('')
  }

  const handleSend = async () => {
    if (!activeProspect) return
    if (!draftSubject.trim() || !draftBody.trim()) {
      alert('Please review and fill in subject and body before sending.')
      return
    }

    if (!confirm(`Send email to ${activeProspect.contact_email}?`)) {
      return
    }

    setIsSending(true)
    try {
      await sendEmail(activeProspect.id, draftSubject, draftBody)
      await loadProspects()
      alert('Email sent successfully!')
      closeComposeModal()
    } catch (error: any) {
      console.error('Failed to send email:', error)
      alert(error.message || 'Failed to send email')
    } finally {
      setIsSending(false)
    }
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
          <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
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
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          prospect.outreach_status === 'sent'
                            ? 'bg-green-100 text-green-800'
                            : prospect.outreach_status === 'replied'
                            ? 'bg-blue-100 text-blue-800'
                            : prospect.outreach_status === 'pending'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
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
                          <button
                            onClick={() => openComposeModal(prospect)}
                            disabled={isComposing}
                            className="text-olive-600 hover:text-olive-700 text-sm underline"
                          >
                            {prospect.draft_subject ? 'View / Edit Email' : 'Compose Email'}
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

      {/* Compose / Review Modal */}
      {activeProspect && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-height-[80vh] max-h-[80vh] overflow-hidden flex flex-col">
            <div className "flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  Review &amp; Send Email
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  {activeProspect.domain} — {activeProspect.contact_email}
                </p>
              </div>
              <button
                onClick={closeComposeModal}
                className="p-1 rounded-full hover:bg-gray-200 text-gray-500"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Subject
                </label>
                <input
                  type="text"
                  value={draftSubject}
                  onChange={(e) => setDraftSubject(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-olive-500 text-sm"
                  placeholder="Email subject"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Message
                </label>
                <textarea
                  value={draftBody}
                  onChange={(e) => setDraftBody(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-olive-500 text-sm h-48 resize-vertical"
                  placeholder="Your email message will appear here. You can edit it before sending."
                />
              </div>
            </div>

            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
              <p className="text-xs text-gray-500">
                Emails are never sent automatically. You always review and click send manually.
              </p>
              <div className="flex items-center space-x-2">
                <button
                  onClick={closeComposeModal}
                  className="px-3 py-2 text-sm text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300"
                  disabled={isSending}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSend}
                  disabled={isSending}
                  className="flex items-center space-x-2 px-4 py-2 bg-olive-600 text-white rounded-md hover:bg-olive-700 disabled:opacity-50"
                >
                  {isSending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Sending...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Send Email</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

