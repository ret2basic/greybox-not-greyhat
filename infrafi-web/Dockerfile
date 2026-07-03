# Use the official Node.js v22 image as the base
FROM node:22 AS base

# Install dependencies only when needed
FROM base AS deps

ARG NEXT_PUBLIC_PROJECT_ID
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET
ARG NEXT_PUBLIC_GLOW_QUOTE_SIMULATION_OWNER
ARG NEXT_PUBLIC_GLOW_VAULT_ADDRESS

ARG NODE_AUTH_TOKEN
ENV NODE_AUTH_TOKEN=$NODE_AUTH_TOKEN

# Set the working directory to /app
WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Create .npmrc with auth token
RUN echo "@DAWN-Foundation:registry=https://npm.pkg.github.com/" > .npmrc && \
    echo "//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}" >> .npmrc

# Install dependencies
RUN npm ci --no-audit --no-fund

# Rebuild the source code only when needed
FROM base AS builder

# NEXT_PUBLIC_* variables are inlined into the JS bundle at build time by
# webpack, so they must be available here — not just at container runtime.
ARG NEXT_PUBLIC_PROJECT_ID
ENV NEXT_PUBLIC_PROJECT_ID=$NEXT_PUBLIC_PROJECT_ID

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET
ENV NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET=$NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET

ARG NEXT_PUBLIC_GLOW_QUOTE_SIMULATION_OWNER
ENV NEXT_PUBLIC_GLOW_QUOTE_SIMULATION_OWNER=$NEXT_PUBLIC_GLOW_QUOTE_SIMULATION_OWNER

ARG NEXT_PUBLIC_GLOW_VAULT_ADDRESS
ENV NEXT_PUBLIC_GLOW_VAULT_ADDRESS=$NEXT_PUBLIC_GLOW_VAULT_ADDRESS

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy the rest of the app
COPY . .

# Build the Next.js app
# This will create a .next/standalone directory with the standalone build
RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner

WORKDIR /app

ENV NODE_ENV=production
ARG NEXT_PUBLIC_PROJECT_ID
ENV NEXT_PUBLIC_PROJECT_ID=$NEXT_PUBLIC_PROJECT_ID
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET
ENV NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET=$NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET
ARG NEXT_PUBLIC_GLOW_QUOTE_SIMULATION_OWNER
ENV NEXT_PUBLIC_GLOW_QUOTE_SIMULATION_OWNER=$NEXT_PUBLIC_GLOW_QUOTE_SIMULATION_OWNER
ARG NEXT_PUBLIC_GLOW_VAULT_ADDRESS
ENV NEXT_PUBLIC_GLOW_VAULT_ADDRESS=$NEXT_PUBLIC_GLOW_VAULT_ADDRESS

# Don't run as root
RUN groupadd --system --gid 1001 nodejs
RUN useradd --system --uid 1001 nextjs

# Copy the standalone build from builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/server.js ./server.js
COPY --from=deps --chown=nextjs:nodejs /app/node_modules/@next/env ./node_modules/@next/env
COPY --from=deps --chown=nextjs:nodejs /app/node_modules/ws ./node_modules/ws
RUN rm -f .env .env.local .env.* || true

USER nextjs

# Expose port 3000
EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Start Next.js server
CMD ["node", "server.js"]
