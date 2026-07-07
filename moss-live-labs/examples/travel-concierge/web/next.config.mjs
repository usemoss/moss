/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // This app lives in a monorepo with other lockfiles; pin the tracing root here.
  outputFileTracingRoot: import.meta.dirname,
};

export default nextConfig;
