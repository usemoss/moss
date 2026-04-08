# Multi-stage build for Moss Bun App
FROM oven/bun:1.3-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json bunfig.toml ./

# Install dependencies
RUN bun install --production

# Copy source code
COPY src ./src

# Build the application
RUN bun build src/index.ts --outdir dist --target bun


# Production stage
FROM oven/bun:1.3-alpine

WORKDIR /app

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Copy from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nodejs -u 1001

USER nodejs

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD bun run -e "fetch('http://localhost:3000/health').then(r => r.ok ? process.exit(0) : process.exit(1))" || exit 1

# Expose port
EXPOSE 3000

# Run with dumb-init to handle signals properly
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["bun", "run", "dist/index.js"]
