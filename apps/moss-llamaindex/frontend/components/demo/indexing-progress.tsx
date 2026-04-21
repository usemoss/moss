'use client';

import { motion } from 'motion/react';
import { Check, Loader2 } from 'lucide-react';

interface IndexingProgressProps {
	currentStep: number;
	steps: string[];
}

export default function IndexingProgress({ currentStep, steps }: IndexingProgressProps) {
	return (
		<div className='mx-auto max-w-md space-y-6'>
			<div className='text-center'>
				<div className='inline-flex items-center gap-2 rounded-full border border-[--color-moss-border] bg-white px-4 py-2 text-sm text-[--color-moss-title] shadow-sm'>
					<Loader2 className='h-4 w-4 animate-spin text-[--color-moss-cta]' />
					Processing documents...
				</div>
			</div>

			<div className='space-y-3'>
				{steps.map((step, i) => {
					const isComplete = i < currentStep;
					const isCurrent = i === currentStep;
					return (
						<motion.div
							key={step}
							initial={{ opacity: 0, y: 8 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ delay: i * 0.1 }}
							className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition-all duration-300 ${
								isComplete
									? 'border-green-200 bg-green-50/50'
									: isCurrent
									? 'border-[--color-moss-cta]/20 bg-white shadow-sm'
									: 'border-[--color-moss-border] bg-white opacity-50'
							}`}
						>
							<div
								className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-medium ${
									isComplete
										? 'bg-green-500 text-white'
										: isCurrent
										? 'bg-[--color-moss-cta] text-white'
										: 'bg-gray-100 text-[--color-moss-muted]'
								}`}
							>
								{isComplete ? <Check className='h-3.5 w-3.5' /> : isCurrent ? <Loader2 className='h-3.5 w-3.5 animate-spin' /> : i + 1}
							</div>
							<span
								className={`text-sm ${
									isComplete ? 'text-green-700' : isCurrent ? 'text-[--color-moss-title] font-medium' : 'text-[--color-moss-muted]'
								}`}
							>
								{step}
							</span>
						</motion.div>
					);
				})}
			</div>
		</div>
	);
}
