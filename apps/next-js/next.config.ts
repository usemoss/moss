import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  serverExternalPackages: ["@inferedge/moss", "@huggingface/transformers"],
  turbopack: {},
};

export default nextConfig;
