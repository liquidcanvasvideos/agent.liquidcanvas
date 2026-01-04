'use client'

import { useState } from 'react'
import { CheckCircle, XCircle, Clock, Loader, ChevronDown, ChevronUp, Search, Globe, Mail, Filter, X } from 'lucide-react'
import { cancelJob, type Job } from '@/lib/api'

interface JobStatusPanelProps {
  jobs: Job[]
  expanded?: boolean
  onRefresh?: () => void
}

export default function JobStatusPanel({ jobs, expanded = false, onRefresh }: JobStatusPanelProps) {
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set())
  const [cancellingJobs, setCancellingJobs] = useState<Set<string>>(new Set())
  const [showCancelModal, setShowCancelModal] = useState<{ show: boolean; jobId: string | null }>({ show: false, jobId: null })

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
    setShowCancelModal({ show: true, jobId })
  }

  const confirmCancelJob = async () => {
    if (!showCancelModal.jobId) return
    
    const jobId = showCancelModal.jobId
    setCancellingJobs(prev => new Set(prev).add(jobId))
    setShowCancelModal({ show: false, jobId: null })
    
    try {
      await cancelJob(jobId)
      console.log(`✅ Job ${jobId} cancelled successfully`)
      // Trigger refresh if callback provided
      if (onRefresh) {
        onRefresh()
      } else {
        // Fallback: dispatch event to refresh
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('jobsCompleted'))
        }
      }
    } catch (error: any) {
      console.error(`❌ Failed to cancel job ${jobId}:`, error)
      alert(`Failed to cancel job: ${error.message || 'Unknown error'}`)
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
    // Support both website discovery ('discover') and social discovery ('social_discover')
    if ((job.job_type !== 'discover' && job.job_type !== 'social_discover') || !job.result) return null

    const result = job.result as any
    const stats = result.search_statistics || result
    const queries = Array.isArray(result.queries_detail) ? result.queries_detail : []
    const isSocial = job.job_type === 'social_discover'

    return (
      <div className="mt-3 space-y-3 pt-3 border-t border-gray-200">
        {/* Summary Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="glass rounded-xl p-2 border border-blue-200/50 shadow-sm">
              <div className="text-xs text-blue-600 font-semibold mb-1">Queries Executed</div>
              <div className="text-lg font-bold text-olive-700">{stats.queries_executed || 0}</div>
            </div>
            <div className="glass rounded-xl p-2 border border-green-200/50 shadow-sm">
              <div className="text-xs text-green-600 font-semibold mb-1">Results Found</div>
              <div className="text-lg font-bold text-green-700">{stats.total_results_found || 0}</div>
            </div>
            <div className="glass rounded-xl p-2 border border-purple-200/50 shadow-sm">
              <div className="text-xs text-purple-600 font-semibold mb-1">Prospects Saved</div>
              <div className="text-lg font-bold text-purple-700">{stats.results_saved || 0}</div>
            </div>
            <div className="glass rounded-xl p-2 border border-orange-200/50 shadow-sm">
              <div className="text-xs text-orange-600 font-semibold mb-1">Skipped</div>
              <div className="text-lg font-bold text-orange-700">
                {(stats.results_skipped_duplicate || 0) + (stats.results_skipped_existing || 0)}
              </div>
            </div>
          </div>
        )}

        {/* Detailed Stats */}
        {stats && (
          <div className="glass rounded-xl p-2 border border-gray-200/50 shadow-sm space-y-1 text-xs">
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
                <div key={idx} className="text-xs glass rounded-xl p-3 border border-gray-200/50 shadow-sm">
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
        {stats && stats.total_results_found === 0 && !isSocial && (
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-300 rounded-xl p-2 shadow-sm">
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

        {/* Social Discovery Specific Info */}
        {isSocial && job.params && (
          <div className="bg-blue-50 rounded-lg p-3 space-y-2 text-xs">
            <div className="flex items-center space-x-2 text-blue-700 font-medium mb-2">
              <Search className="w-3 h-3" />
              <span>Social Discovery Parameters</span>
            </div>
            {job.params.platform && (
              <div>
                <span className="text-gray-600">Platform:</span>
                <span className="ml-1 font-medium capitalize">{job.params.platform}</span>
              </div>
            )}
            {job.params.categories && job.params.categories.length > 0 && (
              <div>
                <span className="text-gray-600">Categories:</span>
                <span className="ml-1 font-medium">{job.params.categories.join(', ')}</span>
              </div>
            )}
            {job.params.locations && job.params.locations.length > 0 && (
              <div>
                <span className="text-gray-600">Locations:</span>
                <span className="ml-1 font-medium">{job.params.locations.join(', ')}</span>
              </div>
            )}
            {job.params.keywords && job.params.keywords.length > 0 && (
              <div>
                <span className="text-gray-600">Keywords:</span>
                <span className="ml-1 font-medium">{job.params.keywords.join(', ')}</span>
              </div>
            )}
            {result.prospects_count !== undefined && (
              <div>
                <span className="text-gray-600">Profiles Discovered:</span>
                <span className="ml-1 font-medium text-green-700">{result.prospects_count || 0}</span>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  // Ensure jobs is always an array
  const jobsArray = Array.isArray(jobs) ? jobs : []
  const displayJobs = expanded ? jobsArray : jobsArray.slice(0, 5)

  return (
    <div className="glass rounded-xl shadow-lg border border-white/20 p-3 animate-fade-in">
      <h2 className="text-sm font-bold text-olive-700 mb-3">Recent Jobs</h2>
      {displayJobs.length === 0 ? (
        <p className="text-gray-500 text-sm">No jobs found</p>
      ) : (
        <div className="space-y-3">
          {displayJobs.map((job) => {
            const isExpanded = expandedJobs.has(job.id)
            return (
              <div
                key={job.id}
                className="glass rounded-lg p-2 border border-white/20 hover:bg-white/60 hover:shadow-md transition-all duration-200"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(job.status)}
                    <span className="font-semibold text-gray-900 capitalize">{job.job_type}</span>
                    <span className={`px-3 py-1 rounded-lg text-xs font-semibold shadow-sm ${
                      job.status === 'completed' ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white' :
                      job.status === 'failed' ? 'bg-gradient-to-r from-red-500 to-pink-600 text-white' :
                      job.status === 'running' ? 'bg-gradient-to-r from-yellow-400 to-amber-500 text-white' :
                      'bg-gray-200 text-gray-700'
                    }`}>
                      {job.status}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-500">{formatDate(job.created_at)}</span>
                    {(job.status === 'running' || job.status === 'pending') && (
                      <button
                        onClick={() => handleCancelJob(job.id)}
                        disabled={cancellingJobs.has(job.id)}
                        className="px-3 py-1 text-xs font-semibold text-red-600 hover:text-red-800 hover:bg-red-50 rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 hover:scale-105"
                        title="Cancel this job"
                      >
                        <X className="w-3 h-3" />
                        {cancellingJobs.has(job.id) ? 'Cancelling...' : 'Cancel'}
                      </button>
                    )}
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
                {!isExpanded && job.result && (job.job_type === 'discover' || job.job_type === 'social_discover') && (
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
      
      {/* Cancel Confirmation Modal */}
      {showCancelModal.show && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-3 max-w-md w-full mx-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">Cancel Job?</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to cancel this job? This will stop the discovery process, but it will NOT delete any prospects that have already been saved.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowCancelModal({ show: false, jobId: null })}
                className="px-3 py-1.5 text-xs text-gray-700 glass hover:bg-white/80 rounded-lg transition-all duration-200 font-semibold"
              >
                No, Keep Running
              </button>
              <button
                onClick={confirmCancelJob}
                className="px-3 py-1.5 text-xs text-white bg-gradient-to-r from-red-500 to-pink-600 rounded-lg hover:shadow-md hover:scale-102 transition-all duration-200 font-semibold shadow-md"
              >
                Yes, Cancel Job
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

