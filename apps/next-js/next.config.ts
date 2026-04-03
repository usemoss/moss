import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  serverExternalPackages: [
    "onnxruntime-common",
    "onnxruntime-web",
    "sharp",
  ],
};

export default nextConfig;
