# Liquid Canvas - Agent Frontend

The administrative dashboard for the Liquid Canvas Social Outreach Engine. Built with Next.js 14, Tailwind CSS, and Lucide Icons. (auto-deploy test 4)

## 🚀 Overview

The Agent Frontend provides a visual command center for managing the end-to-end social discovery and outreach pipeline. It allows users to trigger discovery jobs, review extracted leads, personalize AI-generated drafts, and monitor the health of automated campaigns across LinkedIn, Instagram, TikTok, and Facebook.

## 🛠️ Key

*   **Social Pipeline:** A kanban-style view of prospects as they move through the pipeline (Discovery -> Scraped -> Drafted -> Sent).
*   **Discovery Center:** Interface to launch targeted searches based on Category and Location constraints.
*   **Draft Editor:** AI-powered message personalization tool for reviewing and refining outreach messages.
*   **Job Monitor:** Real-time tracking of background DataForSEO and Playwright scraping tasks.
*   **Lead CRM:** Comprehensive table view of all discovered social profiles with advanced filtering.

## 📁 Repository Structure

```text
agent-frontend/
├── app/                  # Next.js App Router (Dashboard, Settings, Social)
├── components/           # Core UI Components (Tables, Pipeline, Modals)
├── hooks/                # Custom React hooks for data fetching & state
├── lib/                  # API clients and utility functions
├── public/               # Static assets and icons
├── tailwind.config.js    # Design system and theme configuration
└── next.config.js        # Next.js optimization and environment routing
```

## ⚙️ Setup & Installation

### Prerequisites
*   Node.js 18+
*   FastAPI Backend running (default: http://localhost:8000)

### Installation
1.  **Install dependencies:**
    ```bash
    npm install
    ```

2.  **Configure Environment:**
    Create a `.env.local` file:
    ```env
    NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
    ```

3.  **Run Development Server:**
    ```bash
    npm run dev
    ```

4.  **Open Dashboard:**
    Navigate to [http://localhost:3000](http://localhost:3000)

## 🎨 UI & Design System

The dashboard uses a modern, minimal aesthetic:
*   **Framework:** Next.js 14 (App Router)
*   **Styling:** Tailwind CSS
*   **Icons:** Lucide React
*   **Components:** Radix UI primitives for accessible modals and dropdowns.

## 🔗 Backend Integration

This frontend communicates with the `liquidcanvas` backend repository. Ensure the backend is active for discovery jobs and lead data to populate.

Deployment refresh trigger: 2026-02-10 (auto-deploy test 2)

Deployment refresh trigger: 2026-02-11 (vercel pick-up test)

---
*Liquid Canvas Agent Dashboard v2.0*
