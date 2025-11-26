'use client'

import { useEffect, useState } from 'react'
import StatsCards from '@/components/StatsCards'
import LeadsTable from '@/components/LeadsTable'
import EmailsTable from '@/components/EmailsTable'
import JobStatusPanel from '@/components/JobStatusPanel'
import ScrapeForm from '@/components/ScrapeForm'
import ActivityFeed from '@/components/ActivityFeed'
import AutomationControl from '@/components/AutomationControl'
import EmailTemplateEditor from '@/components/EmailTemplateEditor'
import DiscoveryControl from '@/components/DiscoveryControl'
import WebsitesTable from '@/components/WebsitesTable'
import SystemStatus from '@/components/SystemStatus'
import { getStats, getLatestJobs } from '@/lib/api'
import type { Stats, LatestJobs } from '@/lib/api'
import { 
  LayoutDashboard, 
  Globe, 
  Users, 
  Mail, 
  Settings, 
  Activity,
  Search,
  Zap,
  XCircle,
  AtSign
} from 'lucide-react'

interface AutomationStatus {
  automation_enabled: boolean
  email_trigger_mode: string
  search_interval_seconds: number
  next_search_time?: string
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [jobs, setJobs] = useState<LatestJobs | null>(null)
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [connectionError, setConnectionError] = useState(false)
  const [activeTab, setActiveTab] = useState<
    'overview' | 'leads' | 'scraped_emails' | 'emails' | 'jobs' | 'websites' | 'settings'
  >('overview')

  useEffect(() => {
    loadData()
    // Refresh every 5 seconds for real-time updates
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [statsData, jobsData, automationData] = await Promise.all([
        getStats().catch(err => {
          console.warn('Failed to get stats:', err.message)
          return null
        }),
        getLatestJobs().catch(err => {
          console.warn('Failed to get jobs:', err.message)
          return null
        }),
        fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1'}/automation/status`)
          .then(r => r.ok ? r.json() : null)
          .catch(() => null)
      ]) as [Stats | null, LatestJobs | null, AutomationStatus | null]
      
      // Only update if we got valid data
      if (statsData) setStats(statsData)
      if (jobsData) setJobs(jobsData)
      if (automationData) setAutomationStatus(automationData)
      
      // Check if backend is actually responding
      const backendResponding = statsData !== null || jobsData !== null || automationData !== null
      setConnectionError(!backendResponding)
    } catch (error: any) {
      console.error('Error loading data:', error)
      const isConnectionError = 
        error.message?.includes('Failed to fetch') || 
        error.message?.includes('ERR_CONNECTION_REFUSED') ||
        error.message?.includes('Request timeout') ||
        error.message?.includes('NetworkError')
      
      if (isConnectionError) {
        setConnectionError(true)
      }
      
      if (!stats) {
        setStats({
          leads_collected: 0,
          emails_extracted: 0,
          phones_extracted: 0,
          social_links_extracted: 0,
          outreach_sent: 0,
          outreach_pending: 0,
          outreach_failed: 0,
          websites_scraped: 0,
          websites_pending: 0,
          websites_failed: 0,
          jobs_completed: 0,
          jobs_running: 0,
          jobs_failed: 0,
          recent_activity: {
            leads_last_24h: 0,
            emails_sent_last_24h: 0,
            websites_scraped_last_24h: 0
          }
        })
      }
      
      if (!jobs) {
        setJobs({})
      }
    } finally {
      setLoading(false)
    }
  }

  const refreshData = () => {
    loadData()
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'websites', label: 'Websites', icon: Globe },
    { id: 'leads', label: 'Leads', icon: Users },
    { id: 'scraped_emails', label: 'Scraped Emails', icon: AtSign },
    { id: 'emails', label: 'Outreach Emails', icon: Mail },
    { id: 'jobs', label: 'Jobs', icon: Activity },
    { id: 'settings', label: 'Settings', icon: Settings },
  ]

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-purple-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-indigo-600 border-t-transparent mb-4"></div>
          <div className="text-xl font-semibold text-gray-900">Loading dashboard...</div>
          <div className="text-sm text-gray-600 mt-2">Connecting to backend...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-indigo-50/30 to-purple-50/30">
      {/* Modern Header */}
      <header className="bg-white/80 backdrop-blur-lg shadow-sm border-b border-gray-200/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                Art Outreach Scraper
              </h1>
              <p className="text-gray-600 mt-1 text-sm">
                Autonomous website discovery and outreach automation
              </p>
            </div>
            <div className="flex items-center space-x-3">
              {automationStatus?.automation_enabled && (
                <div className="flex items-center space-x-2 bg-green-50 border border-green-200 rounded-full px-4 py-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm font-medium text-green-800">Active</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Connection Error Banner */}
      {connectionError && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className="bg-red-50 border-l-4 border-red-500 rounded-lg p-4 shadow-sm">
            <div className="flex items-center">
              <XCircle className="h-5 w-5 text-red-500 mr-3" />
              <div>
                <p className="text-sm font-medium text-red-800">
                  Backend not connected
                </p>
                <p className="text-xs text-red-600 mt-1">
                  Unable to connect to API server. Please ensure the FastAPI backend is running.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* System Status Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <SystemStatus 
          automationStatus={automationStatus}
          jobs={jobs}
          loading={loading}
        />
      </div>

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="bg-white/60 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200/50 p-2">
          <nav className="flex space-x-2">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`
                    flex items-center space-x-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all
                    ${
                      activeTab === tab.id
                        ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md'
                        : 'text-gray-700 hover:bg-gray-100/80'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {stats ? <StatsCards stats={stats} /> : (
              <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200/50 p-6">
                <p className="text-gray-500">Stats unavailable. Check backend connection.</p>
              </div>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ScrapeForm onScrape={refreshData} />
              {jobs ? <JobStatusPanel jobs={jobs} /> : (
                <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200/50 p-6">
                  <p className="text-gray-500">Job status unavailable.</p>
                </div>
              )}
            </div>
            <ActivityFeed limit={20} autoRefresh={true} />
          </div>
        )}

        {activeTab === 'websites' && <WebsitesTable />}

        {activeTab === 'leads' && <LeadsTable />}

        {activeTab === 'scraped_emails' && <LeadsTable emailsOnly />}

        {activeTab === 'emails' && <EmailsTable />}

        {activeTab === 'jobs' && jobs && <JobStatusPanel jobs={jobs} expanded />}

        {activeTab === 'settings' && (
          <div className="space-y-6">
            <AutomationControl />
            <DiscoveryControl />
            <EmailTemplateEditor />
          </div>
        )}
      </main>
    </div>
  )
}
