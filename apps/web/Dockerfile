# SchoolOS web — Next.js build.
# Build context must be the monorepo root (docker build -f apps/web/Dockerfile .)
FROM node:22-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY packages/shared/package.json packages/shared/
COPY apps/web/package.json apps/web/
RUN npm ci --workspaces --ignore-scripts

FROM node:22-alpine AS build
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/packages/shared/node_modules ./packages/shared/node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY packages/shared ./packages/shared
COPY apps/web ./apps/web
WORKDIR /repo/apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /repo/apps/web
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
COPY --from=build /repo/apps/web/.next ./.next
COPY --from=build /repo/apps/web/public ./public
COPY --from=build /repo/apps/web/package.json ./package.json
COPY --from=build /repo/apps/web/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "start"]