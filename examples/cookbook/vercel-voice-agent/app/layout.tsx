import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'MOSS Voice Agent',
  description: 'Realtime voice agent powered by Vercel AI Gateway and MOSS semantic search',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{
        margin: 0,
        background: '#0a0a0a',
        color: '#f0f0ee',
        fontFamily: '"Inter", ui-sans-serif, system-ui, -apple-system, sans-serif',
        WebkitFontSmoothing: 'antialiased',
      }}>
        {children}
      </body>
    </html>
  );
}
