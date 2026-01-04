'use client'

import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Loader2, Copy, Check } from 'lucide-react'
import { geminiChat, type GeminiChatResponse } from '@/lib/api'

interface GeminiChatPanelProps {
  prospectId: string
  currentSubject: string
  currentBody: string
  onSuggestion?: (subject?: string, body?: string) => void
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export default function GeminiChatPanel({ prospectId, currentSubject, currentBody, onSuggestion }: GeminiChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
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
        timestamp: new Date()
      }

      setMessages(prev => [...prev, assistantMessage])

      // If Gemini suggests specific text, notify parent
      if (response.suggested_subject || response.suggested_body) {
        onSuggestion?.(response.suggested_subject, response.suggested_body)
      }
    } catch (error: any) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Error: ${error.message || 'Failed to get response from Gemini'}`,
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

  const extractSuggestedText = (content: string): { subject?: string; body?: string } => {
    // Try to extract suggested subject/body from Gemini response
    const subjectMatch = content.match(/subject[:\s]+["']?([^"'\n]+)["']?/i)
    const bodyMatch = content.match(/body[:\s]+["']?([^"']+)["']?/is)
    
    return {
      subject: subjectMatch?.[1],
      body: bodyMatch?.[1]
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
            <p className="text-xs text-gray-400 mt-1">Try: "Make this more engaging" or "Suggest a better subject line"</p>
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

