import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import NoAlertScript from './no-alert-script'

const inter = Inter({ subsets: ['latin'] })

// CRITICAL: Force dynamic rendering - no static generation
// This ensures the page is always server-rendered and never cached
export const dynamic = 'force-dynamic'
export const revalidate = 0

export const metadata: Metadata = {
  title: 'Liquid Canvas | Outreach Automation',
  description: 'Beautiful outreach automation powered by Liquid Canvas - Transform your creative connections',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Get build info - will be injected at build time via env vars
  const buildId = process.env.NEXT_PUBLIC_BUILD_ID || `runtime-${Date.now()}`
  const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME || new Date().toISOString()
  
  return (
    <html lang="en">
      <head>
        {/* Fix favicon 404 error by providing proper link tag */}
        <link rel="icon" href="/favicon.ico" type="image/x-icon" />
        <link rel="shortcut icon" href="/favicon.ico" type="image/x-icon" />
        {/* CRITICAL: Meta tags to prevent caching */}
        <meta httpEquiv="Cache-Control" content="no-store, no-cache, must-revalidate" />
        <meta httpEquiv="Pragma" content="no-cache" />
        <meta httpEquiv="Expires" content="0" />
      </head>
      <body className={inter.className}>
        <NoAlertScript />
        {/* CRITICAL: Visible version stamp - always in DOM - proves code is running */}
        <div 
          id="build-version-stamp" 
          style={{ 
            position: 'fixed', 
            bottom: 0, 
            left: 0, 
            zIndex: 99999, 
            background: 'rgba(0,0,0,0.8)', 
            color: 'white', 
            padding: '4px 8px', 
            fontSize: '10px', 
            fontFamily: 'monospace',
            pointerEvents: 'none',
            display: 'block'
          }}
          suppressHydrationWarning
        >
          <span style={{ color: '#ff00ff', fontWeight: 'bold' }}>MONOREPO v5.0-DRAFTS-FIX</span> | 
          <span style={{ color: '#00ff00', fontWeight: 'bold' }}>ROOT-DIR</span> | 
          Build: <span id="build-id-placeholder">loading...</span>
        </div>
        {/* Immediate debug script - runs before React loads - proves new code is deployed */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                const buildId = '${buildId}';
                const buildTime = '${buildTime}';
                const runtimeTime = new Date().toISOString();
                // CRITICAL RUNTIME PROOF: This will FAIL if wrong codebase is running
                const EXPECTED_REPO = 'liquidcanvas-monorepo-frontend';
                const EXPECTED_VERSION = '5.0-DRAFTS-FIX';
                const RUNTIME_PROOF = 'LIQUIDCANVAS-MONOREPO-' + Date.now();
                
                // FORENSIC MARKER: This proves root directory code is running
                const FORENSIC_MARKER = 'ROOT-DIRECTORY-BUILD-' + Date.now() + '-' + Math.random().toString(36).substring(7);
                window.__FORENSIC_MARKER__ = FORENSIC_MARKER;
                document.body.setAttribute('data-forensic-marker', FORENSIC_MARKER);
                
                console.log('🚨🚨🚨 DASHBOARD CODE LOADED - VERSION 5.0-DRAFTS-FIX 🚨🚨🚨');
                console.log('🚨🚨🚨 IF YOU SEE THIS, NEW CODE IS DEPLOYED 🚨🚨🚨');
                console.log('🚨 FORENSIC MARKER:', FORENSIC_MARKER);
                console.log('🚨 REPO PROOF:', EXPECTED_REPO);
                console.log('🚨 RUNTIME PROOF:', RUNTIME_PROOF);
                console.log('🚨 Build ID:', buildId);
                console.log('🚨 Build Time:', buildTime);
                console.log('🚨 Runtime Time:', runtimeTime);
                console.log('🚨 Page Load Time:', new Date().toLocaleString());
                
                // Set global markers for runtime verification
                window.__DASHBOARD_VERSION__ = EXPECTED_VERSION;
                window.__REPO_PROOF__ = EXPECTED_REPO;
                window.__RUNTIME_PROOF__ = RUNTIME_PROOF;
                window.__BUILD_ID__ = buildId;
                window.__BUILD_TIME__ = buildTime;
                window.__RUNTIME_TIME__ = runtimeTime;
                window.__DASHBOARD_LOADED__ = true;
                
                // HARD FAILURE TEST: If this code is NOT running, this will not exist
                window.__LIQUIDCANVAS_MONOREPO_ACTIVE__ = true;
                
                // Update visible stamp immediately
                const placeholder = document.getElementById('build-id-placeholder');
                if (placeholder) {
                  const timeStr = buildTime !== 'unknown' && buildTime.startsWith('2') 
                    ? new Date(buildTime).toLocaleString() 
                    : runtimeTime;
                  placeholder.textContent = buildId.substring(0, 20) + '... | ' + timeStr;
                }
                
                // Also log to console for debugging
                console.log('✅ Build version stamp updated in DOM');
              })();
            `,
          }}
        />
        {children}
      </body>
    </html>
  )
}
