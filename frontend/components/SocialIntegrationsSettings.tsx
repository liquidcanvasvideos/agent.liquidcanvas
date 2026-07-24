'use client'

import { useEffect, useState } from 'react'
import {
  Instagram,
  Facebook,
  Mail,
  Music2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  Trash2,
  ExternalLink,
  Key,
  Lock,
  Unlock,
  Info
} from 'lucide-react'
import {
  listSocialIntegrations,
  getSocialCapabilities,
  createSocialIntegration,
  deleteSocialIntegration,
  validateSocialIntegration,
  refreshSocialIntegrationToken,
  initiateOAuthFlow,
  type SocialIntegration,
  type PlatformCapability,
  type IntegrationCreate
} from '@/lib/api'

interface PlatformConfig {
  name: string
  icon: React.ReactNode
  color: string
  bgColor: string
  description: string
  requiresOAuth: boolean
  supportsDM: boolean
}

const PLATFORMS: Record<string, PlatformConfig> = {
  instagram: {
    name: 'Instagram',
    icon: <Instagram className="w-6 h-6" />,
    color: 'text-pink-600',
    bgColor: 'bg-pink-50',
    description: 'Connect your Instagram Business or Creator account to send DMs',
    requiresOAuth: true,
    supportsDM: true
  },
  facebook: {
    name: 'Facebook Messenger',
    icon: <Facebook className="w-6 h-6" />,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    description: 'Connect your Facebook Page to send messages via Messenger',
    requiresOAuth: true,
    supportsDM: true
  },
  tiktok: {
    name: 'TikTok',
    icon: <Music2 className="w-6 h-6" />,
    color: 'text-black',
    bgColor: 'bg-gray-50',
    description: 'TikTok does not provide an official DM API. Discovery only.',
    requiresOAuth: false,
    supportsDM: false
  },
  email: {
    name: 'Email (SMTP)',
    icon: <Mail className="w-6 h-6" />,
    color: 'text-gray-600',
    bgColor: 'bg-gray-50',
    description: 'Configure SMTP to send emails for outreach',
    requiresOAuth: false,
    supportsDM: true
  }
}

