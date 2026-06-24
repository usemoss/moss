'use client';

import { useCallback, useState } from 'react';
import {
  BarVisualizer,
  useVoiceAssistant,
  useLocalParticipant,
  useChat,
  RoomAudioRenderer,
  StartAudio,
} from '@livekit/components-react';
import { Track } from 'livekit-client';
import { cn } from '@/lib/utils';
import type { ClaimState } from '@/hooks/useClaimState';
import type { MossInsuranceEvent } from '@/hooks/useMossInsuranceEvents';

// ---- Adjuster status bar ----

function StatusBadge({
  active,
  label,
  sub,
}: {
  active: boolean;
  label: string;
  sub?: string;
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-all',
        active
          ? 'border-emerald-800 bg-emerald-950/60 text-emerald-400'
          : 'border-[#3f3f46] bg-[#18181b] text-zinc-600'
      )}
    >
      <div
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          active ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-zinc-600'
        )}
      />
      <span className="font-semibold">{label}</span>
      {sub && <span className="font-mono text-[10px] opacity-70">{sub}</span>}
    </div>
  );
}

function AdjusterHeader({ claimState }: { claimState: ClaimState }) {
  return (
    <div className="flex items-center justify-between border-b border-[#27272a] px-4 py-2.5">
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500/10">
          <svg className="h-3.5 w-3.5 text-amber-400" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12.735 14c.618 0 1.093-.561.872-1.139a6.002 6.002 0 0 0-11.215 0c-.22.578.254 1.139.872 1.139h9.47z" />
          </svg>
        </div>
        <span className="text-xs font-semibold text-zinc-300">
          {claimState.adjusterID ?? 'Not verified'}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <StatusBadge
          active={claimState.adjusterVerified}
          label="ID Verified"
          sub={claimState.adjusterID ?? undefined}
        />
        <StatusBadge
          active={!!claimState.policyLoaded}
          label="Policy"
          sub={
            claimState.policyLoaded
              ? `${claimState.policyLoaded} · ${claimState.policyLoadedMs}ms`
              : undefined
          }
        />
      </div>
    </div>
  );
}

// ---- Moss retrieval indicator ----

function MossRetrievalPill({ event }: { event: MossInsuranceEvent }) {
  const [expanded, setExpanded] = useState(false);

  const sourceLabel = event.source === 'policy' ? '📋 Policy' : event.source === 'claims-kb' ? '📚 KB' : '🔍';
  const sourceStyle =
    event.source === 'policy'
      ? 'border-amber-800 bg-amber-950/40 text-amber-300'
      : 'border-zinc-700 bg-zinc-800/60 text-zinc-300';

  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      className={cn(
        'w-full rounded-lg border px-3 py-2 text-left transition-all',
        sourceStyle
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="shrink-0 text-xs">{sourceLabel}</span>
          <span className="truncate text-xs">{event.query}</span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5 text-[10px]">
          {event.timeTakenMs != null && (
            <span className="font-mono font-semibold text-emerald-400">{event.timeTakenMs.toFixed(0)}ms</span>
          )}
          <span className="text-zinc-500">{event.matches.length} hits</span>
          <svg
            className={cn('h-3 w-3 transition-transform', expanded && 'rotate-180')}
            viewBox="0 0 12 12" fill="currentColor"
          >
            <path d="M6 8L1 3h10L6 8z" />
          </svg>
        </div>
      </div>
      {expanded && event.matches.length > 0 && (
        <div className="mt-2 space-y-1.5 border-t border-current/10 pt-2">
          {event.matches.slice(0, 3).map((m, i) => (
            <p key={i} className="text-[11px] text-zinc-400 leading-relaxed line-clamp-2">
              {m.text}
            </p>
          ))}
        </div>
      )}
    </button>
  );
}

// ---- Chat transcript ----

type ChatMessage = { id: string; from?: { name?: string; isAgent?: boolean }; message: string; timestamp: number };

function TranscriptMessage({ message }: { message: ChatMessage }) {
  const isAgent = message.from?.isAgent;
  return (
    <div className={cn('flex gap-2', isAgent ? 'justify-start' : 'justify-end')}>
      {isAgent && (
        <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500/20">
          <svg className="h-3 w-3 text-amber-400" viewBox="0 0 12 12" fill="currentColor">
            <circle cx="6" cy="6" r="5" />
          </svg>
        </div>
      )}
      <div
        className={cn(
          'max-w-[80%] rounded-xl px-3 py-2 text-xs leading-relaxed',
          isAgent
            ? 'bg-[#27272a] text-zinc-200'
            : 'bg-amber-500/10 text-amber-100 border border-amber-900/40'
        )}
      >
        {message.message}
      </div>
    </div>
  );
}

// ---- Agent voice visualizer ----

function VoiceVisualizer() {
  const { state, audioTrack } = useVoiceAssistant();

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative flex h-24 w-24 items-center justify-center">
        {/* Outer glow ring */}
        <div
          className={cn(
            'absolute inset-0 rounded-full transition-all duration-300',
            state === 'speaking'
              ? 'bg-amber-500/10 ring-2 ring-amber-500/30 shadow-xl shadow-amber-500/10'
              : 'bg-zinc-800/50 ring-1 ring-[#3f3f46]'
          )}
        />
        <div className="relative z-10 h-20 w-20 rounded-full bg-[#18181b] ring-1 ring-[#27272a] overflow-hidden">
          <BarVisualizer
            state={state}
            trackRef={audioTrack}
            barCount={7}
            options={{ minHeight: 4 }}
            className="flex h-full items-center justify-center gap-1 px-3"
          >
            <span className="bg-zinc-700 min-h-1 w-1.5 rounded-full origin-center transition-colors data-[lk-highlighted=true]:bg-amber-400 data-[lk-muted=true]:bg-zinc-800" />
          </BarVisualizer>
        </div>
      </div>

      <div className="text-center">
        <p className="text-xs font-semibold text-zinc-300">
          {state === 'speaking'
            ? 'Agent Speaking'
            : state === 'listening'
            ? 'Listening…'
            : state === 'thinking'
            ? 'Thinking…'
            : 'Agent Ready'}
        </p>
        <p className="mt-0.5 text-[10px] text-zinc-600">
          {state === 'thinking' ? 'Querying Moss…' : 'Sub-10ms retrieval'}
        </p>
      </div>
    </div>
  );
}

