import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "CivicGrid Kathmandu Community Command Center",
    short_name: "CivicGrid",
    description: "Report ward issues, find services, and coordinate emergency support across Kathmandu Metropolitan City.",
    start_url: "/",
    display: "standalone",
    background_color: "#f3f7f5",
    theme_color: "#083f3a",
    icons: [],
  };
}
