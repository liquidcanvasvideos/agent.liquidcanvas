'use client'

import { useState } from 'react'
import { CheckCircle, XCircle, Clock, Loader, ChevronDown, ChevronUp, Search, Globe, Mail, Filter } from 'lucide-react'
import type { Job } from '@/lib/api'

interface JobStatusPanelProps {
  jobs: Job[]
  expanded?: boolean
}

export default function JobStatusPanel({ jobs, expanded = false }: JobStatusPanelProps) {
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set())

  const toggleJob = (jobId: string) => {
    const newExpanded = new Set(expandedJobs)
    if (newExpanded.has(jobId)) {
      newExpanded.delete(jobId)
    } else {
      newExpanded.add(jobId)
    }
    setExpandedJobs(newExpanded)
  }

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

  const renderDiscoveryJobDetails = (job: Job) => {
    if (job.job_type !== 'discover' || !job.result) return null

    const result = job.result as any
    const stats = result.search_statistics
    const queries = Array.isArray(result.queries_detail) ? result.queries_detail : []

    return (
      <div className="mt-3 space-y-3 pt-3 border-t border-gray-200">
        {/* Summary Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="bg-blue-50 rounded p-2">
              <div className="text-xs text-blue-600 font-medium">Queries Executed</div>
              <div className="text-lg font-bold text-blue-900">{stats.queries_executed || 0}</div>
            </div>
            <div className="bg-green-50 rounded p-2">
              <div className="text-xs text-green-600 font-medium">Results Found</div>
              <div className="text-lg font-bold text-green-900">{stats.total_results_found || 0}</div>
            </div>
            <div className="bg-purple-50 rounded p-2">
              <div className="text-xs text-purple-600 font-medium">Prospects Saved</div>
              <div className="text-lg font-bold text-purple-900">{stats.results_saved || 0}</div>
            </div>
            <div className="bg-orange-50 rounded p-2">
              <div className="text-xs text-orange-600 font-medium">Skipped</div>
              <div className="text-lg font-bold text-orange-900">
                {(stats.results_skipped_duplicate || 0) + (stats.results_skipped_existing || 0)}
              </div>
            </div>
          </div>
        )}

        {/* Detailed Stats */}
        {stats && (
          <div className="bg-gray-50 rounded-lg p-3 space-y-2 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-gray-600">Successful Queries:</span>
                <span className="font-semibold ml-1 text-green-700">{stats.queries_successful || 0}</span>
              </div>
              <div>
                <span className="text-gray-600">Failed Queries:</span>
                <span className="font-semibold ml-1 text-red-700">{stats.queries_failed || 0}</span>
              </div>
              <div>
                <span className="text-gray-600">Skipped (Duplicates):</span>
                <span className="font-semibold ml-1">{stats.results_skipped_duplicate || 0}</span>
              </div>
              <div>
                <span className="text-gray-600">Skipped (Existing):</span>
                <span className="font-semibold ml-1">{stats.results_skipped_existing || 0}</span>
              </div>
            </div>
          </div>
        )}

        {/* Search Parameters */}
        <div className="bg-gray-50 rounded-lg p-3 space-y-2 text-xs">
          <div className="flex items-center space-x-2 text-gray-700 font-medium mb-2">
            <Filter className="w-3 h-3" />
            <span>Search Parameters</span>
          </div>
          {result.locations && result.locations.length > 0 && (
            <div className="flex items-start space-x-2">
              <Globe className="w-3 h-3 text-gray-500 mt-0.5" />
              <div>
                <span className="text-gray-600">Locations:</span>
                <span className="ml-1 font-medium">{result.locations.join(', ')}</span>
              </div>
            </div>
          )}
          {result.categories && result.categories.length > 0 && (
            <div className="flex items-start space-x-2">
              <Filter className="w-3 h-3 text-gray-500 mt-0.5" />
              <div>
                <span className="text-gray-600">Categories:</span>
                <span className="ml-1 font-medium">{result.categories.join(', ')}</span>
              </div>
            </div>
          )}
          {result.keywords && (
            <div className="flex items-start space-x-2">
              <Search className="w-3 h-3 text-gray-500 mt-0.5" />
              <div>
                <span className="text-gray-600">Keywords:</span>
                <span className="ml-1 font-medium">{result.keywords || 'None'}</span>
              </div>
            </div>
          )}
        </div>

        {/* Query Details */}
        {queries.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="flex items-center space-x-2 text-gray-700 font-medium mb-2 text-xs">
              <Search className="w-3 h-3" />
              <span>Query Details ({queries.length} shown)</span>
            </div>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {queries.slice(0, 10).map((q: any, idx: number) => (
                <div key={idx} className="text-xs bg-white rounded p-2 border border-gray-200">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-800">&quot;{q.query}&quot;</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      q.status === 'success' ? 'bg-green-100 text-green-700' :
                      q.status === 'failed' ? 'bg-red-100 text-red-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {q.status}
                    </span>
                  </div>
                  {q.status === 'success' && (
                    <div className="mt-1 text-gray-600">
                      Found: {q.results_found || 0} | Saved: {q.results_saved || 0}
                    </div>
                  )}
                  {q.error && (
                    <div className="mt-1 text-red-600 text-xs">Error: {q.error}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warning if no results */}
        {stats && stats.total_results_found === 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            <div className="text-xs text-yellow-800">
              <strong>⚠️ No websites found:</strong> The search queries didn&apos;t return any results from DataForSEO.
              This could mean:
              <ul className="list-disc list-inside mt-1 space-y-0.5">
                <li>No websites match your search criteria</li>
                <li>DataForSEO API returned no results for these queries</li>
                <li>All results were filtered out as duplicates or existing</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    )
  }

  // Ensure jobs is always an array
  const jobsArray = Array.isArray(jobs) ? jobs : []
  const displayJobs = expanded ? jobsArray : jobsArray.slice(0, 5)

  return (
    <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg border-2 border-gray-200/60 p-6">
      <h2 className="text-lg font-bold text-gray-900 mb-4">Recent Jobs</h2>
      {displayJobs.length === 0 ? (
        <p className="text-gray-500 text-sm">No jobs found</p>
      ) : (
        <div className="space-y-3">
          {displayJobs.map((job) => {
            const isExpanded = expandedJobs.has(job.id)
            return (
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
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-500">{formatDate(job.created_at)}</span>
                    {job.result && (
                      <button
                        onClick={() => toggleJob(job.id)}
                        className="text-gray-500 hover:text-gray-700"
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    )}
                  </div>
                </div>
                {job.error_message && (
                  <p className="text-sm text-red-600 mt-2">{job.error_message}</p>
                )}
                {isExpanded && renderDiscoveryJobDetails(job)}
                {!isExpanded && job.result && job.job_type === 'discover' && (
                  <button
                    onClick={() => toggleJob(job.id)}
                    className="text-xs text-blue-600 hover:text-blue-800 mt-2"
                  >
                    Click to view detailed statistics
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

