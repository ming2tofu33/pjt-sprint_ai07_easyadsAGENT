import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "개떡찰떡",
    short_name: "개떡찰떡",
    description: "대충 말해도 AI가 광고 브리프를 완성하는 이미지 광고 앱",
    start_url: "/",
    display: "standalone",
    background_color: "#f8f8f4",
    theme_color: "#f8f8f4",
    icons: [
      {
        src: "/brand/gaetteok-app-icon-192.png",
        sizes: "192x192",
        type: "image/png"
      },
      {
        src: "/brand/gaetteok-app-icon-512.png",
        sizes: "512x512",
        type: "image/png"
      }
    ]
  };
}
