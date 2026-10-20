import type { Metadata } from "next";
import "@fontsource-variable/mona-sans";
import "@fontsource/courier-prime/400.css";
import "@fontsource/courier-prime/700.css";
import "./fonts.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "FraudLens | Financial crime operations",
  description:
    "A simulated multi-channel fraud detection and investigation workspace.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {/* Tanker and Erode come from Fontshare's CDN (see app/fonts.css). */}
        <link rel="preconnect" href="https://cdn.fontshare.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
