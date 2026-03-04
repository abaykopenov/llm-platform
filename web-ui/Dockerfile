FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=production

# Copy pre-built standalone output (built locally on host)
COPY .next/standalone ./
COPY .next/static ./.next/static
COPY public ./public

EXPOSE 3000

CMD ["node", "server.js"]
