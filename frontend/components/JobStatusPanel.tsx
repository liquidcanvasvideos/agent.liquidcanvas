'use client'

import { CheckCircle, XCircle, Clock, Loader } from 'lucide-react'
import type { Job } from '@/lib/api'

interface JobStatusPanelProps {
  jobs: Job[]
  expanded?: boolean
}

export default function JobStatusPanel({ jobs, expanded = false }: JobStatusPanelProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />
      case 'running':
        return <Loader className="w-4 h-4 text-yellow-600 animate-spin" />
      default:
        return <Clock className="w-4 h-4 text-gray-600" />
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  const displayJobs = expanded ? jobs : jobs.slice(0, 5)

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <h2 className="text-lg font-bold text-gray-900 mb-4">Recent Jobs</h2>
      {displayJobs.length === 0 ? (
        <p className="text-gray-500 text-sm">No jobs found</p>
      ) : (
        <div className="space-y-3">
          {displayJobs.map((job) => (
            <div
              key={job.id}
              className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  {getStatusIcon(job.status)}
                  <span className="font-semibold text-gray-900 capitalize">{job.job_type}</span>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    job.status === 'completed' ? 'bg-green-100 text-green-800' :
                    job.status === 'failed' ? 'bg-red-100 text-red-800' :
                    job.status === 'running' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {job.status}
                  </span>
                </div>
                <span className="text-xs text-gray-500">{formatDate(job.created_at)}</span>
              </div>
              {job.error_message && (
                <p className="text-sm text-red-600 mt-2">{job.error_message}</p>
              )}
              {job.result && typeof job.result === 'object' && (
                <div className="text-xs text-gray-600 mt-2">
                  {JSON.stringify(job.result, null, 2)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

