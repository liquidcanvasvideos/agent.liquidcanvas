'use client'

import { useState, useEffect } from 'react'
import { Activity, Search, Zap, CheckCircle2, Loader2, Clock, Timer } from 'lucide-react'

interface AutomationStatus {
  automation_enabled: boolean
  email_trigger_mode: string
  search_interval_seconds: number
  next_search_time?: string
}

interface JobStatus {
  status: string
  started_at?: string
  completed_at?: string
}

interface SystemStatusProps {
  automationStatus: AutomationStatus | null
  jobs: Record<string, JobStatus> | null
  loading: boolean
}

export default function SystemStatus({ automationStatus, jobs, loading }: SystemStatusProps) {
  const [isSearching, setIsSearching] = useState(false)
  const [lastSearchTime, setLastSearchTime] = useState<Date | null>(null)
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null)
  const [nextSearchTime, setNextSearchTime] = useState<Date | null>(null)

  useEffect(() => {
    // Check if search job is running
    if (jobs?.fetch_new_art_websites) {
      const searchJob = jobs.fetch_new_art_websites
      setIsSearching(searchJob.status === 'running')
      if (searchJob.started_at) {
        setLastSearchTime(new Date(searchJob.started_at))
      }
    }

    // Set next search time from automation status
    if (automationStatus?.next_search_time) {
      setNextSearchTime(new Date(automationStatus.next_search_time))
    } else if (automationStatus?.automation_enabled && lastSearchTime && automationStatus?.search_interval_seconds) {
      // Calculate next search time from last search + interval
      const next = new Date(lastSearchTime.getTime() + automationStatus.search_interval_seconds * 1000)
      setNextSearchTime(next)
    }

    // Update countdown timer every second
    const interval = setInterval(() => {
      if (nextSearchTime && automationStatus?.automation_enabled && !isSearching) {
        const now = new Date()
        const remaining = Math.max(0, Math.floor((nextSearchTime.getTime() - now.getTime()) / 1000))
        setTimeRemaining(remaining)
      } else {
        setTimeRemaining(null)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [jobs, automationStatus, lastSearchTime, isSearching, nextSearchTime])

  const getStatusColor = () => {
    if (!automationStatus?.automation_enabled) return 'bg-gray-500'
    if (isSearching) return 'bg-green-500'
    return 'bg-olive-600'
  }

  const getStatusText = () => {
    if (loading) return 'Checking status...'
    if (!automationStatus?.automation_enabled) return 'Automation OFF'
    if (isSearching) return 'Searching Internet...'
    return 'Automation Active'
  }

  const formatTimeRemaining = (seconds: number) => {
    if (seconds <= 0) return '0s'
    
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`
    } else {
      return `${secs}s`
    }
  }

  const formatTimeAgo = (date: Date | null) => {
    if (!date) return 'Never'
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000)
    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    return `${Math.floor(seconds / 3600)}h ago`
  }

  return (
    <div className="bg-black rounded-xl shadow-lg p-6 text-white">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          {/* Status Indicator */}
          <div className="relative">
            <div className={`w-4 h-4 rounded-full ${getStatusColor()} ${isSearching ? 'animate-pulse' : ''}`}></div>
            {isSearching && (
              <div className="absolute inset-0 w-4 h-4 rounded-full bg-green-400 animate-ping opacity-75"></div>
            )}
          </div>

          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-xl font-bold">{getStatusText()}</h2>
              {isSearching && (
                <Loader2 className="w-5 h-5 animate-spin" />
              )}
            </div>
            <div className="text-sm text-gray-300 mt-1">
              {automationStatus?.automation_enabled ? (
                <>
                  Searching every {automationStatus.search_interval_seconds}s
                  {lastSearchTime && !isSearching && (
                    <span className="ml-2">• Last search: {formatTimeAgo(lastSearchTime)}</span>
                  )}
                </>
              ) : (
                'Turn on automation to start searching'
              )}
            </div>
          </div>
        </div>

        {/* Countdown Timer */}
        {automationStatus?.automation_enabled && !isSearching && timeRemaining !== null && (
          <div className="flex items-center space-x-3 bg-white/20 backdrop-blur-sm rounded-lg px-4 py-3 border border-white/30">
            <Timer className="w-5 h-5" />
            <div>
              <div className="text-xs text-gray-300 mb-0.5">Next search in</div>
              <div className="text-2xl font-bold tabular-nums">
                {formatTimeRemaining(timeRemaining)}
              </div>
            </div>
          </div>
        )}

        {/* Quick Stats */}
        <div className="flex items-center space-x-6 text-sm">
          {jobs && (
            <>
              <div className="text-center">
                <div className="text-2xl font-bold">
                  {Object.values(jobs).filter(j => j.status === 'running').length}
                </div>
                <div className="text-gray-300">Active Jobs</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">
                  {Object.values(jobs).filter(j => j.status === 'completed').length}
                </div>
                <div className="text-gray-300">Completed</div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Active Jobs List */}
      {jobs && Object.values(jobs).some(j => j.status === 'running') && (
        <div className="mt-4 pt-4 border-t border-white/20">
          <div className="flex flex-wrap gap-2">
            {Object.entries(jobs)
              .filter(([_, job]) => job.status === 'running')
              .map(([jobType, job]) => (
                <div
                  key={jobType}
                  className="flex items-center space-x-2 bg-white/20 backdrop-blur-sm rounded-lg px-3 py-2"
                >
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm font-medium">
                    {jobType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
