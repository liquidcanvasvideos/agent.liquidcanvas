'use client'

import { useEffect, useState } from 'react'
import {
  Settings,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  Key,
  RefreshCw,
} from 'lucide-react'
import { getSettings, testService, handleOAuthCallback, type ServiceStatus } from '@/lib/api'
import SocialIntegrationsSettings from '@/components/SocialIntegrationsSettings'

interface ServiceCardProps {
  service: ServiceStatus
  serviceKey: string
  onTest: (serviceName: string) => void
  testing: boolean
}

function ServiceCard({ service, serviceKey, onTest, testing }: ServiceCardProps) {
  const getStatusColor = () => {
    switch (service.status) {
      case 'connected':
        return 'text-green-600 bg-green-50 border-green-200'
      case 'error':
        return 'text-red-600 bg-red-50 border-red-200'
      case 'not_configured':
        return 'text-gray-600 bg-gray-50 border-gray-200'
      default:
        return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    }
  }

  const getStatusIcon = () => {
    switch (service.status) {
      case 'connected':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'error':
        return <XCircle className="w-4 h-4 text-red-600" />
      case 'not_configured':
        return <AlertCircle className="w-4 h-4 text-gray-600" />
      default:
        return <AlertCircle className="w-4 h-4 text-yellow-600" />
    }
  }

  const getStatusText = () => {
    switch (service.status) {
      case 'connected':
        return 'Connected'
      case 'error':
        return 'Error'
      case 'not_configured':
        return 'Not Configured'
      case 'disconnected':
        return 'Disconnected'
      default:
        return 'Unknown'
    }
  }

  return (
    <div className={`bg-white rounded-lg shadow-sm border p-4 ${getStatusColor()}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <div>
            <h3 className="text-sm font-bold text-gray-900">{service.name}</h3>
            <p className="text-xs text-gray-600 mt-0.5">{getStatusText()}</p>
          </div>
        </div>
        <div className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
          service.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
        }`}>
          {service.enabled ? 'Enabled' : 'Disabled'}
        </div>
      </div>

      {service.message && (
        <p className="text-xs text-gray-700 mb-3 bg-white/50 p-2 rounded">
          {service.message}
        </p>
      )}

      <div className="flex items-center justify-between">
        <div className="text-xs text-gray-500">
          {service.configured ? (
            <span className="flex items-center space-x-1">
              <Key className="w-3 h-3" />
              <span>Configured</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1">
              <AlertCircle className="w-3 h-3" />
              <span>Not Set</span>
            </span>
          )}
        </div>
        <button
          onClick={() => onTest(serviceKey)}
          disabled={testing || !service.configured}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md font-semibold text-xs transition-all ${
            service.configured && !testing
              ? 'bg-olive-600 hover:bg-olive-700 text-white'
              : 'bg-gray-200 text-gray-500 cursor-not-allowed'
          }`}
        >
          {testing ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Testing...</span>
            </>
          ) : (
            <>
              <RefreshCw className="w-3 h-3" />
              <span>Test</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}

export default function SettingsContent() {
  const [settings, setSettings] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, any>>({})

  useEffect(() => {
    // Handle OAuth callback if present in URL
    const handleOAuthCallbackFlow = async () => {
      const params = new URLSearchParams(window.location.search)
      const oauthCallback = params.get('oauth_callback')
      const code = params.get('code')
      const state = params.get('state')
      const error = params.get('error')
      const errorReason = params.get('error_reason')
      
      if (oauthCallback && (code || error)) {
        if (error) {
          alert(`OAuth authorization failed: ${error}${errorReason ? ` (${errorReason})` : ''}`)
          // Clean up URL
          window.history.replaceState({}, '', window.location.pathname)
          return
        }
        
        if (code && oauthCallback) {
          try {
            setLoading(true)
            await handleOAuthCallback(oauthCallback, code, state || undefined)
            alert(`✅ Successfully connected ${oauthCallback}!`)
            // Clean up URL
            window.history.replaceState({}, '', window.location.pathname)
            // Reload settings to show updated integrations
            loadSettings()
          } catch (err: any) {
            console.error('OAuth callback error:', err)
            alert(`Failed to complete OAuth connection: ${err.message}`)
            // Clean up URL
            window.history.replaceState({}, '', window.location.pathname)
          } finally {
            setLoading(false)
          }
        }
      }
    }

    handleOAuthCallbackFlow()
    loadSettings()
    // Refresh every 30 seconds
    const interval = setInterval(loadSettings, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadSettings = async () => {
    try {
      const data = await getSettings()
      setSettings(data)
    } catch (error: any) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async (serviceKey: string) => {
    setTesting(serviceKey)
    try {
      const serviceName = settings.services[serviceKey]?.name || serviceKey
      const result = await testService(serviceName)
      setTestResult(prev => ({ ...prev, [serviceKey]: result }))
      
      if (settings) {
        setSettings({
          ...settings,
          services: {
            ...settings.services,
            [serviceKey]: {
              ...settings.services[serviceKey],
              status: result.success ? 'connected' : 'error',
              message: result.message,
              last_tested: new Date().toISOString(),
            }
          }
        })
      }
      
      setTimeout(loadSettings, 1000)
    } catch (error: any) {
      console.error(`Failed to test ${serviceKey}:`, error)
      setTestResult(prev => ({
        ...prev,
        [serviceKey]: {
          success: false,
          message: error.message || 'Test failed',
        }
      }))
    } finally {
      setTesting(null)
    }
  }

  if (loading && !settings) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-olive-600" />
      </div>
    )
  }

  const serviceKeys = settings ? Object.keys(settings.services) : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Settings className="w-6 h-6 text-olive-600" />
          <div>
            <h2 className="text-lg font-bold text-gray-900">System Settings</h2>
            <p className="text-xs text-gray-600 mt-0.5">
              Configure and test all third-party API integrations
            </p>
          </div>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border-l-4 border-blue-500 rounded-lg p-3">
        <div className="flex items-start">
          <AlertCircle className="w-4 h-4 text-blue-600 mt-0.5 mr-2 flex-shrink-0" />
          <div className="text-xs text-blue-800">
            <p className="font-semibold mb-1">API Key Configuration</p>
            <p className="text-blue-700">
              To update API keys, go to your Render dashboard → Environment Variables. 
              Changes require a server restart to take effect.
            </p>
          </div>
        </div>
      </div>

      {/* Services Grid */}
      <div>
        <h3 className="text-sm font-bold text-gray-900 mb-3">API Services Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {serviceKeys.map((serviceKey) => (
            <ServiceCard
              key={serviceKey}
              service={settings.services[serviceKey]}
              serviceKey={serviceKey}
              onTest={handleTest}
              testing={testing === serviceKey}
            />
          ))}
        </div>
      </div>

      {/* Test Results */}
      {Object.keys(testResult).length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <h3 className="text-sm font-bold text-gray-900 mb-3">Test Results</h3>
          <div className="space-y-2">
            {Object.entries(testResult).map(([key, result]: [string, any]) => (
              <div
                key={key}
                className={`p-3 rounded-lg ${
                  result.success
                    ? 'bg-green-50 border border-green-200'
                    : 'bg-red-50 border border-red-200'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-sm text-gray-900">
                      {settings.services[key]?.name || key}
                    </p>
                    <p className={`text-xs mt-1 ${
                      result.success ? 'text-green-700' : 'text-red-700'
                    }`}>
                      {result.message}
                    </p>
                  </div>
                  {result.success ? (
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-600" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* API Keys Status */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-bold text-gray-900 mb-3">API Keys Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {settings && Object.entries(settings.api_keys).map(([key, configured]: [string, any]) => (
            <div
              key={key}
              className={`p-2 rounded-lg border-2 ${
                configured
                  ? 'bg-green-50 border-green-200'
                  : 'bg-gray-50 border-gray-200'
              }`}
            >
              <div className="flex items-center space-x-2">
                {configured ? (
                  <CheckCircle className="w-3 h-3 text-green-600" />
                ) : (
                  <XCircle className="w-3 h-3 text-gray-400" />
                )}
                <span className="text-xs font-medium text-gray-700">
                  {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Social Integrations Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <SocialIntegrationsSettings />
      </div>

      {/* Instructions */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-bold text-gray-900 mb-3">Configuration Instructions</h3>
        <div className="space-y-3 text-xs text-gray-700">
          <div>
            <p className="font-semibold mb-1">To configure API keys:</p>
            <ol className="list-decimal list-inside space-y-1 ml-2">
              <li>Go to your Render dashboard</li>
              <li>Navigate to your backend service → Environment</li>
              <li>Add or update the required environment variables</li>
              <li>Redeploy the service for changes to take effect</li>
            </ol>
          </div>
          <div>
            <p className="font-semibold mb-1">Required Environment Variables:</p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li><code className="bg-gray-100 px-1 rounded">HUNTER_IO_API_KEY</code> - Hunter.io API key</li>
              <li><code className="bg-gray-100 px-1 rounded">DATAFORSEO_LOGIN</code> - DataForSEO email/login</li>
              <li><code className="bg-gray-100 px-1 rounded">DATAFORSEO_PASSWORD</code> - DataForSEO password</li>
              <li><code className="bg-gray-100 px-1 rounded">GEMINI_API_KEY</code> - Google Gemini API key</li>
              <li><code className="bg-gray-100 px-1 rounded">INSTAGRAM_CLIENT_ID</code> - Instagram OAuth client ID</li>
              <li><code className="bg-gray-100 px-1 rounded">INSTAGRAM_CLIENT_SECRET</code> - Instagram OAuth client secret</li>
              <li><code className="bg-gray-100 px-1 rounded">FACEBOOK_CLIENT_ID</code> - Facebook OAuth client ID</li>
              <li><code className="bg-gray-100 px-1 rounded">FACEBOOK_CLIENT_SECRET</code> - Facebook OAuth client secret</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

