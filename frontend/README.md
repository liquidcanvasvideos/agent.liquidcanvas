# Art Outreach Scraper Dashboard

TypeScript/Next.js dashboard for the Autonomous Art Outreach Scraper.

## Features

- 📊 **Statistics Dashboard** - View leads, emails, and website metrics
- 📋 **Leads Table** - Browse all collected leads with filtering
- 📧 **Emails Table** - View sent and pending emails
- ⚙️ **Job Status** - Monitor background automation jobs
- 🔍 **Manual Scraping** - Scrape URLs directly from dashboard

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   # or
   yarn install
   ```

2. **Configure environment:**
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local with your API URL
   ```

3. **Run development server:**
   ```bash
   npm run dev
   # or
   yarn dev
   ```

4. **Open browser:**
   ```
   http://localhost:3000
   ```

## Environment Variables

- `NEXT_PUBLIC_API_BASE_URL` - FastAPI backend URL
  - **Production**: `https://agent.liquidcanvas.art/api/v1` (auto-detected)
  - **Local dev**: `http://localhost:8000/api/v1` (default)
  
  Create `frontend/.env.local` with:
  ```env
  NEXT_PUBLIC_API_BASE_URL=https://agent.liquidcanvas.art/api/v1
  ```

## Project Structure

```
frontend/
├── app/              # Next.js app directory
│   ├── page.tsx      # Main dashboard page
│   ├── layout.tsx    # Root layout
│   └── globals.css   # Global styles
├── components/        # React components
│   ├── StatsCards.tsx
│   ├── LeadsTable.tsx
│   ├── EmailsTable.tsx
│   ├── JobStatusPanel.tsx
│   └── ScrapeForm.tsx
├── lib/              # Utilities
│   └── api.ts        # API client functions
└── package.json
```

## API Integration

The dashboard connects to the FastAPI backend at `/api/v1/`:

- `GET /leads` - Get leads
- `GET /emails/sent` - Get sent emails
- `GET /emails/pending` - Get pending emails
- `GET /stats` - Get statistics
- `GET /jobs/latest` - Get job status
- `POST /scrape-url` - Scrape URL

See `lib/api.ts` for all API functions.

## Build for Production

```bash
npm run build
npm start
```

## Technologies

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Lucide React** - Icons

