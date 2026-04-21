'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Layers, ArrowRight } from 'lucide-react';
import Image from 'next/image';
import { toast } from 'sonner';
import UploadSection from '@/components/demo/upload-section';
import IndexingProgress from '@/components/demo/indexing-progress';
import ChatSection from '@/components/demo/chat-section';

type Phase = 'upload' | 'indexing' | 'ready';

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/llamaindex';

const INDEXING_STEPS = [
	'Parsing PDF with LiteParse',
	'Chunking content (400 words, 2-sentence overlap)',
	'Generating embeddings',
	'Building Moss index',
	'Ready for queries',
];

const FEATURES: { icon: React.ComponentType<{ className?: string }> | null; image?: { src: string; alt: string }; title: string; description: string }[] = [
	{
		icon: null,
		image: { src: '/liteparse.png', alt: 'LiteParse' },
		title: 'LiteParse',
		description: 'Spatial PDF parsing preserving document structure, tables, and layout.',
	},
	{
		icon: null,
		image: { src: '/Favicon.svg', alt: 'Moss' },
		title: 'Moss',
		description: 'Sub-10ms local vector search. No server round-trips, no latency spikes.',
	},
	{
		icon: Layers,
		title: 'Pipeline',
		description: 'Parse, chunk, embed, index, and retrieve — all in a single seamless flow.',
	},
];