export default function SocialIntegrationsSettings() {
  const [integrations, setIntegrations] = useState<SocialIntegration[]>([])
  const [capabilities, setCapabilities] = useState<PlatformCapability[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [validating, setValidating] = useState<string | null>(null)
  const [showEmailForm, setShowEmailForm] = useState(false)
  const [emailFormData, setEmailFormData] = useState({
    email_address: '',
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: ''
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [integrationsData, capabilitiesData] = await Promise.all([
        listSocialIntegrations(),
        getSocialCapabilities()
      ])
      setIntegrations(integrationsData)
      setCapabilities(capabilitiesData)
    } catch (error: any) {
      console.error('Failed to load social integrations:', error)
      alert(`Failed to load integrations: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const getIntegrationForPlatform = (platform: string): SocialIntegration | undefined => {
    return integrations.find(int => int.platform === platform)
  }

  const getCapabilityForPlatform = (platform: string): PlatformCapability | undefined => {
    return capabilities.find(cap => cap.platform === platform)
  }

  const handleOAuthConnect = async (platform: 'instagram' | 'facebook') => {
    try {
      setConnecting(platform)
      const { authorization_url } = await initiateOAuthFlow(platform)
      // Redirect to OAuth flow (or open in popup)
      window.location.href = authorization_url
      // Note: After OAuth callback, user will be redirected back to settings page
      // The callback handler should process the OAuth code and create the integration
    } catch (error: any) {
      console.error(`Failed to initiate OAuth for ${platform}:`, error)
      alert(`Failed to connect ${platform}: ${error.message}`)
      setConnecting(null)
    }
  }

  const handleEmailConnect = async () => {
    try {
      setConnecting('email')
      const integrationData: IntegrationCreate = {
        platform: 'email',
        email_address: emailFormData.email_address,
        smtp_host: emailFormData.smtp_host,
        smtp_port: emailFormData.smtp_port,
        smtp_username: emailFormData.smtp_username,
        smtp_password: emailFormData.smtp_password
      }
      await createSocialIntegration(integrationData)
      setShowEmailForm(false)
      setEmailFormData({
        email_address: '',
        smtp_host: '',
        smtp_port: 587,
        smtp_username: '',
        smtp_password: ''
      })
      await loadData()
      alert('Email integration connected successfully!')
    } catch (error: any) {
      console.error('Failed to connect email:', error)
      alert(`Failed to connect email: ${error.message}`)
    } finally {
      setConnecting(null)
    }
  }

  const handleValidate = async (platform: string) => {
    try {
      setValidating(platform)
      const result = await validateSocialIntegration(platform)
      if (result.valid) {
        alert('✅ Integration is valid and working!')
      } else {
        alert(`⚠️ Integration validation failed: ${result.message}`)
      }
      await loadData()
    } catch (error: any) {
      console.error('Failed to validate integration:', error)
      alert(`Failed to validate: ${error.message}`)
    } finally {
      setValidating(null)
    }
  }

  const handleDisconnect = async (platform: string) => {
    if (!confirm(`Are you sure you want to disconnect ${platform}?`)) {
      return
    }
    try {
      await deleteSocialIntegration(platform)
      await loadData()
      alert(`${platform} disconnected successfully`)
    } catch (error: any) {
      console.error('Failed to disconnect:', error)
      alert(`Failed to disconnect: ${error.message}`)
    }
  }

  const getStatusBadge = (capability: PlatformCapability | undefined, integration: SocialIntegration | undefined) => {
    if (!integration) {
      return (
        <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">
          Not Connected
        </span>
      )
    }

    if (capability?.is_connected) {
      return (
        <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-700 flex items-center gap-1">
          <CheckCircle className="w-3 h-3" />
          Connected
        </span>
      )
    }

    if (integration.connection_status === 'expired') {
      return (
        <span className="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-700 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          Expired
        </span>
      )
    }

    return (
      <span className="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-700 flex items-center gap-1">
        <XCircle className="w-3 h-3" />
        {integration.connection_status || 'Disconnected'}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-olive-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Social Outreach Integrations</h2>
        <p className="text-sm text-gray-600">
          Connect your social media accounts to enable outbound outreach. Discovery works without connections, but sending messages requires valid integrations.
        </p>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border-l-4 border-blue-500 rounded-lg p-4">
        <div className="flex items-start">
          <Info className="w-5 h-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
          <div className="text-sm text-blue-800">
            <p className="font-semibold mb-1">How It Works</p>
            <ul className="list-disc list-inside space-y-1 text-blue-700">
              <li>Discovery works even without connections - you can find profiles anytime</li>
              <li>To send messages, you need to connect the corresponding platform</li>
              <li>OAuth platforms (Instagram, Facebook) require proper scopes for messaging</li>
              <li>Email requires SMTP configuration</li>
              <li>TikTok does not support messaging - discovery only</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Platform Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {Object.entries(PLATFORMS).map(([platformKey, config]) => {
          const integration = getIntegrationForPlatform(platformKey)
          const capability = getCapabilityForPlatform(platformKey)
          const isConnecting = connecting === platformKey
          const isConnected = integration?.is_connected || false
          const canSendDM = capability?.can_send_dm || false

          return (
            <div
              key={platformKey}
              className={`bg-white rounded-xl shadow-md border-2 p-6 ${
                isConnected ? 'border-green-200' : 'border-gray-200'
              }`}
            >
              {/* Platform Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className={`p-3 rounded-lg ${config.bgColor} ${config.color}`}>
                    {config.icon}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900">{config.name}</h3>
                    <p className="text-xs text-gray-600 mt-1">{config.description}</p>
                  </div>
                </div>
                {getStatusBadge(capability, integration)}
              </div>

              {/* Capability Info */}
              {capability && (
                <div className="mb-4 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Can Discover Profiles:</span>
                    <span className={capability.can_discover ? 'text-green-600 font-semibold' : 'text-gray-400'}>
                      {capability.can_discover ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Can Send Messages:</span>
                    <span className={canSendDM ? 'text-green-600 font-semibold' : 'text-red-600'}>
                      {canSendDM ? 'Yes' : 'No'}
                    </span>
                  </div>
                  {capability.reason && !canSendDM && (
                    <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
                      <Info className="w-3 h-3 inline mr-1" />
                      {capability.reason}
                    </div>
                  )}
                  {integration?.token_expires_at && (
                    <div className="text-xs text-gray-500 mt-2">
                      Token expires: {new Date(integration.token_expires_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2">
                {!integration ? (
                  <>
                    {config.requiresOAuth ? (
                      <button
                        onClick={() => handleOAuthConnect(platformKey as 'instagram' | 'facebook')}
                        disabled={isConnecting || platformKey === 'tiktok'}
                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all ${
                          platformKey === 'tiktok'
                            ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                            : isConnecting
                            ? 'bg-olive-400 text-white cursor-not-allowed'
                            : 'bg-olive-600 hover:bg-olive-700 text-white'
                        }`}
                      >
                        {isConnecting ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Connecting...
                          </>
                        ) : (
                          <>
                            <ExternalLink className="w-4 h-4" />
                            Connect via OAuth
                          </>
                        )}
                      </button>
                    ) : platformKey === 'email' ? (
                      <button
                        onClick={() => setShowEmailForm(true)}
                        disabled={isConnecting}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm bg-olive-600 hover:bg-olive-700 text-white transition-all"
                      >
                        <Key className="w-4 h-4" />
                        Configure SMTP
                      </button>
                    ) : null}
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleValidate(platformKey)}
                      disabled={validating === platformKey}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm bg-blue-600 hover:bg-blue-700 text-white transition-all"
                    >
                      {validating === platformKey ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Validating...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="w-4 h-4" />
                          Validate
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleDisconnect(platformKey)}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm bg-red-600 hover:bg-red-700 text-white transition-all"
                    >
                      <Trash2 className="w-4 h-4" />
                      Disconnect
                    </button>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Email Configuration Modal */}
      {showEmailForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-4">Configure Email (SMTP)</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  value={emailFormData.email_address}
                  onChange={(e) => setEmailFormData({ ...emailFormData, email_address: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-transparent"
                  placeholder="your-email@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  SMTP Host
                </label>
                <input
                  type="text"
                  value={emailFormData.smtp_host}
                  onChange={(e) => setEmailFormData({ ...emailFormData, smtp_host: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-transparent"
                  placeholder="smtp.gmail.com"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">
                    SMTP Port
                  </label>
                  <input
                    type="number"
                    value={emailFormData.smtp_port}
                    onChange={(e) => setEmailFormData({ ...emailFormData, smtp_port: parseInt(e.target.value) || 587 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-transparent"
                    placeholder="587"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  SMTP Username
                </label>
                <input
                  type="text"
                  value={emailFormData.smtp_username}
                  onChange={(e) => setEmailFormData({ ...emailFormData, smtp_username: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-transparent"
                  placeholder="your-email@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  SMTP Password
                </label>
                <input
                  type="password"
                  value={emailFormData.smtp_password}
                  onChange={(e) => setEmailFormData({ ...emailFormData, smtp_password: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-500 focus:border-transparent"
                  placeholder="Your SMTP password or app password"
                />
              </div>
            </div>
            <div className="flex items-center gap-3 mt-6">
              <button
                onClick={handleEmailConnect}
                disabled={connecting === 'email'}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm bg-olive-600 hover:bg-olive-700 text-white transition-all disabled:opacity-50"
              >
                {connecting === 'email' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Connect
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setShowEmailForm(false)
                  setEmailFormData({
                    email_address: '',
                    smtp_host: '',
                    smtp_port: 587,
                    smtp_username: '',
                    smtp_password: ''
                  })
                }}
                className="px-4 py-2 rounded-lg font-semibold text-sm bg-gray-200 hover:bg-gray-300 text-gray-700 transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

