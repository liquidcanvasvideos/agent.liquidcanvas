'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { 
  ArrowRight, 
  CheckCircle, 
  Globe, 
  Users, 
  Mail, 
  Zap, 
  Shield, 
  TrendingUp,
  Play,
  Star,
  BarChart3
} from 'lucide-react'
import Link from 'next/link'

export default function LandingPage() {
  const router = useRouter()
  const [isScrolled, setIsScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20)
    }
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const features = [
    {
      icon: Globe,
      title: 'Website Discovery',
      description: 'Automatically discover and categorize relevant websites in your industry'
    },
    {
      icon: Users,
      title: 'Lead Management',
      description: 'Organize and manage your prospects with intelligent categorization'
    },
    {
      icon: Mail,
      title: 'Email Outreach',
      description: 'Streamline your email campaigns with automated drafting and sending'
    },
    {
      icon: Zap,
      title: 'Automation',
      description: 'Set up automated workflows to scale your outreach efforts'
    },
    {
      icon: Shield,
      title: 'Verification',
      description: 'Verify leads and ensure data quality before outreach'
    },
    {
      icon: TrendingUp,
      title: 'Analytics',
      description: 'Track performance and optimize your outreach strategy'
    }
  ]

  const stats = [
    { value: '10K+', label: 'Websites Discovered' },
    { value: '50K+', label: 'Leads Generated' },
    { value: '95%', label: 'Success Rate' },
    { value: '24/7', label: 'Automation' }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-olive-50/30">
      {/* Navigation */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled ? 'bg-white/90 backdrop-blur-md shadow-md' : 'bg-transparent'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-olive-600 flex items-center justify-center">
                <span className="text-white text-xs font-bold">LC</span>
              </div>
              <span className="text-lg font-bold text-olive-700">Liquid Canvas</span>
            </div>
            <div className="flex items-center space-x-4">
              <Link 
                href="/login"
                className="text-gray-700 hover:text-olive-700 transition-colors font-medium"
              >
                Sign In
              </Link>
              <Link
                href="/login"
                className="px-4 py-2 bg-olive-600 text-white rounded-lg hover:bg-olive-700 transition-colors font-medium"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center">
            <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
              Transform Your
              <span className="text-olive-600"> Outreach</span>
              <br />
              with Automation
            </h1>
            <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
              Liquid Canvas Outreach Studio helps you discover leads, manage prospects, 
              and automate your email campaigns—all in one powerful platform.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/login"
                className="px-8 py-4 bg-olive-600 text-white rounded-lg hover:bg-olive-700 transition-all shadow-lg hover:shadow-xl font-semibold text-lg flex items-center gap-2"
              >
                Get Started Free
                <ArrowRight className="w-5 h-5" />
              </Link>
              <button className="px-8 py-4 bg-white text-gray-700 rounded-lg hover:bg-gray-50 transition-all shadow-lg hover:shadow-xl font-semibold text-lg flex items-center gap-2 border border-gray-200">
                <Play className="w-5 h-5" />
                Watch Demo
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, index) => (
              <div key={index} className="text-center">
                <div className="text-4xl font-bold text-olive-600 mb-2">{stat.value}</div>
                <div className="text-gray-600">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Everything You Need to Scale
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Powerful features designed to streamline your outreach workflow
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => {
              const Icon = feature.icon
              return (
                <div
                  key={index}
                  className="p-6 rounded-xl border border-gray-200 hover:border-olive-300 hover:shadow-lg transition-all bg-white"
                >
                  <div className="w-12 h-12 rounded-lg bg-olive-100 flex items-center justify-center mb-4">
                    <Icon className="w-6 h-6 text-olive-600" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-gray-600">
                    {feature.description}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-olive-600 to-olive-700">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-white mb-4">
            Ready to Transform Your Outreach?
          </h2>
          <p className="text-xl text-olive-100 mb-8">
            Join thousands of businesses using Liquid Canvas to scale their outreach
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 px-8 py-4 bg-white text-olive-600 rounded-lg hover:bg-gray-50 transition-all shadow-lg hover:shadow-xl font-semibold text-lg"
          >
            Start Free Trial
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 sm:px-6 lg:px-8 bg-gray-900 text-gray-400">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-olive-600 flex items-center justify-center">
                  <span className="text-white text-xs font-bold">LC</span>
                </div>
                <span className="text-white font-bold">Liquid Canvas</span>
              </div>
              <p className="text-sm">
                Transform your outreach with intelligent automation
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Pricing</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Documentation</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Privacy</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Terms</a></li>
                <li><a href="https://liquidcanvas.art" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">liquidcanvas.art</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-gray-800 text-center text-sm">
            <p>&copy; {new Date().getFullYear()} Liquid Canvas. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

