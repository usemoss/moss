import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Insurance Claims Adjuster',
  description: 'Field voice agent for property insurance claims adjusters, powered by Moss',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full overflow-hidden bg-[#0d1117] text-[#d9e1ec]">{children}</body>
    </html>
  );
}
