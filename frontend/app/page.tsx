'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Image from 'next/image'
import { ArrowRight, Globe, Users, Zap, Shield, BarChart3, CheckCircle, Sparkles, Rocket, TrendingUp, Lock, Clock } from 'lucide-react'

export default function LandingPage() {
  const router = useRouter()

  useEffect(() => {
    // Redirect authenticated users to their dashboard
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    if (token) {
      const outreachType = typeof window !== 'undefined' ? localStorage.getItem('outreach_type') : null
      if (outreachType === 'social') {
        router.push('/socials')
      } else {
        router.push('/dashboard')
      }
    }
  }, [router])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30 overflow-hidden">
      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center px-4 sm:px-6 lg:px-8 pt-20 pb-32">
        {/* Animated Background */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-0 w-full h-full">
            <div className="absolute top-20 left-10 w-96 h-96 bg-olive-400/20 rounded-full blur-3xl animate-pulse"></div>
            <div className="absolute bottom-20 right-10 w-[500px] h-[500px] bg-purple-400/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-400/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
          </div>
        </div>

        <div className="relative z-10 max-w-7xl mx-auto w-full">
          <div className="text-center mb-16">
            {/* Logo */}
            <div className="flex justify-center mb-8">
              <div className="w-24 h-24 bg-gradient-to-br from-olive-600 via-olive-500 to-olive-700 rounded-3xl flex items-center justify-center shadow-2xl transform hover:scale-110 transition-transform duration-300">
                <span className="text-white text-4xl font-bold">LC</span>
              </div>
            </div>

            {/* Main Heading */}
            <h1 className="text-6xl md:text-7xl lg:text-8xl font-extrabold mb-6 animate-fade-in">
              <span className="bg-gradient-to-r from-olive-700 via-olive-600 to-olive-500 bg-clip-text text-transparent">
                Liquid Canvas
              </span>
            </h1>
            <p className="text-2xl md:text-3xl text-gray-700 mb-4 font-semibold animate-fade-in" style={{ animationDelay: '0.1s' }}>
              Outreach Studio
            </p>
            <p className="text-lg md:text-xl text-gray-600 max-w-3xl mx-auto mb-10 animate-fade-in" style={{ animationDelay: '0.2s' }}>
              Discover prospects, automate outreach, and scale your business with intelligent automation.
              <br />
              <span className="text-olive-600 font-medium">Everything you need in one powerful platform.</span>
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16 animate-fade-in" style={{ animationDelay: '0.3s' }}>
              <Link
                href="/login"
                className="group px-8 py-4 bg-gradient-to-r from-olive-600 to-olive-700 text-white rounded-2xl hover:shadow-2xl hover:scale-105 transition-all duration-300 font-bold text-lg flex items-center space-x-2 shadow-xl"
              >
                <span>Get Started Free</span>
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <a
                href="https://liquidcanvas.art"
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 glass border-2 border-olive-500/50 text-olive-700 rounded-2xl hover:shadow-xl hover:scale-105 transition-all duration-300 font-semibold text-lg hover:bg-olive-50"
              >
                Learn More
              </a>
            </div>

            {/* Trust Indicators */}
            <div className="flex flex-wrap justify-center items-center gap-8 text-sm text-gray-600 animate-fade-in" style={{ animationDelay: '0.4s' }}>
              <div className="flex items-center space-x-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <span>No Credit Card Required</span>
              </div>
              <div className="flex items-center space-x-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <span>14-Day Free Trial</span>
              </div>
              <div className="flex items-center space-x-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <span>Cancel Anytime</span>
              </div>
            </div>
          </div>
        </div>

        {/* Scroll Indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
          <div className="w-6 h-10 border-2 border-olive-600 rounded-full flex justify-center">
            <div className="w-1 h-3 bg-olive-600 rounded-full mt-2"></div>
          </div>
        </div>
      </section>

      {/* Dashboard Preview Section */}
      <section className="relative py-32 px-4 sm:px-6 lg:px-8 bg-white/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <div className="inline-flex items-center space-x-2 px-4 py-2 bg-olive-50 rounded-full mb-6">
              <Sparkles className="w-4 h-4 text-olive-600" />
              <span className="text-sm font-semibold text-olive-700">Powerful Dashboard</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
              Everything You Need, <span className="text-olive-600">All in One Place</span>
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Manage your entire outreach workflow from a single, intuitive dashboard designed for efficiency and scale.
            </p>
          </div>

          {/* Dashboard Screenshot */}
          <div className="relative rounded-3xl shadow-2xl overflow-hidden border-4 border-white/80 bg-white transform hover:scale-[1.02] transition-transform duration-500">
            <div className="aspect-video relative bg-gradient-to-br from-gray-50 to-gray-100">
              <Image
                src="/dashboard-screenshot.png"
                alt="Liquid Canvas Dashboard - Complete Outreach Management Platform"
                fill
                className="object-contain"
                priority
                quality={90}
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.style.display = 'none'
                  const fallback = target.nextElementSibling as HTMLElement
                  if (fallback) fallback.style.display = 'flex'
                }}
              />
              {/* Fallback placeholder */}
              <div className="absolute inset-0 bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center" style={{ display: 'none' }}>
                <div className="text-center p-12">
                  <div className="w-32 h-32 bg-gradient-to-br from-olive-500 to-olive-600 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-2xl">
                    <BarChart3 className="w-16 h-16 text-white" />
                  </div>
                  <p className="text-gray-600 font-semibold text-lg mb-2">Dashboard Preview</p>
                  <p className="text-sm text-gray-500">Add dashboard-screenshot.png to /public folder</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-32 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-white to-slate-50">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-20">
            <div className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-50 rounded-full mb-6">
              <Rocket className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-semibold text-blue-700">Powerful Features</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
              Built for <span className="text-olive-600">Modern Teams</span>
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Everything you need to discover, engage, and convert prospects at scale
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="group glass rounded-2xl p-8 border border-white/50 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                <Globe className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">Website Discovery</h3>
              <p className="text-gray-600 leading-relaxed">
                Automatically discover websites and prospects based on your criteria. Advanced search algorithms find the perfect leads for your business.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="group glass rounded-2xl p-8 border border-white/50 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
              <div className="w-16 h-16 bg-gradient-to-br from-pink-500 to-purple-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                <Users className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">Social Outreach</h3>
              <p className="text-gray-600 leading-relaxed">
                Connect with prospects on Instagram, Facebook, TikTok, and LinkedIn. Multi-platform outreach from a single dashboard.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="group glass rounded-2xl p-8 border border-white/50 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
              <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                <Zap className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">Automated Workflows</h3>
              <p className="text-gray-600 leading-relaxed">
                Set up automated pipelines for discovery, enrichment, and outreach. Save hours every week with intelligent automation.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="group glass rounded-2xl p-8 border border-white/50 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
              <div className="w-16 h-16 bg-gradient-to-br from-yellow-500 to-orange-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                <Shield className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">Enterprise Security</h3>
              <p className="text-gray-600 leading-relaxed">
                Bank-level encryption and secure data storage. Your data is protected with industry-leading security standards.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="group glass rounded-2xl p-8 border border-white/50 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
              <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                <BarChart3 className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">Analytics & Insights</h3>
              <p className="text-gray-600 leading-relaxed">
                Track performance with detailed analytics and reporting. Make data-driven decisions with real-time insights.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="group glass rounded-2xl p-8 border border-white/50 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
              <div className="w-16 h-16 bg-gradient-to-br from-teal-500 to-cyan-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                <CheckCircle className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">Easy Integration</h3>
              <p className="text-gray-600 leading-relaxed">
                Connect your social accounts and email services seamlessly. Get started in minutes, not days.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-olive-600 to-olive-700 text-white">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 text-center">
            <div className="animate-fade-in">
              <div className="text-5xl font-bold mb-2">10K+</div>
              <div className="text-olive-100">Active Users</div>
            </div>
            <div className="animate-fade-in" style={{ animationDelay: '0.1s' }}>
              <div className="text-5xl font-bold mb-2">1M+</div>
              <div className="text-olive-100">Prospects Discovered</div>
            </div>
            <div className="animate-fade-in" style={{ animationDelay: '0.2s' }}>
              <div className="text-5xl font-bold mb-2">50K+</div>
              <div className="text-olive-100">Messages Sent</div>
            </div>
            <div className="animate-fade-in" style={{ animationDelay: '0.3s' }}>
              <div className="text-5xl font-bold mb-2">99.9%</div>
              <div className="text-olive-100">Uptime</div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-32 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-20">
            <div className="inline-flex items-center space-x-2 px-4 py-2 bg-purple-50 rounded-full mb-6">
              <TrendingUp className="w-4 h-4 text-purple-600" />
              <span className="text-sm font-semibold text-purple-700">Simple Process</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
              How It <span className="text-olive-600">Works</span>
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Get started in three simple steps
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-12">
            <div className="text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl text-white text-3xl font-bold">
                1
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Connect Your Accounts</h3>
              <p className="text-gray-600 leading-relaxed">
                Link your social media accounts and email services. Secure OAuth integration takes just minutes.
              </p>
            </div>
            <div className="text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl text-white text-3xl font-bold">
                2
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Discover Prospects</h3>
              <p className="text-gray-600 leading-relaxed">
                Use our intelligent discovery engine to find prospects based on keywords, location, and categories.
              </p>
            </div>
            <div className="text-center">
              <div className="w-20 h-20 bg-gradient-to-br from-olive-500 to-olive-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl text-white text-3xl font-bold">
                3
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">Automate Outreach</h3>
              <p className="text-gray-600 leading-relaxed">
                Set up automated workflows to send personalized messages and track responses. Scale effortlessly.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-32 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-olive-50 via-white to-blue-50/30">
        <div className="max-w-4xl mx-auto text-center">
          <div className="glass rounded-3xl p-12 border border-white/50 shadow-2xl">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
              Ready to Scale Your Outreach?
            </h2>
            <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto">
              Join thousands of businesses using Liquid Canvas to discover prospects, automate outreach, and grow faster.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Link
                href="/login"
                className="group px-10 py-5 bg-gradient-to-r from-olive-600 to-olive-700 text-white rounded-2xl hover:shadow-2xl hover:scale-105 transition-all duration-300 font-bold text-lg flex items-center space-x-2 shadow-xl"
              >
                <span>Start Your Free Trial</span>
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <div className="flex items-center space-x-2 text-sm text-gray-600">
                <Clock className="w-4 h-4" />
                <span>No credit card required • 14-day free trial</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center space-x-3 mb-4 md:mb-0">
              <div className="w-10 h-10 bg-gradient-to-br from-olive-600 to-olive-700 rounded-xl flex items-center justify-center">
                <span className="text-white text-lg font-bold">LC</span>
              </div>
              <div>
                <p className="font-bold text-gray-900">Liquid Canvas</p>
                <p className="text-xs text-gray-500">Outreach Studio</p>
              </div>
            </div>
            <div className="text-center md:text-right">
              <p className="text-sm text-gray-600 mb-2">
                Powered by{' '}
                <a
                  href="https://liquidcanvas.art"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-olive-600 font-semibold hover:underline"
                >
                  liquidcanvas.art
                </a>
              </p>
              <p className="text-xs text-gray-500">
                © {new Date().getFullYear()} Liquid Canvas. All rights reserved.
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
