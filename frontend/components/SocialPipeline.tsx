'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Lock, Loader2, Search, Eye, FileText, Send, RefreshCw, ArrowRight, AlertCircle, Users, Linkedin, Instagram, Facebook, Music } from 'lucide-react'
import { 
  getSocialPipelineStatus,
  discoverSocialProfilesPipeline,
  reviewSocialProfiles,
  draftSocialProfiles,
  sendSocialProfiles,
  createSocialFollowupsPipeline,
  isMasterSwitchEnabled,
  type SocialPipelineStatus
} from '@/lib/api'

interface StepCard {
  id: number
  name: string
  description: string
  icon: any
  status: 'pending' | 'active' | 'completed' | 'locked'
  count: number
  ctaText: string
  ctaAction: () => void
}

type Platform = 'all' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok'

export default function SocialPipeline() {
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('all')
  const [status, setStatus] = useState<SocialPipelineStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [discoveryLoading, setDiscoveryLoading] = useState(false)
  const [masterSwitchEnabled, setMasterSwitchEnabled] = useState(false)

  // Check master switch status
  useEffect(() => {
    const checkMasterSwitch = () => {
      const enabled = isMasterSwitchEnabled()
      setMasterSwitchEnabled(enabled)
    }
    
    // Check on mount
    checkMasterSwitch()
    
    // Listen for changes
    const handleMasterSwitchChange = (e: CustomEvent) => {
      setMasterSwitchEnabled(e.detail.enabled)
    }
    
    window.addEventListener('masterSwitchChanged', handleMasterSwitchChange as EventListener)
    
    return () => {
      window.removeEventListener('masterSwitchChanged', handleMasterSwitchChange as EventListener)
    }
  }, [])

  const loadStatus = async () => {
    try {
      const platform = selectedPlatform === 'all' ? undefined : selectedPlatform
      const pipelineStatus = await getSocialPipelineStatus(platform)
      setStatus(pipelineStatus)
    } catch (error) {
      console.error('Failed to load social pipeline status:', error)
      // Set default status on error
      setStatus({
        discovered: 0,
        reviewed: 0,
        qualified: 0,
        drafted: 0,
        sent: 0,
        followup_ready: 0,
        status: 'inactive'
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let abortController = new AbortController()
    let debounceTimeout: NodeJS.Timeout | null = null
    
    const loadStatusDebounced = () => {
      abortController.abort()
      abortController = new AbortController()
      
      if (debounceTimeout) {
        clearTimeout(debounceTimeout)
      }
      
      debounceTimeout = setTimeout(() => {
        loadStatus()
      }, 300)
    }
    
    // Initial load
    loadStatusDebounced()
    
    // Refresh every 10 seconds
    const interval = setInterval(() => {
      loadStatusDebounced()
    }, 10000)
    
    // Listen for manual refresh requests
    const handleRefresh = () => {
      loadStatusDebounced()
    }
    
    if (typeof window !== 'undefined') {
      window.addEventListener('refreshSocialPipelineStatus', handleRefresh)
    }
    
    return () => {
      abortController.abort()
      if (debounceTimeout) {
        clearTimeout(debounceTimeout)
      }
      clearInterval(interval)
      if (typeof window !== 'undefined') {
        window.removeEventListener('refreshSocialPipelineStatus', handleRefresh)
      }
    }
  }, [selectedPlatform]) // Reload when platform changes

  const handleDiscover = async () => {
    // Discovery is handled in the discovery component
    // This is just a placeholder
  }

  const handleReview = async () => {
    // Review is handled in the profiles table
    // This is just a placeholder
  }

  const handleDraft = async () => {
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    try {
      // Get qualified profiles - this would come from the profiles table
      // For now, this is a placeholder
      alert('Drafting is handled from the Profiles tab. Select qualified profiles and click "Draft".')
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to create drafts')
    }
  }

  const handleSend = async () => {
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    try {
      // Get drafted profiles - this would come from the profiles table
      // For now, this is a placeholder
      alert('Sending is handled from the Profiles tab. Select drafted profiles and click "Send".')
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to send messages')
    }
  }

  const handleFollowup = async () => {
    if (!masterSwitchEnabled) {
      alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
      return
    }
    try {
      // Get sent profiles - this would come from the profiles table
      // For now, this is a placeholder
      alert('Follow-ups are handled from the Profiles tab. Select sent profiles and click "Create Follow-up".')
      await loadStatus()
    } catch (err: any) {
      alert(err.message || 'Failed to create follow-ups')
    }
  }

  if (loading) {
    return (
      <div className="glass rounded-xl shadow-lg p-4 animate-fade-in">
        <div className="text-center py-4">
          <div className="relative inline-block">
            <div className="w-8 h-8 rounded-full border-2 border-olive-200"></div>
            <div className="absolute top-0 left-0 w-8 h-8 rounded-full border-2 border-t-olive-600 border-r-olive-500 animate-spin"></div>
          </div>
          <p className="text-gray-600 mt-2 text-sm font-medium">Loading pipeline...</p>
        </div>
      </div>
    )
  }

  // Only show inactive message if status explicitly says inactive AND has a reason
  // If status is null or missing, show loading or default state
  if (status && status.status === 'inactive' && status.reason) {
    return (
      <div className="glass rounded-xl shadow-lg p-6 border border-olive-200">
        <div className="flex items-center space-x-2 text-amber-600 mb-2">
          <AlertCircle className="w-5 h-5" />
          <h3 className="font-semibold text-sm">Social Outreach Not Available</h3>
        </div>
        <p className="text-xs text-gray-600">
          {status.reason}
        </p>
      </div>
    )
  }
  
  // If status is null, show loading
  if (!status) {
    return (
      <div className="glass rounded-xl shadow-lg p-4 animate-fade-in">
        <div className="text-center py-4">
          <div className="relative inline-block">
            <div className="w-8 h-8 rounded-full border-2 border-olive-200"></div>
            <div className="absolute top-0 left-0 w-8 h-8 rounded-full border-2 border-t-olive-600 border-r-olive-500 animate-spin"></div>
          </div>
          <p className="text-gray-600 mt-2 text-sm font-medium">Loading pipeline...</p>
        </div>
      </div>
    )
  }

  const platforms = [
    { id: 'all' as Platform, label: 'All Platforms', icon: Users },
    { id: 'linkedin' as Platform, label: 'LinkedIn', icon: Linkedin },
    { id: 'instagram' as Platform, label: 'Instagram', icon: Instagram },
    { id: 'facebook' as Platform, label: 'Facebook', icon: Facebook },
    { id: 'tiktok' as Platform, label: 'TikTok', icon: Music },
  ]

  const steps: StepCard[] = [
    {
      id: 1,
      name: 'Profile Discovery',
      description: 'Discover social media profiles',
      icon: Search,
      status: status.discovered > 0 ? 'completed' : 'active', // Always unlocked
      count: status.discovered,
      ctaText: status.discovered > 0 ? 'View Profiles' : 'Start Discovery',
      ctaAction: () => {
        if (!masterSwitchEnabled) {
          alert('Master switch is disabled. Please enable it in Automation Control to run pipeline activities.')
          return
        }
        if (status.discovered > 0) {
          const event = new CustomEvent('change-tab', { detail: 'profiles' })
          window.dispatchEvent(event)
        } else {
          const event = new CustomEvent('change-tab', { detail: 'discover' })
          window.dispatchEvent(event)
        }
      }
    },
    {
      id: 2,
      name: 'Profile Review',
      description: 'Review and qualify profiles',
      icon: Eye,
      status: status.discovered === 0 ? 'locked' :
              status.reviewed > 0 ? 'completed' : 'active',
      count: status.reviewed,
      ctaText: status.discovered === 0 ? 'Discover Profiles First' :
               status.reviewed > 0 ? 'View Reviewed' : 'Review Profiles',
      ctaAction: () => {
        if (status.discovered === 0) {
          const event = new CustomEvent('change-tab', { detail: 'discover' })
          window.dispatchEvent(event)
          return
        }
        const event = new CustomEvent('change-tab', { detail: 'profiles' })
        window.dispatchEvent(event)
      }
    },
    {
      id: 3,
      name: 'Drafting',
      description: 'Create outreach messages',
      icon: FileText,
      status: status.qualified === 0 ? 'locked' :
              status.drafted > 0 ? 'completed' : 'active',
      count: status.drafted,
      ctaText: status.qualified === 0 ? 'Review Profiles First' :
               status.drafted > 0 ? 'View Drafts' : 'Start Drafting',
      ctaAction: () => {
        if (status.qualified === 0) {
          alert('Please review and qualify profiles first')
          return
        }
        handleDraft()
      }
    },
    {
      id: 4,
      name: 'Sending',
      description: 'Send messages to profiles',
      icon: Send,
      status: status.drafted === 0 ? 'locked' :
              status.sent > 0 ? 'completed' : 'active',
      count: status.sent,
      ctaText: status.drafted === 0 ? 'Create Drafts First' :
               status.sent > 0 ? 'View Sent' : 'Start Sending',
      ctaAction: () => {
        if (status.drafted === 0) {
          alert('Please create drafts first')
          return
        }
        handleSend()
      }
    },
    {
      id: 5,
      name: 'Follow-ups',
      description: 'Create follow-up messages',
      icon: RefreshCw,
      status: status.sent === 0 ? 'locked' :
              status.followup_ready > 0 ? 'active' : 'locked',
      count: status.followup_ready,
      ctaText: status.sent === 0 ? 'Send Messages First' : 'Create Follow-ups',
      ctaAction: () => {
        if (status.sent === 0) {
          alert('Please send messages first')
          return
        }
        handleFollowup()
      }
    }
  ]

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Platform Selector */}
      <div className="glass rounded-xl shadow-lg p-3 border border-olive-200">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-bold text-olive-700 mb-1">Social Outreach Pipeline</h2>
            <p className="text-gray-600 text-xs">
              {selectedPlatform === 'all' 
                ? 'View all platforms or filter by specific platform'
                : `Viewing ${platforms.find(p => p.id === selectedPlatform)?.label} pipeline`}
            </p>
          </div>
          <button
            onClick={loadStatus}
            className="flex items-center space-x-1 px-2 py-1 bg-olive-600 text-white rounded-lg transition-all duration-200 text-xs font-medium hover:bg-olive-700 hover:shadow-md"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>
        
        {/* Platform Tabs */}
        <div className="flex flex-wrap gap-2">
          {platforms.map((platform) => {
            const Icon = platform.icon
            const isSelected = selectedPlatform === platform.id
            return (
              <button
                key={platform.id}
                onClick={() => setSelectedPlatform(platform.id)}
                className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                  isSelected
                    ? 'bg-olive-600 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-olive-50 border border-gray-200'
                }`}
              >
                <Icon className="w-3 h-3" />
                <span>{platform.label}</span>
              </button>
            )
          })}
        </div>
        {!masterSwitchEnabled && (
          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-600" />
              <p className="text-xs text-red-700">
                <span className="font-semibold">Master switch is OFF</span> — Enable it in Automation Control to use pipeline activities.
              </p>
            </div>
          </div>
        )}
        {masterSwitchEnabled && (
          <div className="mt-2 p-2 bg-gradient-to-r from-olive-50 to-olive-50 rounded-lg border border-olive-200">
            <p className="text-xs text-gray-700">
              <span className="font-semibold">Orchestrate your social outreach</span> — Each stage builds on the previous, creating meaningful connections through art and creativity.
            </p>
          </div>
        )}
      </div>

      {/* Step Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {steps.map((step, index) => {
          const Icon = step.icon
          const isCompleted = step.status === 'completed'
          const isLocked = step.status === 'locked'
          const isActive = step.status === 'active'
          
          return (
            <div
              key={step.id}
              className={`glass rounded-xl shadow-lg p-3 border transition-all duration-300 hover:shadow-xl hover:scale-102 animate-slide-up ${
                isCompleted
                  ? 'border-olive-300 bg-gradient-to-br from-olive-50/80 to-olive-50/50'
                  : isLocked
                  ? 'border-gray-200 opacity-60'
                  : 'border-olive-300 bg-gradient-to-br from-olive-50/80 to-olive-50/50'
              }`}
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="flex items-start justify-between mb-2">
                <div className={`p-2 rounded-lg shadow-md transition-all duration-300 ${
                  isCompleted
                    ? 'bg-olive-600 text-white'
                    : isLocked
                    ? 'bg-gray-300 text-gray-500'
                    : 'bg-olive-600 text-white hover-glow'
                }`}>
                  <Icon className="w-4 h-4" />
                </div>
                {isCompleted && (
                  <CheckCircle2 className="w-4 h-4 text-olive-600 animate-scale-in" />
                )}
                {isLocked && (
                  <Lock className="w-4 h-4 text-gray-400" />
                )}
              </div>

              <h3 className="text-sm font-bold text-gray-900 mb-1">{step.name}</h3>
              <p className="text-xs text-gray-600 mb-2">{step.description}</p>

              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-lg font-bold text-olive-700">{step.count}</p>
                  <p className="text-xs text-gray-500">
                    {step.id === 1 && `${status.discovered} discovered`}
                    {step.id === 2 && `${status.reviewed} reviewed • ${status.qualified} qualified`}
                    {step.id === 3 && `${status.drafted} drafted`}
                    {step.id === 4 && `${status.sent} sent`}
                    {step.id === 5 && `${status.followup_ready} ready for follow-up`}
                  </p>
                </div>
              </div>

              <button
                onClick={step.ctaAction}
                disabled={isLocked}
                className={`w-full px-2 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center space-x-1 transition-all duration-200 ${
                  isLocked
                    ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                    : isCompleted
                    ? 'bg-olive-600 text-white hover:bg-olive-700 hover:shadow-md hover:scale-102'
                    : 'bg-olive-600 text-white hover:bg-olive-700 hover:shadow-md hover:scale-102'
                }`}
              >
                <span>{step.ctaText}</span>
                {!isLocked && <ArrowRight className="w-3 h-3" />}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

