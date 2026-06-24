import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Insurance Claims Adjuster',
  description: 'Field voice agent for property insurance claims adjusters, powered by Moss',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full overflow-hidden bg-[#09090b] text-[#f4f4f5]">{children}</body>
    </html>
  );
}
