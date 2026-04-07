'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Menu, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

const navItems = [
	{ name: 'Home', href: 'https://www.moss.dev' },
	{ name: 'Docs', href: 'https://docs.moss.dev/docs' },
	{ name: 'Pricing', href: 'https://www.moss.dev/pricing' },
	{ name: 'Blog', href: 'https://www.moss.dev/blog' },
];

export default function Navbar() {
	const [isOpen, setIsOpen] = useState(false);
	const [mounted, setMounted] = useState(false);

	useEffect(() => {
		setMounted(true);
	}, []);

	useEffect(() => {
		if (!mounted) return;
		if (isOpen) {
			document.body.style.overflow = 'hidden';
		} else {
			document.body.style.overflow = 'unset';
		}
		return () => {
			document.body.style.overflow = 'unset';
		};
	}, [isOpen, mounted]);

	const handleNav = (href: string) => {
		setIsOpen(false);
		if (href.startsWith('http')) {
			window.open(href, '_blank', 'noopener,noreferrer');
		}
	};

	return (
		<>
			<nav className='sticky top-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur-sm shadow-sm'>
				<div className='mx-auto flex h-16 max-w-6xl items-center justify-between px-6'>
					<div className='flex items-center gap-2 flex-shrink-0'>
						<Link href='/' className='flex items-center space-x-2 group'>
							<Image src='/Icon.png' alt='Moss Logo' width={32} height={32} className='object-contain' />
							<span className='text-xl font-extrabold tracking-tight text-[--color-moss-title]'>Moss</span>
						</Link>
					</div>

					<div className='hidden items-center space-x-8 text-sm md:flex'>
						{navItems.map((item) => (
							<button
								key={item.name}
								onClick={() => handleNav(item.href)}
								className='text-[--color-moss-text] text-sm font-medium hover:text-[--color-moss-title] transition-colors duration-100 cursor-pointer'
								disabled={!mounted}
							>
								{item.name}
							</button>
						))}
						<div className='hidden md:flex items-center ml-4'>
							<Link
								href='https://portal.usemoss.dev/auth/sign-up'
								target='_blank'
								rel='noopener noreferrer'
							>
								<button className='text-sm font-semibold rounded-lg px-5 py-2.5 bg-moss-cta text-white hover:opacity-90 transition-opacity duration-100 cursor-pointer'>
									Start Free
								</button>
							</Link>
						</div>
					</div>

					<div className='z-[70] flex md:hidden'>
						<Button variant='ghost' size='icon' onClick={() => setIsOpen(!isOpen)} aria-label='Toggle navigation' className='relative'>
							<Menu className='h-6 w-6' />
						</Button>
					</div>
				</div>
			</nav>

			<AnimatePresence>
				{isOpen && (
					<>
						<motion.div
							initial={{ opacity: 0 }}
							animate={{ opacity: 1 }}
							exit={{ opacity: 0 }}
							transition={{ duration: 0.2 }}
							className='fixed inset-0 z-40 bg-black/50 md:hidden'
							onClick={() => setIsOpen(false)}
						/>
						<motion.div
							initial={{ x: '100%' }}
							animate={{ x: 0 }}
							exit={{ x: '100%' }}
							transition={{ type: 'tween', duration: 0.3, ease: 'easeInOut' }}
							className='fixed top-0 right-0 z-60 h-full w-64 bg-white shadow-2xl md:hidden'
						>
							<div className='flex flex-col p-6 pt-6'>
								<div className='mb-4 flex justify-end'>
									<Button variant='ghost' size='icon' onClick={() => setIsOpen(false)} aria-label='Close navigation' className='h-8 w-8'>
										<X className='h-5 w-5' />
									</Button>
								</div>
								<nav className='flex flex-col gap-6 text-lg'>
									{navItems.map((item, index) => (
										<motion.button
											key={item.name}
											initial={{ opacity: 0, x: -20 }}
											animate={{ opacity: 1, x: 0 }}
											transition={{ delay: index * 0.1 + 0.1 }}
											onClick={() => handleNav(item.href)}
											className='text-left transition-colors hover:text-gray-900'
											disabled={!mounted}
										>
											{item.name}
										</motion.button>
									))}
									<motion.div
										initial={{ opacity: 0, x: -20 }}
										animate={{ opacity: 1, x: 0 }}
										transition={{ delay: navItems.length * 0.1 + 0.1 }}
										className='flex flex-col gap-3 mt-4 pt-4 border-t border-gray-200'
									>
										<Link href='https://portal.usemoss.dev/auth/sign-up' target='_blank' rel='noopener noreferrer' onClick={() => setIsOpen(false)}>
											<Button className='w-full text-lg hover:cursor-pointer'>Sign Up</Button>
										</Link>
									</motion.div>
								</nav>
							</div>
						</motion.div>
					</>
				)}
			</AnimatePresence>
		</>
	);
}
