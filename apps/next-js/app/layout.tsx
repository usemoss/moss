import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import "./globals.css";

export const metadata: Metadata = {
  title: "Moss Real-time Semantic Search",
  description: "Real-time semantic search for conversational AI. Build and search your knowledge base with sub-10ms latency.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={GeistSans.variable}>
      <body>
        {children}
      </body>
    </html>
  );
}
