# Dockerfile for Moss Bun App
# Using Node.js base with Bun to ensure native bindings work
FROM node:20

WORKDIR /app

# Install Bun and dumb-init
RUN npm install -g bun && apt-get update && apt-get install -y dumb-init && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY package.json bun.lock ./

# Install dependencies
RUN bun install --production

# Copy source code
COPY src ./src

# Create non-root user for security
RUN groupadd -g 1001 nodejs && useradd -m -u 1001 -g nodejs nodejs
USER nodejs

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD bun -e "fetch('http://localhost:' + (process.env.PORT || 3000) + '/health').then(r => r.ok ? process.exit(0) : process.exit(1))" || exit 1
# Expose port
EXPOSE 3000

# Run with dumb-init to handle signals properly
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["bun", "run", "src/index.ts"]
