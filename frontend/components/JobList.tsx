'use client'

import { useEffect, useState } from 'react'
import { getJobStatus, cancelJob, type Job } from '@/lib/api'
import { RefreshCw, CheckCircle, XCircle, Clock, Loader, X } from 'lucide-react'

interface JobListProps {
  jobs: Job[]
  onRefresh: () => void
}

export default function JobList({ jobs, onRefresh }: JobListProps) {
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set())
  const [cancellingJobs, setCancellingJobs] = useState<Set<string>>(new Set())

  const toggleJob = (jobId: string) => {
    const newExpanded = new Set(expandedJobs)
    if (newExpanded.has(jobId)) {
      newExpanded.delete(jobId)
    } else {
      newExpanded.add(jobId)
    }
    setExpandedJobs(newExpanded)
  }

  const handleCancelJob = async (jobId: string) => {
    if (!confirm('Are you sure you want to cancel this job?')) {
      return
    }
    
    setCancellingJobs(prev => new Set(prev).add(jobId))
    try {
      await cancelJob(jobId)
      onRefresh() // Refresh the job list
    } catch (error: any) {
      alert(`Failed to cancel job: ${error.message}`)
    } finally {
      setCancellingJobs(prev => {
        const newSet = new Set(prev)
        newSet.delete(jobId)
        return newSet
      })
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'running':
        return <Loader className="w-4 h-4 text-blue-500 animate-spin" />
      default:
        return <Clock className="w-4 h-4 text-gray-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      case 'running':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  if (jobs.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
          <button
            onClick={onRefresh}
            className="p-2 text-gray-600 hover:text-gray-900"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <div className="text-sm text-gray-500">No jobs yet</div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
          <button
            onClick={onRefresh}
            className="p-2 text-gray-600 hover:text-gray-900"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="divide-y divide-gray-200">
        {jobs.map((job) => (
          <div key={job.id} className="p-4 hover:bg-gray-50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {getStatusIcon(job.status)}
                <div>
                  <div className="font-medium text-gray-900">{job.job_type}</div>
                  <div className="text-xs text-gray-500">
                    {new Date(job.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(job.status)}`}>
                  {job.status}
                </span>
                {(job.status === 'running' || job.status === 'pending') && (
                  <button
                    onClick={() => handleCancelJob(job.id)}
                    disabled={cancellingJobs.has(job.id)}
                    className="px-2 py-1 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                    title="Stop this job"
                  >
                    <X className="w-3 h-3" />
                    {cancellingJobs.has(job.id) ? 'Stopping...' : 'Stop'}
                  </button>
                )}
                <button
                  onClick={() => toggleJob(job.id)}
                  className="text-sm text-gray-600 hover:text-gray-900"
                >
                  {expandedJobs.has(job.id) ? 'Hide' : 'Details'}
                </button>
              </div>
            </div>
            {expandedJobs.has(job.id) && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                {job.params && (
                  <div className="text-xs text-gray-600 mb-2">
                    <strong>Params:</strong> {JSON.stringify(job.params, null, 2)}
                  </div>
                )}
                {job.result && (
                  <div className="text-xs text-gray-600 mb-2">
                    <strong>Result:</strong> {JSON.stringify(job.result, null, 2)}
                  </div>
                )}
                {job.error_message && (
                  <div className="text-xs text-red-600">
                    <strong>Error:</strong> {job.error_message}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