export default function Home() {
	const [phase, setPhase] = useState<Phase>('upload');
	const [isUploading, setIsUploading] = useState(false);
	const [indexingStep, setIndexingStep] = useState(0);
	const [sessionId, setSessionId] = useState('');
	const [docCount, setDocCount] = useState(0);
	const [isSample, setIsSample] = useState(false);

	const handleUpload = useCallback(async (files: File[]) => {
		setIsUploading(true);

		try {
			const formData = new FormData();
			files.forEach((file) => formData.append('files', file));

			const res = await fetch(`${API_URL}/api/upload`, {
				method: 'POST',
				body: formData,
			});

			if (!res.ok) throw new Error('Upload failed');

			const data = await res.json();
			setPhase('indexing');
			setIsUploading(false);

			const totalSteps = INDEXING_STEPS.length;

			for (let i = 0; i < totalSteps; i++) {
				setIndexingStep(i);
				await new Promise((r) => setTimeout(r, 800));
			}

			setSessionId(data.session_id || data.sessionId);
			setDocCount(data.chunk_count || data.chunkCount || files.length);
			setPhase('ready');
		} catch (err) {
			toast.error('Failed to upload documents. Make sure the backend is running.');
			setIsUploading(false);
			setPhase('upload');
		}
	}, []);

	const loadSample = useCallback(async () => {
		setIsSample(true);
		setPhase('indexing');

		// Fire API call immediately — returns instantly (pre-indexed)
		const apiPromise = fetch(`${API_URL}/api/sample`).then((r) => {
			if (!r.ok) throw new Error('Failed to load sample');
			return r.json();
		});

		try {
			// Play the indexing animation as an illusion while API call runs in parallel
			for (let i = 0; i < INDEXING_STEPS.length; i++) {
				setIndexingStep(i);
				await new Promise((r) => setTimeout(r, 800));
			}

			const data = await apiPromise;
			setSessionId(data.session_id);
			setDocCount(data.chunk_count || 25);
			setPhase('ready');
		} catch {
			toast.error('Failed to load sample PDF.');
			setPhase('upload');
			setIsSample(false);
		}
	}, []);

	const handleReset = () => {
		setPhase('upload');
		setIndexingStep(0);
		setSessionId('');
		setDocCount(0);
		setIsSample(false);
	};

	return (
		<div className='bg-moss-bg min-h-screen'>
			{/* Hero */}
			<section className='mx-auto max-w-6xl px-6 pt-16 pb-12 md:pt-24 md:pb-16'>
				<div className='mx-auto max-w-3xl text-center'>
					<motion.div
						initial={{ opacity: 0, y: 12 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ duration: 0.5 }}
					>
						<p className='mb-3 text-xs font-medium uppercase tracking-[3px] text-[--color-moss-muted]'>
							Document Intelligence Demo
						</p>
						<h1 className='text-4xl font-light tracking-[-1.5px] text-[--color-moss-title] md:text-5xl lg:text-6xl font-[family-name:var(--font-playfair)]'>
							Search PDFs with
							<br />
							<span className='italic'>LlamaIndex + Moss</span>
						</h1>
					</motion.div>
					<motion.p
						initial={{ opacity: 0, y: 12 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ duration: 0.5, delay: 0.1 }}
						className='mt-6 text-base text-[--color-moss-text] leading-relaxed md:text-lg'
					>
						Upload PDFs, parse with LlamaIndex, and query with sub-10ms Moss retrieval.
						<br className='hidden md:block' />
						No infrastructure. No configuration. Just answers.
					</motion.p>
				</div>
			</section>

			{/* Feature cards */}
			<AnimatePresence mode='wait'>
				{phase === 'upload' && (
					<motion.section
						key='features'
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						className='mx-auto max-w-6xl px-6 pb-8'
					>
						<div className='grid grid-cols-1 gap-4 md:grid-cols-3'>
							{FEATURES.map((feat, i) => (
								<motion.div
									key={feat.title}
									initial={{ opacity: 0, y: 16 }}
									animate={{ opacity: 1, y: 0 }}
									transition={{ delay: 0.2 + i * 0.1 }}
									className='rounded-xl border border-[--color-moss-border] bg-white p-6 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5'
								>
									<div className='mb-3 inline-flex rounded-lg bg-gray-100 p-2.5'>
										{feat.image ? (
											<Image src={feat.image.src} alt={feat.image.alt} width={20} height={20} className='h-5 w-5 object-contain' />
										) : feat.icon ? (
											<feat.icon className='h-5 w-5 text-[--color-moss-title]' />
										) : null}
									</div>
									<h3 className='text-base font-medium text-[--color-moss-title]'>{feat.title}</h3>
									<p className='mt-1.5 text-sm leading-relaxed text-[--color-moss-text]'>{feat.description}</p>
								</motion.div>
							))}
						</div>
					</motion.section>
				)}
			</AnimatePresence>

			{/* Main content area */}
			<section className='mx-auto max-w-6xl px-6 pb-24'>
				<div className='mx-auto max-w-2xl'>
					<AnimatePresence mode='wait'>
						{phase === 'upload' && (
							<motion.div
								key='upload'
								initial={{ opacity: 0, y: 16 }}
								animate={{ opacity: 1, y: 0 }}
								exit={{ opacity: 0, y: -16 }}
								transition={{ duration: 0.3 }}
							>
								<div className='rounded-2xl border border-[--color-moss-border] bg-white p-6 md:p-8 shadow-sm'>
									<div className='mb-6'>
										<h2 className='text-xl font-medium text-[--color-moss-title] font-[family-name:var(--font-playfair)]'>
											Upload Documents
										</h2>
										<p className='mt-1 text-sm text-[--color-moss-text]'>
											Select PDF files to parse, index, and query.
										</p>
									</div>
									<div className='relative rounded-xl'>
										<svg className='absolute inset-0 w-full h-full pointer-events-none z-10 overflow-visible'>
											<rect
												x='0' y='0'
												width='100%' height='100%'
												rx='12' ry='12'
												fill='none'
												stroke='rgba(0,0,0,0.55)'
												strokeWidth='2'
												strokeLinecap='round'
												pathLength='100'
												strokeDasharray='8 92'
												className='animate-border-snake-svg'
											/>
										</svg>
										<button
											onClick={loadSample}
											disabled={isUploading}
											className='group relative cursor-pointer w-full overflow-hidden rounded-xl bg-gradient-to-br from-white/80 via-white to-white/80 backdrop-blur-sm px-4 py-4 shadow-[0_2px_16px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_24px_rgba(0,0,0,0.1)] active:scale-[0.99] transition-all disabled:opacity-50 disabled:cursor-not-allowed'
										>
										<div className='pointer-events-none absolute inset-0 animate-shine bg-gradient-to-r from-transparent via-white/70 to-transparent' style={{ width: '60%' }} />
										<div className='pointer-events-none absolute -top-10 -right-10 h-28 w-28 rounded-full bg-blue-200/20 blur-2xl' />
										<div className='pointer-events-none absolute -bottom-6 -left-6 h-20 w-20 rounded-full bg-purple-200/15 blur-2xl' />
										<div className='relative flex items-center gap-3'>
											<div className='flex-shrink-0 rounded-lg bg-white/70 shadow-sm border border-white/80 p-2.5 group-hover:bg-white/90 transition-all'>
												<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-[--color-moss-title]"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
											</div>
											<div className='text-left min-w-0'>
												<p className='text-sm font-medium text-[--color-moss-title]'>Try a sample — <span className='italic font-normal'>Attention Is All You Need</span></p>
												<p className='text-xs text-[--color-moss-muted] mt-0.5'>Click to load & start searching instantly</p>
											</div>
											<motion.div
												animate={{ x: [0, 4, 0] }}
												transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 2 }}
												className='flex-shrink-0 ml-auto self-center'
											>
												<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[--color-moss-title]/40 group-hover:text-[--color-moss-title] transition-colors"><path d="m9 18 6-6-6-6"/></svg>
											</motion.div>
										</div>
									</button>
									</div>
									<div className='relative flex items-center gap-3 my-5'>
										<div className='flex-1 border-t border-[--color-moss-border]' />
										<span className='text-xs text-[--color-moss-muted]'>or upload your own</span>
										<div className='flex-1 border-t border-[--color-moss-border]' />
									</div>
									<UploadSection onUpload={handleUpload} isUploading={isUploading} />
								</div>
							</motion.div>
						)}

						{phase === 'indexing' && (
							<motion.div
								key='indexing'
								initial={{ opacity: 0, y: 16 }}
								animate={{ opacity: 1, y: 0 }}
								exit={{ opacity: 0, y: -16 }}
								transition={{ duration: 0.3 }}
							>
								<div className='rounded-2xl border border-[--color-moss-border] bg-white p-6 md:p-8 shadow-sm'>
									<IndexingProgress currentStep={indexingStep} steps={INDEXING_STEPS} />
								</div>
							</motion.div>
						)}

						{phase === 'ready' && (
							<motion.div
								key='ready'
								initial={{ opacity: 0, y: 16 }}
								animate={{ opacity: 1, y: 0 }}
								exit={{ opacity: 0, y: -16 }}
								transition={{ duration: 0.3 }}
							>
								<div className='rounded-2xl border border-[--color-moss-border] bg-white p-6 md:p-8 shadow-sm'>
									<div className='mb-4 flex items-center justify-between'>
										<h2 className='text-xl font-medium text-[--color-moss-title] font-[family-name:var(--font-playfair)]'>
											Ask Questions
										</h2>
										<button
											onClick={handleReset}
											className='flex items-center gap-1 text-sm text-[--color-moss-text] hover:text-[--color-moss-title] transition-colors'
										>
											New session
											<ArrowRight className='h-3.5 w-3.5' />
										</button>
									</div>
									<ChatSection sessionId={sessionId} apiUrl={API_URL} docCount={docCount} isSample={isSample} />
								</div>
							</motion.div>
						)}
					</AnimatePresence>
				</div>
			</section>

			{/* Bottom CTA */}
			<section className='bg-moss-dark py-16 md:py-24'>
				<div className='mx-auto max-w-6xl px-6 text-center'>
					<h2 className='text-3xl font-light tracking-[-1px] text-white md:text-4xl font-[family-name:var(--font-playfair)]'>
						Make Your PDFs Searchable
					</h2>
					<p className='mx-auto mt-4 max-w-lg text-base text-gray-400 leading-relaxed'>
						Powered by <span className='text-gray-300'>LiteParse</span> parsing · <span className='text-gray-300'>Moss</span> vector search
					</p>
					<div className='mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row'>
						<a
							href='https://portal.usemoss.dev/auth/sign-up'
							target='_blank'
							rel='noopener noreferrer'
							className='inline-flex items-center justify-center rounded-lg bg-white px-6 py-3 text-base font-normal text-[--color-moss-dark] hover:opacity-90 transition-opacity duration-100'
						>
							Start Building
						</a>
						<a
							href='https://docs.moss.dev/docs'
							target='_blank'
							rel='noopener noreferrer'
							className='inline-flex items-center justify-center rounded-lg border border-gray-600 px-6 py-3 text-base font-normal text-white hover:border-gray-400 transition-colors duration-100'
						>
							Read Documentation
						</a>
					</div>
				</div>
			</section>
		</div>
	);
}
