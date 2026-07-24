export {}

declare global {
  interface Window {
    __DASHBOARD_RUNTIME_PROOF__?: string
    __DASHBOARD_REPO__?: string
    __DRAFTS_TAB_DEBUG__?: {
      exists: boolean
      tabId?: string
      label?: string
      allTabs: string[]
      timestamp: number
    }
  }
}
