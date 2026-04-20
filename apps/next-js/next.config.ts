import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // @moss-dev/moss-web is browser-only (WASM); no server externals needed for it
  serverExternalPackages: [],
  // Turbopack configuration (Next.js 16 default)
  turbopack: {
    resolveAlias: {},
  },
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Enable async WebAssembly for @moss-dev/moss-wasm
      config.experiments = { ...config.experiments, asyncWebAssembly: true };
      config.output.webassemblyModuleFilename = "static/wasm/[modulehash].wasm";
    }
    return config;
  },
};

export default nextConfig;
