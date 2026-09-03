FROM node:20-alpine AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY package.json package-lock.json ./
COPY tsconfig.json ./
COPY eslint.config.mjs ./
COPY next-env.d.ts ./
COPY vitest.config.mts ./
COPY app ./app
COPY components ./components
COPY lib ./lib
COPY tests ./tests
COPY types ./types

RUN npm ci
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/package.json ./
COPY --from=builder /app/package-lock.json ./
COPY --from=builder /app/tsconfig.json ./
COPY --from=builder /app/eslint.config.mjs ./
COPY --from=builder /app/next-env.d.ts ./
COPY --from=builder /app/vitest.config.mts ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/app ./app
COPY --from=builder /app/components ./components
COPY --from=builder /app/lib ./lib
COPY --from=builder /app/tests ./tests
COPY --from=builder /app/types ./types

EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
