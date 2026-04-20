'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Github, Linkedin } from 'lucide-react';

export default function Footer() {
	return (
		<footer className='bg-moss-dark py-16 text-white border-t border-gray-800'>
			<div className='mx-auto max-w-6xl px-6'>
				<div className='container'>
					<div className='grid grid-cols-1 gap-12 md:grid-cols-3'>
						<div className='space-y-4'>
							<div className='flex items-center space-x-2'>
								<Image src='/Favicon.svg' alt='Moss Logo' width={32} height={32} className='h-8 w-8' />
								<span className='text-xl font-bold'>Moss</span>
							</div>
							<p className='text-base text-gray-400 leading-relaxed'>Real-time semantic search for Conversational AI.</p>
							<div className='space-y-1 text-sm text-gray-500 pt-4'>
								<p>&copy; 2026 InferEdge Inc.</p>
								<p>All rights reserved.</p>
								<p className='pt-1'>San Francisco, CA</p>
							</div>
						</div>

						<div className='space-y-4'>
							<h3 className='text-base font-semibold text-white'>Quick Links</h3>
							<nav className='flex flex-col space-y-3'>
								<Link href='https://www.moss.dev' className='text-gray-400 text-sm transition-colors hover:text-white'>Home</Link>
								<Link href='https://docs.moss.dev/docs' target='_blank' rel='noopener noreferrer' className='text-gray-400 text-sm transition-colors hover:text-white'>Docs</Link>
								<Link href='https://www.moss.dev/blog' className='text-gray-400 text-sm transition-colors hover:text-white'>Blog</Link>
							</nav>
						</div>

						<div className='space-y-4'>
							<h3 className='text-base font-semibold text-white'>Legal</h3>
							<nav className='flex flex-col space-y-3'>
								<Link href='https://docs.moss.dev/docs/privacy' target='_blank' rel='noopener noreferrer' className='text-gray-400 text-sm transition-colors hover:text-white'>Privacy Policy</Link>
								<Link href='https://docs.moss.dev/docs/tos' target='_blank' rel='noopener noreferrer' className='text-gray-400 text-sm transition-colors hover:text-white'>Terms of Service</Link>
							</nav>
						</div>
					</div>

					<div className='mt-12 flex flex-col items-center justify-between border-t border-gray-800 pt-8 md:flex-row'>
						<p className='mb-4 text-sm text-gray-500 md:mb-0'>Built with &#10084;&#65039; by the Moss team</p>
						<div className='flex items-center space-x-6'>
							<Link href='https://github.com/usemoss' target='_blank' className='text-gray-400 hover:text-white transition-colors duration-100'>
								<Github className='h-5 w-5' />
							</Link>
							<Link href='https://www.linkedin.com/company/mossdev' target='_blank' className='text-gray-400 hover:text-white transition-colors duration-100'>
								<Linkedin className='h-5 w-5' />
							</Link>
							<Link href='https://moss.link/discord' target='_blank' className='text-gray-400 hover:text-white transition-colors duration-100'>
								<svg className='h-5 w-5' viewBox='0 0 24 24' fill='currentColor'>
									<path d='M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z' />
								</svg>
							</Link>
							<Link href='https://x.com/usemoss' target='_blank' className='text-gray-400 hover:text-white transition-colors duration-100'>
								<Image src='/X.svg' alt='X (formerly Twitter)' width={20} height={20} className='h-5 w-5' />
							</Link>
						</div>
					</div>
				</div>
			</div>
		</footer>
	);
}
