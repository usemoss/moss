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
  turbopack: {
    resolveAlias: {
      "onnxruntime-node": "onnxruntime-web",
    },
  },
};

export default nextConfig;
