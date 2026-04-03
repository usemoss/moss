import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  serverExternalPackages: [
    "@inferedge/moss",
    "@huggingface/transformers",
    "onnxruntime-common",
    "onnxruntime-web",
    "sharp",
  ],
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "onnxruntime-node": "onnxruntime-web",
    };
    return config;
  },
};

export default nextConfig;
