import type { Metadata } from "next";
import "@fontsource-variable/mona-sans";
import "@fontsource/courier-prime/400.css";
import "@fontsource/courier-prime/700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "FraudLens | Financial crime operations",
  description:
    "A simulated multi-channel fraud detection and investigation workspace.",
};

// Tanker (posters) and Erode (titles) are served by Fontshare's own API: their
// licence allows embedding but not redistributing the files from this repository.
const FONTSHARE = "https://api.fontshare.com/v2/css?f[]=tanker@400&f[]=erode@500,600,700&display=swap";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://api.fontshare.com" />
        <link rel="preconnect" href="https://cdn.fontshare.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href={FONTSHARE} />
      </head>
      <body>{children}</body>
    </html>
  );
}
