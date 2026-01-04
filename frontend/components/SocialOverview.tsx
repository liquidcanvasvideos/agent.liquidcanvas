'use client'

import { useEffect, useState } from 'react'
import { Users, Mail, CheckCircle, Clock, TrendingUp, AlertCircle, Linkedin, Instagram, Facebook, Music, FileText } from 'lucide-react'
import { getSocialStats, getSocialPipelineStatus, listJobs, type SocialStats, type Job } from '@/lib/api'
import JobStatusPanel from '@/components/JobStatusPanel'
import ActivityFeed from '@/components/ActivityFeed'

interface StatCard {
  title: string
  value: number
  icon: any
  color: string
  bgColor: string
  textColor: string
}

interface PlatformStat {
  platform: string
  icon: any
  total: number
  discovered: number
  drafted: number
  sent: number
  color: string
}

export default function SocialOverview() {
  const [stats, setStats] = useState<SocialStats | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<any>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [jobsLoading, setJobsLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, pipelineData, jobsData] = await Promise.all([
          getSocialStats().catch(() => null),
          getSocialPipelineStatus().catch(() => null),
          listJobs(0, 50).catch(() => [])
        ])
        setStats(statsData)
        setPipelineStatus(pipelineData)
        
        // Filter for social-related jobs
        const socialJobs = Array.isArray(jobsData) ? jobsData.filter((job: Job) => 
          job.job_type?.includes('social') || 
          job.job_type === 'social_discover' ||
          job.job_type === 'social_draft' ||
          job.job_type === 'social_send'
        ) : []
        setJobs(socialJobs)
        setJobsLoading(false)
      } catch (error) {
        console.error('Failed to load social overview data:', error)
      } finally {
        setLoading(false)
      }
    }

    loadData()
    const interval = setInterval(loadData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-olive-600"></div>
          <p className="mt-2 text-sm text-gray-600">Loading social overview...</p>
        </div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="glass rounded-xl shadow-lg p-6 border border-olive-200">
        <p className="text-sm text-gray-600">No social outreach data available</p>
      </div>
    )
  }

  const mainCards: StatCard[] = [
    {
      title: 'Total Profiles',
      value: stats.total_profiles,
      icon: Users,
      color: 'bg-blue-500',
      bgColor: 'bg-blue-50',
      textColor: 'text-blue-700',
    },
    {
      title: 'Discovered',
      value: stats.discovered,
      icon: Users,
      color: 'bg-green-500',
      bgColor: 'bg-green-50',
      textColor: 'text-green-700',
    },
    {
      title: 'Drafted',
      value: stats.drafted,
      icon: FileText,
      color: 'bg-purple-500',
      bgColor: 'bg-purple-50',
      textColor: 'text-purple-700',
    },
    {
      title: 'Sent',
      value: stats.sent,
      icon: CheckCircle,
      color: 'bg-olive-600',
      bgColor: 'bg-olive-50',
      textColor: 'text-olive-700',
    },
    {
      title: 'Pending',
      value: stats.pending,
      icon: Clock,
      color: 'bg-orange-500',
      bgColor: 'bg-orange-50',
      textColor: 'text-orange-700',
    },
    {
      title: 'Jobs Running',
      value: stats.jobs_running,
      icon: AlertCircle,
      color: 'bg-yellow-500',
      bgColor: 'bg-yellow-50',
      textColor: 'text-yellow-700',
    },
  ]

  const platformStats: PlatformStat[] = [
    {
      platform: 'LinkedIn',
      icon: Linkedin,
      total: stats.linkedin_total || 0,
      discovered: stats.linkedin_discovered || 0,
      drafted: stats.linkedin_drafted || 0,
      sent: stats.linkedin_sent || 0,
      color: 'bg-blue-600',
    },
    {
      platform: 'Instagram',
      icon: Instagram,
      total: stats.instagram_total || 0,
      discovered: stats.instagram_discovered || 0,
      drafted: stats.instagram_drafted || 0,
      sent: stats.instagram_sent || 0,
      color: 'bg-pink-600',
    },
    {
      platform: 'Facebook',
      icon: Facebook,
      total: stats.facebook_total || 0,
      discovered: stats.facebook_discovered || 0,
      drafted: stats.facebook_drafted || 0,
      sent: stats.facebook_sent || 0,
      color: 'bg-blue-700',
    },
    {
      platform: 'TikTok',
      icon: Music,
      total: stats.tiktok_total || 0,
      discovered: stats.tiktok_discovered || 0,
      drafted: stats.tiktok_drafted || 0,
      sent: stats.tiktok_sent || 0,
      color: 'bg-black',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Main Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {mainCards.map((card, index) => {
          const Icon = card.icon
          return (
            <div
              key={card.title}
              className="glass rounded-xl shadow-lg border border-white/20 p-3 hover:shadow-xl hover:scale-102 transition-all duration-300 animate-slide-up"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1">{card.title}</p>
                  <p className={`text-lg font-bold text-olive-700`}>{card.value}</p>
                </div>
                <div className={`p-2 rounded-lg shadow-md bg-olive-600`}>
                  <Icon className="w-4 h-4 text-white" />
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Platform-Specific Stats */}
      <div className="glass rounded-xl shadow-lg border border-olive-200 p-6">
        <h3 className="text-sm font-bold text-olive-700 mb-4">Platform Breakdown</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {platformStats.map((platform) => {
            const Icon = platform.icon
            return (
              <div
                key={platform.platform}
                className="glass rounded-lg border border-white/20 p-4 hover:shadow-lg transition-all duration-300"
              >
                <div className="flex items-center space-x-2 mb-3">
                  <div className={`p-2 rounded-lg ${platform.color}`}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <h4 className="text-sm font-semibold text-gray-700">{platform.platform}</h4>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Total:</span>
                    <span className="font-semibold text-olive-700">{platform.total}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Discovered:</span>
                    <span className="font-semibold text-green-700">{platform.discovered}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Drafted:</span>
                    <span className="font-semibold text-purple-700">{platform.drafted}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Sent:</span>
                    <span className="font-semibold text-olive-700">{platform.sent}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Pipeline Summary */}
      {pipelineStatus && (
        <div className="glass rounded-xl shadow-lg border border-olive-200 p-6">
          <h3 className="text-sm font-bold text-olive-700 mb-4">Pipeline Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="text-center">
              <p className="text-xs text-gray-600 mb-1">Discovered</p>
              <p className="text-lg font-bold text-olive-700">{pipelineStatus.discovered || 0}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-600 mb-1">Reviewed</p>
              <p className="text-lg font-bold text-olive-700">{pipelineStatus.reviewed || 0}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-600 mb-1">Qualified</p>
              <p className="text-lg font-bold text-olive-700">{pipelineStatus.qualified || 0}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-600 mb-1">Drafted</p>
              <p className="text-lg font-bold text-olive-700">{pipelineStatus.drafted || 0}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-600 mb-1">Sent</p>
              <p className="text-lg font-bold text-olive-700">{pipelineStatus.sent || 0}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-600 mb-1">Follow-ups</p>
              <p className="text-lg font-bold text-olive-700">{pipelineStatus.followup_ready || 0}</p>
            </div>
          </div>
        </div>
      )}

      {/* Jobs & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {jobsLoading ? (
          <div className="glass rounded-xl shadow-lg border border-olive-200 p-6">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-olive-600"></div>
              <p className="text-gray-500 text-xs mt-2">Loading jobs...</p>
            </div>
          </div>
        ) : jobs.length > 0 ? (
          <JobStatusPanel jobs={jobs} onRefresh={async () => {
            const jobsData = await listJobs(0, 50).catch(() => [])
            const socialJobs = Array.isArray(jobsData) ? jobsData.filter((job: Job) => 
              job.job_type?.includes('social') || 
              job.job_type === 'social_discover' ||
              job.job_type === 'social_draft' ||
              job.job_type === 'social_send'
            ) : []
            setJobs(socialJobs)
          }} />
        ) : (
          <div className="glass rounded-xl shadow-lg border border-olive-200 p-6">
            <p className="text-gray-500 text-sm">No social jobs found.</p>
            <p className="text-gray-400 text-xs mt-1">Start a discovery job to see it here.</p>
          </div>
        )}
        <ActivityFeed limit={15} autoRefresh={true} />
      </div>
    </div>
  )
}

