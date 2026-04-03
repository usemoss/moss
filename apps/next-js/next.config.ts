import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Mark packages with native dependencies as external
  serverExternalPackages: [
    "@inferedge/moss",
    "@huggingface/transformers",
    "onnxruntime",
    "onnxruntime-node",
  ],
  // Turbopack config (Next.js 16 uses Turbopack by default)
  turbopack: {
    resolveAlias: {},
  },
};

export default nextConfig;
