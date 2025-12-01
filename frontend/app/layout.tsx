import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import NoAlertScript from './no-alert-script'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Art Outreach Automation',
  description: 'Automated outreach system',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        {/* Fix favicon 404 error by providing proper link tag */}
        <link rel="icon" href="/favicon.ico" type="image/x-icon" />
        <link rel="shortcut icon" href="/favicon.ico" type="image/x-icon" />
        {/* Alternative: Use a data URI if favicon.ico doesn't exist */}
        {/* <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎨</text></svg>" /> */}
      </head>
      <body className={inter.className}>
        <NoAlertScript />
        {children}
      </body>
    </html>
  )
}