// ---- Main component ----

interface VoiceCenterProps {
  claimState: ClaimState;
  mossEvents: MossInsuranceEvent[];
  onDisconnect: () => void;
}

export function VoiceCenter({ claimState, mossEvents, onDisconnect }: VoiceCenterProps) {
  const { localParticipant } = useLocalParticipant();
  const { chatMessages } = useChat();

  const isMuted = localParticipant.isMicrophoneEnabled === false;

  const toggleMic = useCallback(() => {
    localParticipant.setMicrophoneEnabled(isMuted);
  }, [localParticipant, isMuted]);

  const recentMoss = mossEvents.slice(-6).reverse();
  const recentMessages = chatMessages.slice(-20);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <RoomAudioRenderer />
      <StartAudio label="Enable Audio" />

      {/* Adjuster status bar */}
      <AdjusterHeader claimState={claimState} />

      {/* Voice visualizer */}
      <div className="border-b border-[#27272a] px-4 py-6">
        <VoiceVisualizer />
      </div>

      {/* Moss retrieval events (dual-source) */}
      {recentMoss.length > 0 && (
        <div className="border-b border-[#27272a] p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
            Last Retrieval
          </p>
          <div className="space-y-1.5">
            {recentMoss.slice(0, 2).map((e) => (
              <MossRetrievalPill key={e.id} event={e} />
            ))}
          </div>
        </div>
      )}

      {/* Chat transcript */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="space-y-2">
          {recentMessages.map((msg) => (
            <TranscriptMessage key={msg.id} message={msg as ChatMessage} />
          ))}
          {chatMessages.length === 0 && (
            <p className="text-center text-xs text-zinc-600 py-4">
              Conversation will appear here
            </p>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="border-t border-[#27272a] p-4">
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={toggleMic}
            className={cn(
              'flex h-12 w-12 items-center justify-center rounded-full transition-all',
              isMuted
                ? 'bg-rose-600 text-white hover:bg-rose-500'
                : 'bg-[#27272a] text-zinc-300 hover:bg-[#3f3f46]'
            )}
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? (
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="1" y1="1" x2="23" y2="23" />
                <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
                <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            ) : (
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            )}
          </button>

          <button
            onClick={onDisconnect}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-[#27272a] text-zinc-400 transition-all hover:bg-rose-950 hover:text-rose-400"
            title="End call"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 8.25V6a2.25 2.25 0 0 0-2.25-2.25H6A2.25 2.25 0 0 0 3.75 6v8.25A2.25 2.25 0 0 0 6 16.5h2.25m.75-3 3 3m0 0 3-3m-3 3V10.5" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
