'use client'

import { Clock, CheckCircle2, XCircle, Loader2, Play } from 'lucide-react'
import type { LatestJobs } from '@/lib/api'

interface JobStatusPanelProps {
  jobs: LatestJobs
  expanded?: boolean
}

export default function JobStatusPanel({ jobs, expanded = false }: JobStatusPanelProps) {
  const jobNames: Record<string, string> = {
    fetch_new_art_websites: 'Website Discovery',
    scrape_pending_websites: 'Scrape Websites',
    extract_and_store_contacts: 'Extract Contacts',
    generate_ai_email: 'Generate Emails',
    send_email_if_not_sent: 'Send Emails',
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Loader2 className="w-5 h-5 text-olive-600 animate-spin" />
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />
      default:
        return <Clock className="w-5 h-5 text-gray-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-olive-100 text-olive-800 border-olive-200'
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200'
      default:
        return 'bg-gray-100 text-gray-600 border-gray-200'
    }
  }

  const formatTime = (timeString: string | null) => {
    if (!timeString) return 'N/A'
    const date = new Date(timeString)
    return date.toLocaleString()
  }

  const jobEntries = Object.entries(jobs)

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200/50 p-6">
      <div className="flex items-center space-x-2 mb-4">
        <div className="p-2 bg-olive-600 rounded-lg">
          <Play className="w-5 h-5 text-white" />
        </div>
        <h2 className="text-xl font-bold text-gray-900">Job Status</h2>
      </div>

      {jobEntries.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No job data available</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobEntries.map(([jobType, job]) => (
            <div
              key={jobType}
              className={`p-4 rounded-lg border-2 ${getStatusColor(job.status)} transition-all hover:shadow-md`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(job.status)}
                  <div>
                    <h3 className="font-semibold">{jobNames[jobType] || jobType}</h3>
                    <p className="text-xs opacity-75 mt-0.5">
                      {job.status === 'running' && job.started_at
                        ? `Started: ${formatTime(job.started_at)}`
                        : job.completed_at
                        ? `Completed: ${formatTime(job.completed_at)}`
                        : 'Never run'}
                    </p>
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(job.status)}`}>
                  {job.status}
                </span>
              </div>

              {expanded && job.result && (
                <div className="mt-3 pt-3 border-t border-current/20">
                  <p className="text-xs font-medium mb-1">Results:</p>
                  <pre className="text-xs opacity-75 overflow-x-auto">
                    {JSON.stringify(job.result, null, 2)}
                  </pre>
                </div>
              )}

              {expanded && job.error_message && (
                <div className="mt-3 pt-3 border-t border-current/20">
                  <p className="text-xs font-medium mb-1">Error:</p>
                  <p className="text-xs opacity-75">{job.error_message}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
