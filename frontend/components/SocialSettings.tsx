'use client'

import { useState, useEffect } from 'react'
import { Save, CheckCircle, XCircle, Loader2, Instagram, Facebook, Music, Mail } from 'lucide-react'
import { getSocialIntegrations, saveSocialApiKey } from '@/lib/api'

interface SocialIntegration {
  platform: string
  connection_status: string
  api_key?: string // Masked API key for display
}

export default function SocialSettings() {
  const [integrations, setIntegrations] = useState<Record<string, SocialIntegration>>({})
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    instagram: '',
    facebook: '',
    tiktok: '',
  })
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<Record<string, boolean>>({})

  useEffect(() => {
    loadIntegrations()
  }, [])

  const loadIntegrations = async () => {
    try {
      setLoading(true)
      const data = await getSocialIntegrations()
      
      // Initialize integrations state
      const integrationsMap: Record<string, SocialIntegration> = {}
      data.forEach((integration: any) => {
        integrationsMap[integration.platform] = {
          platform: integration.platform,
          connection_status: integration.connection_status || 'not_connected',
        }
      })
      
      // Set default status for platforms not found
      ;['instagram', 'facebook', 'tiktok'].forEach((platform) => {
        if (!integrationsMap[platform]) {
          integrationsMap[platform] = {
            platform,
            connection_status: 'not_connected',
          }
        }
      })
      
      setIntegrations(integrationsMap)
    } catch (err: any) {
      console.error('Failed to load integrations:', err)
      setError('Failed to load social integrations')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (platform: string) => {
    const apiKey = apiKeys[platform]?.trim()
    if (!apiKey) {
      setError(`Please enter an API key for ${platform}`)
      return
    }

    try {
      setSaving((prev) => ({ ...prev, [platform]: true }))
      setError(null)
      
      await saveSocialApiKey(platform, apiKey)
      
      // Update local state
      setIntegrations((prev) => ({
        ...prev,
        [platform]: {
          ...prev[platform],
          platform,
          connection_status: 'connected',
        },
      }))
      
      // Clear the input
      setApiKeys((prev) => ({ ...prev, [platform]: '' }))
      
      // Show success message
      setSuccess((prev) => ({ ...prev, [platform]: true }))
      setTimeout(() => {
        setSuccess((prev) => ({ ...prev, [platform]: false }))
      }, 3000)
      
      // Reload integrations to get updated status
      await loadIntegrations()
    } catch (err: any) {
      console.error(`Failed to save ${platform} API key:`, err)
      setError(err.message || `Failed to save ${platform} API key`)
    } finally {
      setSaving((prev) => ({ ...prev, [platform]: false }))
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'connected':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <CheckCircle className="w-3 h-3 mr-1" />
            Connected
          </span>
        )
      case 'error':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
            <XCircle className="w-3 h-3 mr-1" />
            Error
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
            Not Connected
          </span>
        )
    }
  }

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case 'instagram':
        return <Instagram className="w-5 h-5" />
      case 'facebook':
        return <Facebook className="w-5 h-5" />
      case 'tiktok':
        return <Music className="w-5 h-5" />
      default:
        return <Mail className="w-5 h-5" />
    }
  }

  const getPlatformName = (platform: string) => {
    switch (platform) {
      case 'instagram':
        return 'Instagram'
      case 'facebook':
        return 'Facebook Messenger'
      case 'tiktok':
        return 'TikTok'
      default:
        return platform
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-olive-600" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Social Settings</h2>
        <p className="text-sm text-gray-600">
          Configure API keys for social media platforms to enable discovery and messaging capabilities.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border-2 border-red-300 rounded-xl text-red-700 text-sm font-medium">
          {error}
        </div>
      )}

      {/* Platform Cards */}
      <div className="space-y-4">
        {['instagram', 'facebook', 'tiktok'].map((platform) => {
          const integration = integrations[platform] || { platform, connection_status: 'not_connected' }
          const isConnected = integration.connection_status === 'connected'
          const isSaving = saving[platform]
          const showSuccess = success[platform]

          return (
            <div
              key={platform}
              className="glass rounded-xl border border-gray-200/50 p-6 shadow-lg"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-olive-500 to-olive-600 flex items-center justify-center text-white">
                    {getPlatformIcon(platform)}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      {getPlatformName(platform)}
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {platform === 'tiktok'
                        ? 'TikTok does not provide an official DM API. Discovery only.'
                        : `Connect your ${getPlatformName(platform)} account to send DMs.`}
                    </p>
                  </div>
                </div>
                {getStatusBadge(integration.connection_status)}
              </div>

              {platform === 'tiktok' ? (
                <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-xs text-yellow-800">
                    <strong>Note:</strong> TikTok does not support direct messaging via API. Only profile discovery is available.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <label
                      htmlFor={`${platform}-key`}
                      className="block text-sm font-semibold text-gray-700 mb-2"
                    >
                      API Key / Token
                    </label>
                    <input
                      id={`${platform}-key`}
                      type="password"
                      value={apiKeys[platform] || ''}
                      onChange={(e) =>
                        setApiKeys((prev) => ({ ...prev, [platform]: e.target.value }))
                      }
                      placeholder={isConnected ? 'API key is saved (enter new key to update)' : 'Enter API key or token'}
                      className="w-full px-4 py-2.5 bg-white/80 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-olive-500 focus:border-olive-500 transition-all"
                      disabled={isSaving}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-gray-500">
                      {isConnected
                        ? 'API key is securely stored. Enter a new key to update.'
                        : 'Enter your API key to enable this platform.'}
                    </p>
                    <button
                      onClick={() => handleSave(platform)}
                      disabled={isSaving || !apiKeys[platform]?.trim()}
                      className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-olive-600 to-olive-700 text-white rounded-lg hover:shadow-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
                    >
                      {isSaving ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Saving...</span>
                        </>
                      ) : showSuccess ? (
                        <>
                          <CheckCircle className="w-4 h-4" />
                          <span>Saved!</span>
                        </>
                      ) : (
                        <>
                          <Save className="w-4 h-4" />
                          <span>Save</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Info Box */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h4 className="text-sm font-semibold text-blue-900 mb-2">How it works:</h4>
        <ul className="text-xs text-blue-800 space-y-1 list-disc list-inside">
          <li>Enter your API key or token for each platform</li>
          <li>Keys are encrypted and stored securely</li>
          <li>Connected platforms enable discovery and messaging features</li>
          <li>Discovery works even without connections, but DM actions require valid keys</li>
        </ul>
      </div>
    </div>
  )
}

