'use client';

import { useState, useRef, useCallback } from 'react';
import { Send, FileText, Loader2, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ShardDoc {
	text: string;
	score: number;
	source: string;
	page: number;
}

interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	shards?: ShardDoc[];
	totalShards?: number;
	done?: boolean;
	retrievalMs?: number;
}

const SAMPLE_QUESTIONS = [
	'How many training steps were used for base models?',
	'What is the inner-layer dimensionality of the position-wise feed-forward networks?',
];

interface ChatSectionProps {
	sessionId: string;
	apiUrl: string;
	docCount: number;
	isSample?: boolean;
}

export default function ChatSection({ sessionId, apiUrl, docCount, isSample }: ChatSectionProps) {
	const [messages, setMessages] = useState<Message[]>([]);
	const [input, setInput] = useState('');
	const [isStreaming, setIsStreaming] = useState(false);
	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const inputRef = useRef<HTMLTextAreaElement>(null);

	const handleSubmit = useCallback(async () => {
		const query = input.trim();
		if (!query || isStreaming) return;

		setInput('');
		const userMsg: Message = { id: Date.now().toString(), role: 'user', content: query };
		const assistantId = (Date.now() + 1).toString();
		const assistantMsg: Message = { id: assistantId, role: 'assistant', content: '', shards: [], done: false };

		setMessages((prev) => [...prev, userMsg, assistantMsg]);
		setIsStreaming(true);
		const retrievalStart = performance.now();

		const scrollToAssistant = () => {
			requestAnimationFrame(() => {
				const container = scrollContainerRef.current;
				const el = document.getElementById(`shards-${assistantId}`);
				if (container && el) {
					const elRect = el.getBoundingClientRect();
					const containerRect = container.getBoundingClientRect();
					container.scrollTop += elRect.top - containerRect.top - 4;
				}
			});
		};

		try {
			const res = await fetch(`${apiUrl}/api/chat/${sessionId}`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ question: query }),
			});

			if (!res.ok) throw new Error('Chat request failed');

			const reader = res.body?.getReader();
			if (!reader) throw new Error('No response stream');

			const decoder = new TextDecoder();
			let buffer = '';
			let firstShardReceived = false;

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';

				for (const line of lines) {
					if (!line.startsWith('data: ')) continue;
					const data = line.slice(6).trim();
					if (data === '[DONE]') continue;

					try {
						const parsed = JSON.parse(data);
						setMessages((prev) =>
							prev.map((m) => {
								if (m.id !== assistantId) return m;
								if (parsed.type === 'shard') {
									firstShardReceived = true;
									return {
										...m,
										shards: [...(m.shards || []), ...parsed.docs],
										totalShards: parsed.total,
										retrievalMs: parsed.time_ms ?? m.retrievalMs,
									};
								}
								if (parsed.type === 'done') {
									return { ...m, done: true };
								}
								return m;
							})
						);
						scrollToAssistant();
					} catch {
						// skip malformed lines
					}
				}
			}
		} catch (err) {
			setMessages((prev) =>
				prev.map((m) =>
					m.id === assistantId
						? { ...m, content: 'An error occurred while processing your question. Please try again.', done: true }
						: m
				)
			);
		} finally {
			setIsStreaming(false);
		}
	}, [input, isStreaming, apiUrl, sessionId]);

	const scoreColor = (score: number) => {
		if (score >= 0.8) return 'score-high';
		if (score >= 0.6) return 'score-medium';
		return 'score-low';
	};

	return (
		<div className='flex flex-col'>
			{/* Header info */}
			<div className='mb-3 flex items-center gap-2 text-sm text-[--color-moss-muted]'>
				<FileText className='h-4 w-4' />
				<span>{docCount} document{docCount !== 1 ? 's' : ''} indexed</span>
				<span className='text-[--color-moss-border]'>|</span>
				<span>Session: {sessionId.slice(0, 8)}...</span>
			</div>

			{/* Messages — constrained height, internal scroll */}
			<div ref={scrollContainerRef} className='space-y-4 overflow-y-auto scrollbar-thin pr-1 mb-3 h-[420px]'>
				{messages.length === 0 && (
					<div className='flex flex-col items-center justify-center py-16 text-center'>
						<div className='rounded-full bg-gray-100 p-4 mb-4'>
							<Send className='h-6 w-6 text-[--color-moss-muted]' />
						</div>
						<p className='text-[--color-moss-title] font-medium'>Ask a question about your documents</p>
						<p className='mt-1 text-sm text-[--color-moss-muted]'>Moss will retrieve relevant passages in under 10ms</p>
						{isSample && (
							<div className='mt-6 flex flex-col gap-2 w-full max-w-md'>
								<p className='text-xs text-[--color-moss-muted] uppercase tracking-wider'>Try these</p>
								{SAMPLE_QUESTIONS.map((q) => (
									<button
										key={q}
										onClick={() => { setInput(q); inputRef.current?.focus(); }}
										className='cursor-pointer rounded-lg border border-[--color-moss-border] bg-gray-50 px-4 py-2.5 text-left text-sm text-[--color-moss-title] hover:bg-gray-100 hover:border-[--color-moss-cta]/30 transition-colors'
									>
										{q}
									</button>
								))}
							</div>
						)}
					</div>
				)}

				{messages.map((msg) => (
					<div key={msg.id} id={`msg-${msg.id}`} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
						{msg.role === 'user' ? (
							<div className='max-w-[80%] rounded-2xl rounded-br-md bg-[--color-moss-cta] px-4 py-3 text-sm text-white'>
								{msg.content}
							</div>
						) : (
							<div className='w-full space-y-2'>
								{msg.content && (
									<div className='rounded-2xl rounded-bl-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700'>
										{msg.content}
									</div>
								)}

								{msg.shards && msg.shards.length > 0 && (
									<div className='space-y-2'>
										<div id={`shards-${msg.id}`} className='flex items-center gap-2 text-xs text-[--color-moss-muted]'>
											<span>{msg.shards.length} relevant passages found</span>
											{msg.retrievalMs != null && (
												<>
													<span className='text-[--color-moss-border]'>·</span>
													<span className='inline-flex items-center gap-1 font-mono'>
														<Clock className='h-3 w-3' />
														{msg.retrievalMs.toFixed(1)}ms
													</span>
												</>
											)}
										</div>
										{msg.shards.map((doc, i) => (
											<div
												key={i}
												className='rounded-lg border border-[--color-moss-border] bg-white p-4 hover:shadow-sm'
											>
												<div className='mb-2 flex items-center justify-between'>
													<div className='flex items-center gap-2'>
														<span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-mono font-medium ${scoreColor(doc.score)}`}>
															{doc.score.toFixed(3)}
														</span>
														<span className='text-xs text-[--color-moss-muted]'>
															p.{doc.page}
														</span>
													</div>
													<span className='text-xs text-[--color-moss-muted] truncate max-w-[150px]'>
														{doc.source}
													</span>
												</div>
												<p className='text-sm leading-relaxed text-[--color-moss-title]'>{doc.text}</p>
											</div>
										))}
									</div>
								)}

								{!msg.content && (!msg.shards || msg.shards.length === 0) && !msg.done && (
									<div className='flex items-center gap-2 rounded-lg border border-[--color-moss-border] bg-white px-4 py-3'>
										<Loader2 className='h-4 w-4 animate-spin text-[--color-moss-cta]' />
										<span className='text-sm text-[--color-moss-muted]'>Searching documents...</span>
									</div>
								)}
							</div>
						)}
					</div>
				))}
			</div>

			{/* Input */}
			<div className='relative'>
				<textarea
					ref={inputRef}
					value={input}
					onChange={(e) => setInput(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === 'Enter' && !e.shiftKey) {
							e.preventDefault();
							handleSubmit();
						}
					}}
					placeholder='Ask a question about your documents...'
					rows={1}
					className='w-full resize-none rounded-xl border border-[--color-moss-border] bg-white px-4 py-3 pr-12 text-sm text-[--color-moss-title] placeholder:text-[--color-moss-muted] focus:border-[--color-moss-cta] focus:outline-none focus:ring-1 focus:ring-[--color-moss-cta]/20'
				/>
				<button
					type='button'
					onClick={handleSubmit}
					disabled={!input.trim() || isStreaming}
					style={{
						backgroundColor: 'var(--color-moss-cta)',
						width: '28px',
						height: '28px',
						padding: 0,
						position: 'absolute',
						right: '8px',
						top: '50%',
						transform: 'translateY(-60%)',
						borderRadius: '6px',
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						color: 'white',
						border: 'none',
						cursor: 'pointer',
						opacity: !input.trim() || isStreaming ? 0.5 : 1,
					}}
				>
					{isStreaming ? <Loader2 style={{ width: 14, height: 14 }} className='animate-spin' /> : <Send style={{ width: 14, height: 14 }} />}
				</button>
			</div>
		</div>
	);
}
