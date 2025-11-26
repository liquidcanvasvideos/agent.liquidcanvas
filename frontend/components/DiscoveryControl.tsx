'use client'

import { useState, useEffect } from 'react'
import { Search, Loader2, CheckCircle2, AlertCircle, BarChart3 } from 'lucide-react'

interface DiscoveryStatus {
  status: string
  last_run?: string
  result?: {
    discovered?: number
    new_websites?: number
    skipped?: number
    failed?: number
  }
  error?: string
  started_at?: string
  completed_at?: string
}

interface AutomationStatus {
  automation_enabled: boolean
  email_trigger_mode: string
  search_interval_seconds: number
}

export default function DiscoveryControl() {
  const [status, setStatus] = useState<DiscoveryStatus | null>(null)
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [showStats, setShowStats] = useState(false)

  useEffect(() => {
    loadStatus()
    loadAutomationStatus()
    // Refresh every 10 seconds
    const interval = setInterval(() => {
      loadStatus()
      loadAutomationStatus()
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/discovery/status`
      )
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      }
    } catch (error) {
      console.error('Error loading discovery status:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadAutomationStatus = async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/status`
      )
      if (response.ok) {
        const data = await response.json()
        setAutomationStatus(data)
      }
    } catch (error) {
      console.error('Error loading automation status:', error)
    }
  }

  const triggerSearch = async () => {
    setSearching(true)
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/discovery/search-now`,
        {
          method: 'POST'
        }
      )
      if (response.ok) {
        // Wait a moment then refresh status
        setTimeout(() => {
          loadStatus()
        }, 2000)
      } else {
        alert('Failed to start search')
      }
    } catch (error: any) {
      alert(`Error: ${error.message}`)
    } finally {
      setSearching(false)
    }
  }

  const formatTime = (timeString?: string) => {
    if (!timeString) return 'Never'
    const date = new Date(timeString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)
    
    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return date.toLocaleString()
  }

  // Only show "Search Now" button if automation is in manual mode
  const isManualMode = automationStatus?.email_trigger_mode === 'manual'
  const isAutomationOn = automationStatus?.automation_enabled

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200/50 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 bg-olive-600 rounded-lg">
            <Search className="w-5 h-5 text-white" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Website Discovery</h2>
        </div>
        <button
          onClick={() => setShowStats(!showStats)}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          title="Show discovery statistics"
        >
          <BarChart3 className="w-5 h-5" />
        </button>
      </div>

      {/* Status Display */}
      {loading ? (
        <div className="flex items-center space-x-2 text-gray-600">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Loading status...</span>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Current Status */}
          <div className="flex items-center space-x-3">
            {status?.status === 'running' ? (
              <>
                <Loader2 className="w-5 h-5 text-olive-600 animate-spin" />
                <div>
                  <p className="font-medium text-gray-900">Searching Internet...</p>
                  <p className="text-sm text-gray-600">
                    {status.started_at ? `Started: ${formatTime(status.started_at)}` : 'In progress'}
                  </p>
                </div>
              </>
            ) : status?.status === 'completed' ? (
              <>
                <CheckCircle2 className="w-5 h-5 text-green-500" />
                <div>
                  <p className="font-medium text-gray-900">Last Search Completed</p>
                  <p className="text-sm text-gray-600">
                    {status.completed_at ? formatTime(status.completed_at) : 'Unknown'}
                  </p>
                </div>
              </>
            ) : status?.status === 'failed' ? (
              <>
                <AlertCircle className="w-5 h-5 text-red-500" />
                <div>
                  <p className="font-medium text-gray-900">Last Search Failed</p>
                  <p className="text-sm text-red-600">{status.error || 'Unknown error'}</p>
                </div>
              </>
            ) : (
              <>
                <AlertCircle className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900">Never Run</p>
                  <p className="text-sm text-gray-600">No searches have been performed yet</p>
                </div>
              </>
            )}
          </div>

          {/* Statistics Panel (Toggle) */}
          {showStats && status?.result && (
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Last Search Results</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-gray-600">Discovered</p>
                  <p className="text-lg font-bold text-gray-900">
                    {status.result.discovered || 0}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-600">New Websites</p>
                  <p className="text-lg font-bold text-green-600">
                    {status.result.new_websites || 0}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-600">Skipped</p>
                  <p className="text-lg font-bold text-yellow-600">
                    {status.result.skipped || 0}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-600">Failed</p>
                  <p className="text-lg font-bold text-red-600">
                    {status.result.failed || 0}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Automation Info */}
          {isAutomationOn && (
            <div className="bg-olive-50 border border-olive-200 rounded-lg p-3">
              <p className="text-sm text-olive-800">
                <strong>Automatic Mode:</strong> Searching every {automationStatus?.search_interval_seconds || 'N/A'} seconds
              </p>
              <p className="text-xs text-olive-600 mt-1">
                The system will automatically discover and scrape websites at the configured interval.
                No manual action needed.
              </p>
            </div>
          )}

          {/* Manual Search Button (Only in Manual Mode) */}
          {isManualMode && (
            <div className="border-t pt-4">
              <button
                onClick={triggerSearch}
                disabled={searching || status?.status === 'running'}
                className="w-full px-4 py-3 bg-olive-600 text-white rounded-lg font-medium hover:bg-olive-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg flex items-center justify-center space-x-2"
              >
                {searching || status?.status === 'running' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    <span>Search Internet Now</span>
                  </>
                )}
              </button>
              <p className="text-xs text-gray-500 mt-2 text-center">
                Manual mode: Click to trigger a search immediately
              </p>
            </div>
          )}

          {/* Info when automation is on */}
          {isAutomationOn && !isManualMode && (
            <div className="text-xs text-gray-500 text-center pt-2">
              Switch to manual mode in Settings to enable manual search trigger
            </div>
          )}
        </div>
      )}
    </div>
  )
}
