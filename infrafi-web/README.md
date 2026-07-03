# Infrafi-Web

Retail crypto investment platform for DAWN - enabling investors to invest crypto into billbound and deployment.

## Tech Stack

- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript 5
- **UI Library:** React 19
- **Styling:** Tailwind CSS 4 + HeroUI
- **State Management:** Zustand
- **Node Version:** 22

## Prerequisites

- Node.js 22 (managed via mise - see `mise.toml`)

## Installation

### 1. Install Dependencies

```bash
npm install
```

### 2. Environment Setup

Create `.env.local` from template:

```bash
cp .env.template .env.local
```

Edit `.env.local` with your environment-specific values.

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues automatically
- `npm run fmt` - Format code with Prettier

## Commit Convention

This repository uses the DAWN commit message format:

```
[DAWN-xxx] type: commit message
```

Where:
- `DAWN-xxx` is your Linear ticket number
- `type` is one of: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
- commit message describes what you changed

**Examples:**
```
[DAWN-123] feat: add wallet connection
[DAWN-456] fix: resolve portfolio display issue
[DAWN-789] docs: update investment flow documentation
```

The commit message format is enforced by git hooks. Invalid messages will be rejected.

## Project Structure

```
infrafi-web/
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── layout.tsx      # Root layout with providers
│   │   ├── page.tsx        # Homepage
│   │   ├── globals.css     # Global styles
│   │   └── health/         # Health check endpoint
│   ├── ui-components/      # React components
│   │   └── shared/        # Shared UI components
│   ├── store/             # Zustand state management
│   │   ├── app.ts        # App state (theme, etc.)
│   │   ├── user.ts       # User/wallet state
│   │   └── index.ts      # Store exports
│   ├── hooks/            # Custom React hooks
│   ├── utils/            # Utility functions
│   ├── types/            # TypeScript type definitions
│   └── assets/           # Static assets
├── public/               # Static files served at root
└── scripts/              # Build/deployment scripts
```

## Development

### Health Check

A health check endpoint is available at `/health` for monitoring:

```bash
curl http://localhost:3000/health
```

Response:
```json
{
  "status": "ok",
  "timestamp": "2026-02-03T...",
  "service": "infrafi-web"
}
```

### Dark Mode

The application uses dark mode by default. Theme state is managed via Zustand and persisted in cookies.

## Next Steps

- Add wallet connection (Phantom/Metamask)
- Implement investment features (Buy/Stake)
- Create portfolio and dashboard pages
- Add CI/CD workflows
- Set up deployment infrastructure

## Contributing

1. Create a feature branch from `master`
2. Make your changes following the code style
3. Ensure all tests pass and linting is clean
4. Commit using the DAWN commit convention
5. Push and create a pull request

## License

Proprietary - DAWN Foundation
