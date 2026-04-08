'use client';

import { useCallback, useRef, useState } from 'react';
import { Upload, FileText, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface UploadSectionProps {
	onUpload: (files: File[]) => void;
	isUploading: boolean;
}

export default function UploadSection({ onUpload, isUploading }: UploadSectionProps) {
	const [files, setFiles] = useState<File[]>([]);
	const [dragOver, setDragOver] = useState(false);
	const inputRef = useRef<HTMLInputElement>(null);

	const handleFiles = useCallback((newFiles: FileList | null) => {
		if (!newFiles) return;
		const pdfs = Array.from(newFiles).filter((f) => f.type === 'application/pdf');
		setFiles((prev) => {
			const existing = new Set(prev.map((f) => f.name));
			const unique = pdfs.filter((f) => !existing.has(f.name));
			return [...prev, ...unique].slice(0, 5);
		});
	}, []);

	const removeFile = (name: string) => {
		setFiles((prev) => prev.filter((f) => f.name !== name));
	};

	const handleDrop = useCallback(
		(e: React.DragEvent) => {
			e.preventDefault();
			setDragOver(false);
			handleFiles(e.dataTransfer.files);
		},
		[handleFiles]
	);

	const handleKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			inputRef.current?.click();
		}
	};

	const handleSubmit = () => {
		if (files.length > 0) {
			onUpload(files);
		}
	};

	return (
		<div className='space-y-6'>
			{/* Drop zone */}
			<label
				onDragOver={(e) => {
					e.preventDefault();
					setDragOver(true);
				}}
				onDragLeave={() => setDragOver(false)}
				onDrop={handleDrop}
				onKeyDown={handleKeyDown}
				tabIndex={0}
				role='button'
				aria-label='Upload PDF files - drag and drop or click to browse'
				className={`relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[--color-moss-cta] ${
					dragOver
						? 'border-[--color-moss-cta] bg-[--color-moss-cta]/[0.03]'
						: 'border-[--color-moss-border] hover:border-[--color-moss-border-light] hover:bg-gray-50/50'
				}`}
			>
				<input
					ref={inputRef}
					id='pdf-upload'
					type='file'
					accept='.pdf'
					multiple
					onChange={(e) => handleFiles(e.target.files)}
					className='hidden'
					aria-hidden='true'
				/>
				<div className='flex flex-col items-center gap-3'>
					<div className='rounded-full bg-gray-100 p-3'>
						<Upload className='h-5 w-5 text-[--color-moss-text]' />
					</div>
					<div>
						<p className='text-sm font-medium text-[--color-moss-title]'>Drop PDFs here or click to browse</p>
						<p className='mt-1 text-xs text-[--color-moss-muted]'>Up to 5 documents, PDF format</p>
					</div>
				</div>
			</div>

			{/* File list */}
			{files.length > 0 && (
				<div className='space-y-2'>
					{files.map((file) => (
						<div
							key={file.name}
							className='flex items-center justify-between rounded-lg border border-[--color-moss-border] bg-white px-4 py-3'
						>
							<div className='flex items-center gap-3 min-w-0'>
								<FileText className='h-4 w-4 flex-shrink-0 text-[--color-moss-text]' />
								<span className='text-sm text-[--color-moss-title] truncate'>{file.name}</span>
								<span className='text-xs text-[--color-moss-muted] flex-shrink-0'>
									{(file.size / 1024).toFixed(0)} KB
								</span>
							</div>
							<button
								type='button'
								onClick={(e) => {
									e.stopPropagation();
									removeFile(file.name);
								}}
								aria-label={`Remove ${file.name}`}
								className='ml-2 rounded p-1 text-[--color-moss-muted] hover:bg-gray-100 hover:text-[--color-moss-title] transition-colors'
							>
								<X className='h-4 w-4' />
							</button>
						</div>
					))}
				</div>
			)}

			{/* Upload button */}
			<Button
				onClick={handleSubmit}
				disabled={files.length === 0 || isUploading}
				className='w-full rounded-lg bg-moss-cta px-6 py-3 text-base font-normal text-white hover:opacity-90 transition-opacity duration-100 disabled:opacity-40 h-12'
			>
				{isUploading ? (
					<>
						<Loader2 className='h-4 w-4 animate-spin' />
						Uploading & Indexing...
					</>
				) : (
					<>
						<Upload className='h-4 w-4' />
						Upload & Index {files.length > 0 ? `(${files.length} file${files.length > 1 ? 's' : ''})` : ''}
					</>
				)}
			</Button>
		</div>
	);
}
