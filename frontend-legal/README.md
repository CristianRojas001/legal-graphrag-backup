# Legal GraphRAG Frontend

Frontend application for the Legal GraphRAG system - A legal assistant for Spanish artists.

## Overview

This is a Next.js 15 application that provides a chat interface for querying legal information from official Spanish and EU sources (BOE, EUR-Lex). The system uses AI to generate accurate answers with proper citations.

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **UI Components**: Custom React components
- **Markdown Rendering**: react-markdown
- **API Client**: Axios

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running (default: http://localhost:8000)

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local

# Update .env.local with your backend URL
```

### Development

```bash
# Run development server
npm run dev

# Open browser
# Navigate to http://localhost:3000
```

### Build for Production

```bash
# Build application
npm run build

# Start production server
npm start
```

## Environment Variables

Create a `.env.local` file with:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME="Legal GraphRAG - Artisting"
NEXT_PUBLIC_APP_VERSION="1.0.0"
```

## Project Structure

```
frontend-legal/
├── src/
│   ├── app/                    # Next.js app router
│   │   ├── layout.tsx         # Root layout
│   │   ├── page.tsx           # Home page
│   │   └── globals.css        # Global styles
│   ├── components/            # React components
│   │   ├── LegalChatInterface.tsx    # Main chat UI
│   │   ├── SourceCard.tsx            # Source citation card
│   │   ├── LoadingSkeleton.tsx       # Loading state
│   │   ├── ErrorMessage.tsx          # Error display
│   │   └── LegalDisclaimer.tsx       # Legal warning
│   ├── services/              # API services
│   │   └── api.ts             # Backend API client
│   └── types/                 # TypeScript types
│       └── api.ts             # API response types
├── public/                    # Static assets
├── .env.local                 # Environment variables (local)
├── .env.example              # Environment template
└── package.json              # Dependencies
```

## Features

### Chat Interface
- Multi-turn conversation support
- Real-time message streaming
- Session management with UUID
- Auto-scroll to latest messages

### Source Citations
- Expandable source cards
- Direct links to official documents
- Source type indicators (BOE, EUR-Lex, DGT)
- Relevance scoring

### User Experience
- Responsive design (mobile & desktop)
- Loading skeletons during API calls
- Error handling with dismissible alerts
- Legal disclaimer banner
- Character counter (500 char limit)

### Accessibility
- Semantic HTML
- ARIA labels
- Keyboard navigation
- Screen reader support

## API Integration

The frontend connects to the Django backend at `/api/v1/legal-graphrag/`:

### Endpoints Used

1. **POST /chat/** - Submit legal queries
   - Request: `{ query: string, session_id?: string }`
   - Response: `{ answer: string, sources: LegalSource[] }`

2. **POST /search/** - Search legal documents
   - Request: `{ query: string, limit?: number }`
   - Response: `{ results: SearchResult[] }`

3. **GET /sources/** - Get corpus sources
   - Response: `{ sources: CorpusSource[], total: number }`

## Styling

Tailwind CSS v4 with custom configuration:
- Custom color palette (blue theme)
- Typography plugin for markdown
- Responsive breakpoints
- Dark mode ready (not enabled)

## Testing

```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Build check
npm run build
```

## Deployment

### Digital Ocean App Platform

1. Connect GitHub repository
2. Set build command: `npm run build`
3. Set start command: `npm start`
4. Add environment variables
5. Deploy

### Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

## Troubleshooting

### API Connection Issues

- Verify backend is running: `curl http://localhost:8000/api/v1/health/`
- Check CORS settings in Django
- Verify `NEXT_PUBLIC_API_URL` in `.env.local`

### Build Errors

- Clear Next.js cache: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && npm install`
- Check TypeScript errors: `npm run type-check`

## Future Enhancements

- [ ] Multi-language support (English, Catalan)
- [ ] Dark mode toggle
- [ ] Chat history persistence
- [ ] Export chat to PDF
- [ ] Voice input support
- [ ] Advanced search filters

## License

Proprietary - Artisting Platform

## Contact

For issues or questions, contact the Artisting development team.
