import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Required for livekit-server-sdk (uses Node.js built-ins)
  serverExternalPackages: ['livekit-server-sdk'],
};

export default nextConfig;
