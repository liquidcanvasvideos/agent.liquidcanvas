'use client'

import { useState, useEffect } from 'react'
import { Search, Loader2, Linkedin, Instagram, Facebook, Music, MapPin, Tag } from 'lucide-react'
import { discoverSocialProfilesPipeline, listJobs, type Job } from '@/lib/api'
import JobStatusPanel from '@/components/JobStatusPanel'
import ActivityFeed from '@/components/ActivityFeed'

export default function SocialDiscovery() {
  const [platform, setPlatform] = useState<'linkedin' | 'instagram' | 'tiktok' | 'facebook'>('linkedin')
  const [categories, setCategories] = useState<string[]>([])
  const [locations, setLocations] = useState<string[]>([])
  const [keywords, setKeywords] = useState('')
  const [maxResults, setMaxResults] = useState(100)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobsLoading, setJobsLoading] = useState(true)

  const availableCategories = [
    'Art Gallery', 'Museums', 'Art Studio', 'Art School', 'Art Fair', 
    'Art Dealer', 'Art Consultant', 'Art Publisher', 'Art Magazine'
  ]

  const availableLocations = [
    'United States', 'United Kingdom', 'Canada', 'Australia', 'Germany',
    'Spain', 'Netherlands', 'Belgium', 'France', 'Italy'
  ]

  const platformIcons = {
    linkedin: Linkedin,
    instagram: Instagram,
    facebook: Facebook,
    tiktok: Music,
  }

  // Load social jobs
  useEffect(() => {
    const loadJobs = async () => {
      try {
        const allJobs = await listJobs(0, 50)
        // Filter for social-related jobs
        const socialJobs = allJobs.filter((job: Job) => 
          job.job_type?.includes('social') || 
          job.job_type === 'social_discover' ||
          job.job_type === 'social_draft' ||
          job.job_type === 'social_send'
        )
        setJobs(socialJobs)
      } catch (err) {
        console.error('Failed to load social jobs:', err)
        setJobs([])
      } finally {
        setJobsLoading(false)
      }
    }

    loadJobs()
    const interval = setInterval(loadJobs, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const handleCategoryToggle = (category: string) => {
    if (categories.includes(category)) {
      setCategories(categories.filter(c => c !== category))
    } else {
      setCategories([...categories, category])
    }
    setError(null)
    setSuccess(null)
  }

  const handleLocationToggle = (location: string) => {
    if (locations.includes(location)) {
      setLocations(locations.filter(l => l !== location))
    } else {
      setLocations([...locations, location])
    }
    setError(null)
    setSuccess(null)
  }

  const handleMaxResultsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value)
    if (!isNaN(value) && value >= 1 && value <= 1000) {
      setMaxResults(value)
    } else if (e.target.value === '') {
      setMaxResults(0)
    }
    setError(null)
    setSuccess(null)
  }

  const canStart = () => {
    return categories.length > 0 && locations.length > 0 && maxResults > 0
  }

  const handleDiscover = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!canStart()) {
      if (categories.length === 0) {
        setError('Please select at least one category')
        return
      }
      if (locations.length === 0) {
        setError('Please select at least one location')
        return
      }
      if (maxResults === 0) {
        setError('Please enter a valid number for max results (1-1000)')
        return
      }
    }

    setError(null)
    setSuccess(null)
    setLoading(true)

    try {
      const result = await discoverSocialProfilesPipeline({
        platform,
        categories,
        locations,
        keywords: keywords.split(',').map(k => k.trim()).filter(k => k),
        max_results: maxResults,
      })
      setSuccess(`Discovery job started! Job ID: ${result.job_id}. Check the Jobs panel for status.`)
      setKeywords('')
      setCategories([])
      setLocations([])
      setMaxResults(100)
      
      // Refresh jobs
      const allJobs = await listJobs(0, 50)
      const socialJobs = allJobs.filter((job: Job) => 
        job.job_type?.includes('social') || 
        job.job_type === 'social_discover' ||
        job.job_type === 'social_draft' ||
        job.job_type === 'social_send'
      )
      setJobs(socialJobs)
      
      // Refresh pipeline status and trigger all table refreshes
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refreshSocialPipelineStatus'))
        window.dispatchEvent(new CustomEvent('jobsCompleted'))
      }
    } catch (err: any) {
      setError(err.message || 'Failed to start discovery')
    } finally {
      setLoading(false)
    }
  }

  const PlatformIcon = platformIcons[platform]

  return (
    <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-3">
      {/* Left Column - Discovery Form */}
      <div className="lg:col-span-7 space-y-3">
        <div className="glass rounded-xl shadow-lg border border-olive-200 p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-lg bg-olive-600">
                <Search className="w-4 h-4 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-olive-700">Social Profile Discovery</h3>
                <p className="text-xs text-gray-600">Discover social media profiles by platform, category, and location</p>
              </div>
            </div>
          </div>
          
          <form onSubmit={handleDiscover} className="space-y-4">
            {/* Platform Selection */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-2">
                Platform <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {(['linkedin', 'instagram', 'facebook', 'tiktok'] as const).map((p) => {
                  const Icon = platformIcons[p]
                  const isSelected = platform === p
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => {
                        setPlatform(p)
                        setError(null)
                        setSuccess(null)
                      }}
                      className={`flex items-center justify-center space-x-2 px-3 py-2 rounded-lg border-2 transition-all duration-200 text-xs font-medium ${
                        isSelected
                          ? 'border-olive-600 bg-olive-50 text-olive-700 shadow-md'
                          : 'border-gray-200 bg-white text-gray-700 hover:border-olive-300 hover:bg-olive-50'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span className="capitalize">{p}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Categories */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-2">
                <Tag className="w-3 h-3 inline mr-1" />
                Categories <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {availableCategories.map(cat => (
                  <label key={cat} className="flex items-center space-x-2 p-2 border border-olive-200 rounded-lg hover:bg-olive-50 cursor-pointer transition-colors">
                    <input
                      type="checkbox"
                      checked={categories.includes(cat)}
                      onChange={() => handleCategoryToggle(cat)}
                      className="accent-olive-600"
                    />
                    <span className="text-xs text-gray-700">{cat}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Locations */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-2">
                <MapPin className="w-3 h-3 inline mr-1" />
                Locations <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {availableLocations.map(loc => (
                  <label key={loc} className="flex items-center space-x-2 p-2 border border-olive-200 rounded-lg hover:bg-olive-50 cursor-pointer transition-colors">
                    <input
                      type="checkbox"
                      checked={locations.includes(loc)}
                      onChange={() => handleLocationToggle(loc)}
                      className="accent-olive-600"
                    />
                    <span className="text-xs text-gray-700">{loc}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Keywords */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-2">
                Keywords (Optional)
              </label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => {
                  setKeywords(e.target.value)
                  setError(null)
                  setSuccess(null)
                }}
                placeholder="e.g., contemporary art, abstract painting"
                className="w-full px-3 py-2 text-xs border border-olive-200 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
              />
            </div>

            {/* Max Results */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-2">
                Max Results <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                value={maxResults || ''}
                onChange={handleMaxResultsChange}
                min="1"
                max="1000"
                placeholder="100"
                className="w-full px-3 py-2 text-xs border border-olive-200 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-olive-500"
              />
              <p className="text-xs text-gray-500 mt-1">Enter a number between 1 and 1000</p>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-xs text-red-700 font-medium">{error}</p>
              </div>
            )}

            {success && (
              <div className="p-3 bg-olive-50 border border-olive-200 rounded-lg">
                <p className="text-xs text-olive-700 font-medium">✅ {success}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !canStart()}
              className="w-full px-4 py-2.5 bg-olive-600 text-white rounded-lg hover:bg-olive-700 hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 text-sm font-semibold transition-all duration-200"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Starting Discovery...</span>
                </>
              ) : (
                <>
                  <PlatformIcon className="w-4 h-4" />
                  <span>Discover {platform.charAt(0).toUpperCase() + platform.slice(1)} Profiles</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>

      {/* Right Column - Jobs & Activity */}
      <div className="lg:col-span-5 space-y-3">
        {jobsLoading ? (
          <div className="glass rounded-xl shadow-lg border border-olive-200 p-6">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-olive-600"></div>
              <p className="text-gray-500 text-xs mt-2">Loading jobs...</p>
            </div>
          </div>
        ) : jobs.length > 0 ? (
          <JobStatusPanel jobs={jobs} onRefresh={async () => {
            const allJobs = await listJobs(0, 50)
            const socialJobs = allJobs.filter((job: Job) => 
              job.job_type?.includes('social') || 
              job.job_type === 'social_discover' ||
              job.job_type === 'social_draft' ||
              job.job_type === 'social_send'
            )
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
