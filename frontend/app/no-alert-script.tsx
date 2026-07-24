'use client'

/**
 * Global component to disable all alert(), confirm(), and prompt() popups
 * This prevents any popups from showing, even from cached code or browser extensions
 */
import { useEffect } from 'react'

export default function NoAlertScript() {
  useEffect(() => {
    // Override alert() - log to console instead, no popup
    const originalAlert = window.alert
    window.alert = function(message: any) {
      console.warn('[ALERT BLOCKED - No popup shown]', message)
      console.trace('Alert was called from:')
      // Do nothing - no popup shown
      return undefined
    }
    
    // Override confirm() - log and return false
    const originalConfirm = window.confirm
    window.confirm = function(message?: string): boolean {
      console.warn('[CONFIRM BLOCKED - No popup shown]', message)
      console.trace('Confirm was called from:')
      // Return false to prevent any action
      return false
    }
    
    // Override prompt() - log and return null
    const originalPrompt = window.prompt
    window.prompt = function(message?: string, defaultValue?: string): string | null {
      console.warn('[PROMPT BLOCKED - No popup shown]', message, defaultValue)
      console.trace('Prompt was called from:')
      // Return null to indicate cancellation
      return null
    }
    
    console.log('✅ All browser popups (alert, confirm, prompt) have been disabled')
    
    // Cleanup on unmount (restore originals if needed)
    return () => {
      // Optionally restore originals, but we want to keep them disabled
      // window.alert = originalAlert
      // window.confirm = originalConfirm
      // window.prompt = originalPrompt
    }
  }, [])
  
  return null
}

