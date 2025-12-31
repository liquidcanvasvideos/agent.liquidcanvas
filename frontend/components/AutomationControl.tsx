'use client'

import { useState, useEffect } from 'react'
import { Power, Zap, Hand, Loader2 } from 'lucide-react'
import { getMasterSwitch, setMasterSwitch, getAutomationSettings, updateAutomationSettings, isMasterSwitchEnabled } from '@/lib/api'

type AutomationMode = 'manual' | 'automatic' | 'off'

export default function AutomationControl() {
  const [masterSwitch, setMasterSwitchState] = useState(false)
  const [mode, setMode] = useState<AutomationMode>('off')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Load initial state from backend
  useEffect(() => {
    const loadState = async () => {
      try {
        setLoading(true)
        const [masterStatus, automationSettings] = await Promise.all([
          getMasterSwitch().catch(() => ({ enabled: false })),
          getAutomationSettings().catch(() => ({ enabled: false }))
        ])
        
        const masterEnabled = masterStatus.enabled
        setMasterSwitchState(masterEnabled)
        
        // Determine mode: off, manual, or automatic
        if (!masterEnabled) {
          setMode('off')
        } else if (automationSettings.enabled) {
          setMode('automatic')
        } else {
          setMode('manual')
        }
        
        // Store in localStorage for Pipeline to check
        if (typeof window !== 'undefined') {
          localStorage.setItem('master_switch_enabled', String(masterEnabled))
          localStorage.setItem('automation_mode', mode)
        }
      } catch (error) {
        console.error('Failed to load automation state:', error)
        // Fallback to localStorage
        if (typeof window !== 'undefined') {
          const stored = localStorage.getItem('master_switch_enabled')
          setMasterSwitchState(stored === 'true')
          const storedMode = localStorage.getItem('automation_mode') as AutomationMode
          if (storedMode) setMode(storedMode)
        }
      } finally {
        setLoading(false)
      }
    }
    
    loadState()
    
    // Listen for changes from other components
    const handleMasterSwitchChange = (e: CustomEvent) => {
      setMasterSwitchState(e.detail.enabled)
    }
    const handleAutomationChange = (e: CustomEvent) => {
      if (e.detail.enabled) {
        setMode('automatic')
      } else if (masterSwitch) {
        setMode('manual')
      } else {
        setMode('off')
      }
    }
    
    window.addEventListener('masterSwitchChanged', handleMasterSwitchChange as EventListener)
    window.addEventListener('automationSettingsChanged', handleAutomationChange as EventListener)
    
    return () => {
      window.removeEventListener('masterSwitchChanged', handleMasterSwitchChange as EventListener)
      window.removeEventListener('automationSettingsChanged', handleAutomationChange as EventListener)
    }
  }, [])

  const handleMasterSwitchToggle = async (enabled: boolean) => {
    try {
      setSaving(true)
      await setMasterSwitch(enabled)
      setMasterSwitchState(enabled)
      
      if (!enabled) {
        // If disabling master, also disable automation
        setMode('off')
        await updateAutomationSettings({ enabled: false })
        if (typeof window !== 'undefined') {
          localStorage.setItem('automation_mode', 'off')
        }
      } else {
        // If enabling master, set to manual mode
        setMode('manual')
        if (typeof window !== 'undefined') {
          localStorage.setItem('automation_mode', 'manual')
        }
      }
    } catch (error: any) {
      console.error('Failed to toggle master switch:', error)
      alert(error.message || 'Failed to toggle master switch')
    } finally {
      setSaving(false)
    }
  }

  const handleModeChange = async (newMode: AutomationMode) => {
    if (!masterSwitch && newMode !== 'off') {
      // Can't set mode without master switch
      return
    }
    
    try {
      setSaving(true)
      
      if (newMode === 'off') {
        // Turn off master switch
        await handleMasterSwitchToggle(false)
      } else if (newMode === 'automatic') {
        // Enable automation
        await updateAutomationSettings({ enabled: true })
        setMode('automatic')
        if (typeof window !== 'undefined') {
          localStorage.setItem('automation_mode', 'automatic')
        }
      } else {
        // Manual mode
        await updateAutomationSettings({ enabled: false })
        setMode('manual')
        if (typeof window !== 'undefined') {
          localStorage.setItem('automation_mode', 'manual')
        }
      }
    } catch (error: any) {
      console.error('Failed to change mode:', error)
      alert(error.message || 'Failed to change automation mode')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="glass rounded-xl shadow-lg border border-white/20 p-3 animate-fade-in">
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-4 h-4 animate-spin text-olive-600" />
        </div>
      </div>
    )
  }

  return (
    <div className="glass rounded-xl shadow-lg border border-white/20 p-3 animate-fade-in">
      <h2 className="text-sm font-bold text-olive-700 mb-3">Master Control</h2>
      <div className="space-y-3">
        {/* Master Switch */}
        <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-2">
            <Power className="w-4 h-4 text-gray-600" />
            <div>
              <p className="text-xs font-semibold text-gray-900">Master Switch</p>
              <p className="text-xs text-gray-600">Enable/disable all pipeline activities</p>
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={masterSwitch}
              disabled={saving}
              onChange={(e) => handleMasterSwitchToggle(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-olive-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-olive-600"></div>
          </label>
        </div>

        {/* Mode Selector */}
        <div className="p-2 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-2 mb-2">
            <Zap className="w-4 h-4 text-gray-600" />
            <p className="text-xs font-semibold text-gray-900">Mode</p>
          </div>
          <div className="grid grid-cols-3 gap-1">
            <button
              onClick={() => handleModeChange('off')}
              disabled={saving}
              className={`px-2 py-1.5 rounded text-xs font-medium transition-all ${
                mode === 'off'
                  ? 'bg-olive-600 text-white shadow-md'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Off
            </button>
            <button
              onClick={() => handleModeChange('manual')}
              disabled={saving || !masterSwitch}
              className={`px-2 py-1.5 rounded text-xs font-medium transition-all flex items-center justify-center space-x-1 ${
                mode === 'manual'
                  ? 'bg-olive-600 text-white shadow-md'
                  : masterSwitch
                  ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              <Hand className="w-3 h-3" />
              <span>Manual</span>
            </button>
            <button
              onClick={() => handleModeChange('automatic')}
              disabled={saving || !masterSwitch}
              className={`px-2 py-1.5 rounded text-xs font-medium transition-all flex items-center justify-center space-x-1 ${
                mode === 'automatic'
                  ? 'bg-olive-600 text-white shadow-md'
                  : masterSwitch
                  ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              <Zap className="w-3 h-3" />
              <span>Auto</span>
            </button>
          </div>
          <p className="text-xs text-gray-600 mt-2">
            {mode === 'off' && 'All pipeline activities are disabled'}
            {mode === 'manual' && 'Pipeline activities run only when you trigger them'}
            {mode === 'automatic' && 'Pipeline activities run automatically on schedule'}
          </p>
        </div>
      </div>
    </div>
  )
}

