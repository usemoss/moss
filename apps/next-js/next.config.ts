import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  serverExternalPackages: [
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
