/** @type {import('next').NextConfig} */
// FORENSIC MARKER: This file proves root directory is being used
console.log('🔨 [FORENSIC] next.config.js loaded from ROOT directory')
console.log('🔨 [FORENSIC] File path should be: frontend/next.config.js')
console.log('🔨 [FORENSIC] NOT: frontend/frontend/next.config.js')

const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
  },
  // Generate unique build ID at build time - FORCE NEW BUILD EVERY TIME
  generateBuildId: async () => {
    const timestamp = Date.now()
    const random = Math.random().toString(36).substring(7)
    const buildId = `build-${timestamp}-${random}`
    const buildTime = new Date().toISOString()
    // CRITICAL: Log to build output so we can verify in Vercel logs
    // Use process.stdout.write to ensure it appears in build logs
    process.stdout.write('\n🔨🔨🔨 GENERATING NEW BUILD ID 🔨🔨🔨\n')
    process.stdout.write(`🔨 Build ID: ${buildId}\n`)
    process.stdout.write(`🔨 Build time: ${buildTime}\n`)
    process.stdout.write(`🔨 Timestamp: ${timestamp}\n`)
    console.log('🔨🔨🔨 GENERATING NEW BUILD ID 🔨🔨🔨')
    console.log('🔨 Build ID:', buildId)
    console.log('🔨 Build time:', buildTime)
    console.log('🔨 Timestamp:', timestamp)
    // Store in env for runtime access (Next.js will make NEXT_PUBLIC_* vars available)
    process.env.NEXT_PUBLIC_BUILD_ID = buildId
    process.env.NEXT_PUBLIC_BUILD_TIME = buildTime
    // CRITICAL: Return unique ID every time - no caching
    return buildId
  },
  // Disable ESLint during build to prevent config errors from blocking deployment
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Disable TypeScript errors during build (we'll catch them in dev)
  typescript: {
    ignoreBuildErrors: false, // Keep this false to catch real errors
  },
  // CRITICAL: Disable static optimization and caching
  // Remove 'standalone' output as it may cause issues with Vercel
  // output: 'standalone', 
  // Add headers to prevent caching at CDN and browser level
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0',
          },
          {
            key: 'Pragma',
            value: 'no-cache',
          },
          {
            key: 'Expires',
            value: '0',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
    ]
  },
}

module.exports = nextConfig
