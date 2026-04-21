import type { Metadata } from 'next';
import { Playfair_Display } from 'next/font/google';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './globals.css';
import { Suspense } from 'react';
import Navbar from '@/components/common/navbar';
import Footer from '@/components/common/footer';
import { Toaster } from 'sonner';

const playfair = Playfair_Display({ subsets: ['latin'], variable: '--font-playfair' });

export const metadata: Metadata = {
	title: 'Moss + LlamaIndex | Document Intelligence Demo',
	description:
		'Upload PDFs and ask questions using LlamaIndex for parsing and Moss for sub-10ms semantic retrieval. RAG pipeline demo with instant context retrieval.',
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang='en' suppressHydrationWarning>
			<body className={`${GeistSans.variable} ${GeistMono.variable} ${playfair.variable} font-sans antialiased`}>
				<Suspense fallback={null}>
					<Navbar />
					{children}
					<Footer />
				</Suspense>
				<Toaster />
			</body>
		</html>
	);
}
