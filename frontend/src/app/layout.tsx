import type { Metadata, Viewport } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import { PwaRegister } from "@/components/PwaRegister";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "CivicGrid", template: "%s · CivicGrid" },
  description: "Ward-level issue reporting, civic services, and emergency coordination for Kathmandu Metropolitan City.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#083f3a",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <Providers>{children}</Providers>
        <PwaRegister />
      </body>
    </html>
  );
}
