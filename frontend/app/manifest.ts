import type { MetadataRoute } from "next"
import { INK, PAPER } from "@/lib/brand"

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Corvus",
    short_name: "Corvus",
    start_url: "/",
    display: "browser",
    background_color: PAPER,
    theme_color: INK,
    icons: [
      { src: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/brand/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  }
}
