'use client';

import { useCallback, useRef, useEffect } from 'react';
import {
  BarVisualizer,
  useVoiceAssistant,
  useLocalParticipant,
  useTranscriptions,
  RoomAudioRenderer,
  StartAudio,
} from '@livekit/components-react';
import { cn } from '@/lib/utils';
import type { ClaimState } from '@/hooks/useClaimState';

// ---- Agent state label ----

const STATE_CONFIG = {
  speaking:  { label: 'Speaking',   dot: 'bg-[#3b82f6]', text: 'text-[#3b82f6]' },
  listening: { label: 'Listening',  dot: 'bg-[#16a34a]', text: 'text-[#6b7a8d]' },
  thinking:  { label: 'Processing', dot: 'bg-[#f59e0b] animate-pulse', text: 'text-[#6b7a8d]' },
  idle:      { label: 'Ready',      dot: 'bg-[#263044]', text: 'text-[#3f4f63]' },
  connecting:{ label: 'Connecting', dot: 'bg-[#263044]', text: 'text-[#3f4f63]' },
} as const;

// ---- Top bar ----

function TopBar({
  claimState,
  onDisconnect,
  isMuted,
  onToggleMic,
}: {
  claimState: ClaimState;
  onDisconnect: () => void;
  isMuted: boolean;
  onToggleMic: () => void;
}) {
  const { state, audioTrack } = useVoiceAssistant();
  const cfg = STATE_CONFIG[state as keyof typeof STATE_CONFIG] ?? STATE_CONFIG.idle;

  return (
    <div className="flex items-center justify-between border-b border-[#1c2438] px-5 py-2.5">
      {/* Left: agent state + visualizer */}
      <div className="flex items-center gap-3">
        <div className="h-7 w-7 border border-[#1c2438] bg-[#161c28] shrink-0">
          <BarVisualizer
            state={state}
            track={audioTrack}
            barCount={4}
            options={{ minHeight: 2 }}
            className="flex h-full items-center justify-center gap-0.5 px-1"
          >
            <span className={cn(
              'w-0.5 min-h-0.5 transition-colors duration-100',
              state === 'speaking'
                ? 'bg-[#3b82f6] data-[lk-highlighted=true]:bg-[#60a5fa]'
                : 'bg-[#263044] data-[lk-highlighted=true]:bg-[#3b82f6]'
            )} />
          </BarVisualizer>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={cn('h-1.5 w-1.5 rounded-full', cfg.dot)} />
          <span className={cn('text-[11px] font-semibold uppercase tracking-widest', cfg.text)}>
            {cfg.label}
          </span>
        </div>
      </div>

      {/* Center: policy */}
      {claimState.policyLoaded && (
        <span className="font-mono text-xs text-[#6b7a8d]">{claimState.policyLoaded}</span>
      )}

      {/* Right: controls */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={onToggleMic}
          className={cn(
            'flex h-7 w-7 items-center justify-center border transition-colors',
            isMuted
              ? 'border-[#dc2626] bg-[#1c0505] text-[#dc2626]'
              : 'border-[#263044] text-[#6b7a8d] hover:border-[#3b82f6] hover:text-[#3b82f6]'
          )}
        >
          <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            {isMuted ? (
              <><line x1="1" y1="1" x2="23" y2="23" /><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" /><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" /></>
            ) : (
              <><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /></>
            )}
          </svg>
        </button>
        <button
          onClick={onDisconnect}
          className="flex h-7 w-7 items-center justify-center border border-[#263044] text-[#6b7a8d] transition-colors hover:border-[#dc2626] hover:text-[#dc2626]"
        >
          <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ---- Transcript entry ----

function TranscriptEntry({ text, isAgent }: { text: string; isAgent: boolean }) {
  return (
    <div className={cn('flex gap-3', isAgent ? 'justify-start' : 'justify-end')}>
      {isAgent && (
        <div className="mt-1 shrink-0">
          <span className="block h-1.5 w-1.5 rounded-full bg-[#2563eb] mt-1.5" />
        </div>
      )}
      <div className="max-w-[78%]">
        <p className={cn(
          'mb-0.5 text-[9px] font-bold uppercase tracking-widest',
          isAgent ? 'text-[#2563eb]' : 'text-[#3f4f63] text-right'
        )}>
          {isAgent ? 'Agent' : 'You'}
        </p>
        <div className={cn(
          'px-3.5 py-2.5 text-sm leading-relaxed',
          isAgent
            ? 'bg-[#161c28] text-[#c8d3e0]'
            : 'bg-[#0d1621] text-[#8fa8c8] border border-[#1e3356]'
        )}>
          {text}
        </div>
      </div>
      {!isAgent && (
        <div className="mt-1 shrink-0">
          <span className="block h-1.5 w-1.5 rounded-full bg-[#3f4f63] mt-1.5" />
        </div>
      )}
    </div>
  );
}

// ---- Main ----

interface VoiceCenterProps {
  claimState: ClaimState;
  onDisconnect: () => void;
}

export function VoiceCenter({ claimState, onDisconnect }: VoiceCenterProps) {
  const { localParticipant } = useLocalParticipant();
  const transcriptions = useTranscriptions();
  const bottomRef = useRef<HTMLDivElement>(null);

  const isMuted = !localParticipant.isMicrophoneEnabled;
  const toggleMic = useCallback(() => {
    localParticipant.setMicrophoneEnabled(isMuted);
  }, [localParticipant, isMuted]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcriptions.length]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <RoomAudioRenderer />
      <StartAudio label="Enable Audio" />

      <TopBar
        claimState={claimState}
        onDisconnect={onDisconnect}
        isMuted={isMuted}
        onToggleMic={toggleMic}
      />

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        {transcriptions.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center border border-[#1c2438]">
              <svg className="h-4 w-4 text-[#263044]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
              </svg>
            </div>
            <p className="text-xs text-[#263044]">Speak to begin the inspection</p>
          </div>
        ) : (
          <div className="mx-auto max-w-2xl space-y-4">
            {transcriptions.map((t, i) => {
              const isAgent = t.participantInfo.identity.startsWith('agent');
              return (
                <TranscriptEntry
                  key={`${t.participantInfo.identity}-${i}`}
                  text={t.text}
                  isAgent={isAgent}
                />
              );
            })}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
  );
}
