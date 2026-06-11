const DEFAULT_BFF_BASE_URL = "http://127.0.0.1:4000";

function bffRemotePattern() {
  try {
    const bffUrl = new URL(process.env.NEXT_PUBLIC_BFF_BASE_URL || DEFAULT_BFF_BASE_URL);
    return {
      protocol: bffUrl.protocol.replace(":", ""),
      hostname: bffUrl.hostname,
      port: bffUrl.port,
      pathname: "/api/references/**"
    };
  } catch {
    return null;
  }
}

const bffPattern = bffRemotePattern();

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: bffPattern ? [bffPattern] : []
  }
};

export default nextConfig;
