import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Mark packages with native dependencies as external to prevent bundling
  serverExternalPackages: [
    "@inferedge/moss",
    "@huggingface/transformers",
    "onnxruntime",
    "onnxruntime-node",
  ],
  // Turbopack configuration (Next.js 16 default)
  turbopack: {
    resolveAlias: {},
  },
  // Also configure webpack as fallback
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals = [
        ...(Array.isArray(config.externals) ? config.externals : [config.externals].filter(Boolean)),
        "@inferedge/moss",
        "@huggingface/transformers",
        "onnxruntime",
        "onnxruntime-node",
      ];
    }
    return config;
  },
};

export default nextConfig;
