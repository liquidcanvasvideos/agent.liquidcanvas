'use client'

import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Loader2, Copy, Check } from 'lucide-react'
import { geminiChat, type GeminiChatResponse } from '@/lib/api'

interface GeminiChatPanelProps {
  prospectId: string
  currentSubject: string
  currentBody: string
  onSuggestion?: (subject?: string, body?: string) => void
  onDraftAdopted?: (subject: string, body: string) => void
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  candidateDraft?: {
    subject: string
    body: string
  }
}

export default function GeminiChatPanel({ prospectId, currentSubject, currentBody, onSuggestion, onDraftAdopted }: GeminiChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [savingDraft, setSavingDraft] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: ChatMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await geminiChat({
        prospect_id: prospectId,
        message: input.trim(),
        current_subject: currentSubject,
        current_body: currentBody
      })

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        candidateDraft: response.candidate_draft || undefined
      }

      setMessages(prev => [...prev, assistantMessage])

      // Legacy support: if old format suggested_subject/body exists, use it
      // (This should not happen with new backend, but keeping for compatibility)
      if (!response.candidate_draft && (response as any).suggested_subject || (response as any).suggested_body) {
        onSuggestion?.((response as any).suggested_subject, (response as any).suggested_body)
      }
    } catch (error: any) {
      // Extract error message properly - handle both Error objects and string errors
      let errorText = 'Failed to get response from Gemini'
      if (error instanceof Error) {
        errorText = error.message
      } else if (typeof error === 'string') {
        errorText = error
      } else if (error?.message) {
        errorText = error.message
      }
      
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Error: ${errorText}`,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIndex(index)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  const handleUseDraft = async (candidateDraft: { subject: string; body: string }) => {
    if (savingDraft) return
    
    setSavingDraft(true)
    try {
      // Update local draft state via parent callback
      if (onDraftAdopted) {
        onDraftAdopted(candidateDraft.subject, candidateDraft.body)
      } else if (onSuggestion) {
        // Fallback to old callback if onDraftAdopted not provided
        onSuggestion(candidateDraft.subject, candidateDraft.body)
      }
      
      // Show success message
      const successMessage: ChatMessage = {
        role: 'assistant',
        content: '✅ Draft adopted! The suggested draft has been applied to your email editor.',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, successMessage])
    } catch (error: any) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Error adopting draft: ${error.message || 'Failed to save draft'}`,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setSavingDraft(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-purple-50">
        <div className="flex items-center space-x-2">
          <MessageSquare className="w-5 h-5 text-blue-600" />
          <h3 className="text-sm font-bold text-gray-900">Gemini Assistant</h3>
        </div>
        <p className="text-xs text-gray-600 mt-1">Ask for refinements, alternative phrasing, or suggestions</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-8">
            <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">Start a conversation with Gemini</p>
            <p className="text-xs text-gray-400 mt-1">Try: &quot;Make this more engaging&quot; or &quot;Suggest a better subject line&quot;</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                
                {/* Show candidate draft preview if present */}
                {msg.role === 'assistant' && msg.candidateDraft && (
                  <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-xs font-semibold text-blue-900 mb-2">💡 Draft Suggestion</p>
                    <div className="space-y-2 text-xs">
                      <div>
                        <span className="font-medium text-blue-800">Subject:</span>
                        <p className="text-blue-900 mt-1">{msg.candidateDraft.subject}</p>
                      </div>
                      <div>
                        <span className="font-medium text-blue-800">Body:</span>
                        <p className="text-blue-900 mt-1 whitespace-pre-wrap max-h-32 overflow-y-auto">
                          {msg.candidateDraft.body}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleUseDraft(msg.candidateDraft!)}
                      disabled={savingDraft}
                      className="mt-3 w-full px-3 py-2 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-1"
                    >
                      {savingDraft ? (
                        <>
                          <Loader2 className="w-3 h-3 animate-spin" />
                          <span>Applying...</span>
                        </>
                      ) : (
                        <>
                          <Check className="w-3 h-3" />
                          <span>Use This Draft</span>
                        </>
                      )}
                    </button>
                  </div>
                )}
                
                {msg.role === 'assistant' && (
                  <button
                    onClick={() => handleCopy(msg.content, idx)}
                    className="mt-2 text-xs text-gray-600 hover:text-gray-900 flex items-center space-x-1"
                  >
                    {copiedIndex === idx ? (
                      <>
                        <Check className="w-3 h-3" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-3">
              <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-200 p-4">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="Ask Gemini to refine your email..."
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            onClick={() => setInput('Make this more engaging')}
            className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
          >
            More engaging
          </button>
          <button
            onClick={() => setInput('Suggest a better subject line')}
            className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
          >
            Better subject
          </button>
          <button
            onClick={() => setInput('Add more personalization')}
            className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
          >
            More personal
          </button>
          <button
            onClick={() => setInput('Make it shorter')}
            className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
          >
            Shorter
          </button>
        </div>
      </div>
    </div>
  )
}

