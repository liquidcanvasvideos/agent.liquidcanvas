'use client'

import { useState, useEffect } from 'react'
import { RefreshCw, ExternalLink, CheckCircle, XCircle, Eye, Download } from 'lucide-react'
import { 
  listSocialProfiles, 
  reviewSocialProfiles,
  exportSocialProfilesCSV
} from '@/lib/api'

interface SocialProfile {
  id: string
  platform: string
  username: string
  full_name?: string
  profile_url: string
  bio?: string
  followers_count: number
  location?: string
  category?: string
  engagement_score: number
  contact_email?: string
  discovery_status: string
  outreach_status: string
  created_at: string
}

type Platform = 'all' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok'

export default function SocialDiscoveredProfilesTable() {
  const [profiles, setProfiles] = useState<SocialProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actionLoading, setActionLoading] = useState(false)
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('all')
  
  const platformIcons = {
    linkedin: '💼',
    instagram: '📷',
    facebook: '👥',
    tiktok: '🎵',
  }

  const loadProfiles = async () => {
    try {
      setLoading(true)
      setError(null)
      const platform = selectedPlatform === 'all' ? undefined : selectedPlatform
      // List only PENDING profiles (discovered but not yet accepted/rejected)
      const response = await listSocialProfiles(0, 1000, platform, 'discovered')
      
      // CRITICAL DIAGNOSTIC LOGGING
      console.log('🔍 [DISCOVERED TAB] RAW API RESPONSE:', response)
      console.log('🔍 [DISCOVERED TAB] response.data:', response.data)
      console.log('🔍 [DISCOVERED TAB] typeof response.data:', typeof response.data)
      console.log('🔍 [DISCOVERED TAB] Array.isArray(response.data):', Array.isArray(response.data))
      console.log('🔍 [DISCOVERED TAB] response.data?.length:', response.data?.length)
      console.log('🔍 [DISCOVERED TAB] response.total:', response.total)
      console.log('🔍 [DISCOVERED TAB] response keys:', response && Object.keys(response))
      if (response.data && response.data.length > 0) {
        console.log('🔍 [DISCOVERED TAB] First item:', response.data[0])
      }

      const profilesArray: SocialProfile[] = Array.isArray((response as any)?.data)
        ? ((response as any).data as SocialProfile[])
        : Array.isArray((response as any)?.data?.data)
          ? (((response as any).data.data) as SocialProfile[])
          : Array.isArray((response as any)?.data?.profiles)
            ? (((response as any).data.profiles) as SocialProfile[])
            : []

      setProfiles(profilesArray)
    } catch (err: any) {
      console.error('Failed to load discovered profiles:', err)
      setError(err.message || 'Failed to load discovered profiles')
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProfiles()
  }, [selectedPlatform])

  const handleSelect = (id: string) => {
    const newSelected = new Set(selected)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelected(newSelected)
  }

  const handleAccept = async () => {
    if (selected.size === 0) {
      setError('Please select at least one profile to accept')
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      await reviewSocialProfiles(Array.from(selected), 'qualify')
      setSelected(new Set())
      
      // Initial refresh
      await loadProfiles()
      
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
        // Also trigger a refresh for Social Leads tab
        window.dispatchEvent(new CustomEvent('refreshSocialLeads'))
      }
      
      // Poll for updates (scraping happens in background)
      // Refresh every 2 seconds for up to 30 seconds to catch scraping updates
      let pollCount = 0
      const maxPolls = 15 // 15 * 2 seconds = 30 seconds
      const pollInterval = setInterval(async () => {
        pollCount++
        await loadProfiles()
        
        if (pollCount >= maxPolls) {
          clearInterval(pollInterval)
        }
      }, 2000) // Poll every 2 seconds
      
      // Clear interval after 30 seconds
      setTimeout(() => {
        clearInterval(pollInterval)
      }, 30000)
      
    } catch (err: any) {
      setError(err.message || 'Failed to accept profiles')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (selected.size === 0) {
      setError('Please select at least one profile to reject')
      return
    }

    if (!confirm(`Reject ${selected.size} profile(s)? This action cannot be undone.`)) {
      return
    }

    setActionLoading(true)
    setError(null)
    try {
      await reviewSocialProfiles(Array.from(selected), 'reject')
      setSelected(new Set())
      await loadProfiles()
      // Refresh pipeline status
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to reject profiles')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-olive-600" />
        <p className="text-xs text-gray-600 mt-2">Loading discovered profiles...</p>
      </div>
    )
  }

  const platforms = [
    { id: 'all' as Platform, label: 'All Platforms' },
    { id: 'linkedin' as Platform, label: 'LinkedIn' },
    { id: 'instagram' as Platform, label: 'Instagram' },
    { id: 'facebook' as Platform, label: 'Facebook' },
    { id: 'tiktok' as Platform, label: 'TikTok' },
  ]

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Discovered Profiles</h2>
          <p className="text-xs text-gray-500 mt-1">Review and accept/reject discovered profiles. Only qualified profiles (≥1,000 followers, minimum engagement rate) appear here.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {selected.size > 0 && (
            <>
              <button
                onClick={handleAccept}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-1"
              >
                <CheckCircle className="w-3 h-3" />
                Accept ({selected.size})
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-1"
              >
                <XCircle className="w-3 h-3" />
                Reject ({selected.size})
              </button>
            </>
          )}
          <button
            onClick={async () => {
              try {
                const blob = await exportSocialProfilesCSV()
                const url = window.URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `discovered_profiles_${new Date().toISOString().split('T')[0]}.csv`
                document.body.appendChild(a)
                a.click()
                window.URL.revokeObjectURL(url)
                document.body.removeChild(a)
              } catch (error: any) {
                alert(`Failed to export CSV: ${error.message}`)
              }
            }}
            className="px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-1"
          >
            <Download className="w-3 h-3" />
            Download CSV
          </button>
          <button
            onClick={loadProfiles}
            className="px-3 py-1.5 text-xs bg-gray-600 text-white rounded-lg hover:bg-gray-700 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      </div>

      {/* Platform-Specific Tabs */}
      <div className="mb-4 flex items-center space-x-2 border-b border-olive-200">
        {platforms.map((platform) => (
          <button
            key={platform.id}
            onClick={() => setSelectedPlatform(platform.id)}
            className={`px-4 py-2 rounded-t-lg text-xs font-semibold transition-all border-b-2 ${
              selectedPlatform === platform.id
                ? 'bg-olive-50 text-olive-700 border-olive-600'
                : 'bg-white text-gray-600 border-transparent hover:text-olive-700 hover:bg-olive-50'
            }`}
          >
            {platform.id === 'all' ? (
              platform.label
            ) : (
              <span className="flex items-center space-x-1">
                <span>{platformIcons[platform.id]}</span>
                <span>{platform.label}</span>
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          {error}
        </div>
      )}

      {profiles.length === 0 ? (
        <div className="text-center py-12">
          <Eye className="w-12 h-12 mx-auto text-gray-400 mb-2" />
          <p className="text-sm text-gray-600">No discovered profiles found.</p>
          <p className="text-xs text-gray-500 mt-1">Run discovery to find qualified profiles (≥1,000 followers, minimum engagement rate).</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-3">
                  <input
                    type="checkbox"
                    checked={selected.size === profiles.length && profiles.length > 0}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelected(new Set(profiles.map(p => p.id)))
                      } else {
                        setSelected(new Set())
                      }
                    }}
                  />
                </th>
                <th className="text-left py-2 px-3">Platform</th>
                <th className="text-left py-2 px-3">Username</th>
                <th className="text-left py-2 px-3">Name</th>
                <th className="text-left py-2 px-3">Category</th>
                <th className="text-left py-2 px-3">Followers</th>
                <th className="text-left py-2 px-3">Engagement</th>
                <th className="text-left py-2 px-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((profile) => (
                <tr key={profile.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 px-3">
                    <input
                      type="checkbox"
                      checked={selected.has(profile.id)}
                      onChange={() => handleSelect(profile.id)}
                    />
                  </td>
                  <td className="py-2 px-3 capitalize">{profile.platform}</td>
                  <td className="py-2 px-3 font-medium">@{profile.username}</td>
                  <td className="py-2 px-3">{profile.full_name || '-'}</td>
                  <td className="py-2 px-3">{profile.category || '-'}</td>
                  <td className="py-2 px-3">{profile.followers_count.toLocaleString()}</td>
                  <td className="py-2 px-3">{profile.engagement_score.toFixed(2)}%</td>
                  <td className="py-2 px-3">
                    {profile.contact_email ? (
                      <span className="text-green-600 font-medium">{profile.contact_email}</span>
                    ) : (
                      <span className="text-gray-400 text-xs">Scraping...</span>
                    )}
                  </td>
                  <td className="py-2 px-3">
                    <a
                      href={profile.profile_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-olive-600 hover:text-olive-700"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

