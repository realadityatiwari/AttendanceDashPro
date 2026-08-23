# syntax=docker/dockerfile:1

# ────────────────────────────────────────────────────────────────────────
# AttendanceDash Pro — Frontend production image (Next.js 16 SSR + PWA)
#
# Multi-stage build:
#   deps    — install exact dependencies from the lockfile (npm ci)
#   builder — production build (next build)
#   runner  — minimal runtime using Next.js standalone output
#
# Requirements:
#   - Node 20+ (Next.js 16 requires Node 20.9+)
#   - NEXT_PUBLIC_API_URL must be provided as a build ARG (it is inlined
#     into the client bundle at build time — the only public env var).
#   - The Phase 13 PWA (manifest.json, service-worker.js, icons/) lives in
#     public/ and is copied into the runtime image unchanged (SSR preserved;
#     NOT a static export).
# ────────────────────────────────────────────────────────────────────────

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# Align npm with the version used to generate the lockfile (npm 11; the
# base image ships npm 10, which rejects npm-11 lockfile resolution).
RUN npm install -g npm@11 && npm ci --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Non-root runtime user (pre-existing `node` user in the node image)
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001

# Standalone output: minimal server + pruned node_modules
COPY --from=builder --chown=nodejs:nodejs /app/public ./public
COPY --from=builder --chown=nodejs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nodejs:nodejs /app/.next/static ./.next/static

USER nodejs

EXPOSE 3000
CMD ["node", "server.js"]
