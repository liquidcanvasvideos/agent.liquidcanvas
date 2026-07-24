import React from 'react'

// CRITICAL: Server Component layout - dynamic directives work here
// This layout wraps the dashboard page and forces dynamic rendering
export const dynamic = 'force-dynamic'
export const revalidate = 0

// HARD PROOF: Build-time log that proves this file is being used
// This will appear in Vercel build logs if the correct route is being built
console.log('🔨🔨🔨 [ROUTE BUILD] /dashboard/layout.tsx - DYNAMIC ROUTE FORCED 🔨🔨🔨')
console.log('🔨 [ROUTE BUILD] File path: frontend/app/dashboard/layout.tsx')
console.log('🔨 [ROUTE BUILD] Dynamic:', 'force-dynamic')
console.log('🔨 [ROUTE BUILD] Revalidate:', 0)

// Force this to execute at module load time
if (typeof window === 'undefined') {
  // Server-side only
  process.stdout?.write?.('\n🔨🔨🔨 [ROUTE BUILD] /dashboard/layout.tsx - DYNAMIC ROUTE FORCED 🔨🔨🔨\n')
  process.stdout?.write?.('🔨 [ROUTE BUILD] File path: frontend/app/dashboard/layout.tsx\n')
  process.stdout?.write?.('🔨 [ROUTE BUILD] Dynamic: force-dynamic\n')
  process.stdout?.write?.('🔨 [ROUTE BUILD] Revalidate: 0\n')
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}

