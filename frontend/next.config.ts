import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // The guide is read from disk at request time; the standalone build copies
  // only the files it traces, so name it here.
  outputFileTracingIncludes: {
    "/przewodnik.pdf": ["./content/guide/*.pdf"],
  },
};

export default nextConfig;
