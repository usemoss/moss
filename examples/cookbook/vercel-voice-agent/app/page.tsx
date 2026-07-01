'use client';

import { experimental_useRealtime as useRealtime } from '@ai-sdk/react';
import { gateway } from '@ai-sdk/gateway';
import { useMemo, useState } from 'react';

type SearchEntry = { query: string; hits: number };

// MOSS design tokens (dark mode) — monochromatic white-based brand
const c = {
  bg:        '#0a0a0a',
  bgAlt:     '#111110',
  bgElevated:'#181816',
  border:    '#222220',
  borderSub: '#1a1a18',
  text1:     '#f0f0ee',
  text2:     '#888',
  text3:     '#555',
  brand:     '#e8e8e4',   // MOSS brand — warm near-white
  brandDim:  '#ccccc6',
  brandGlow: 'rgba(232,232,228,0.06)',
  green:     '#10b981',
  greenGlow: 'rgba(16,185,129,0.12)',
};

export default function Page() {
  const [connected, setConnected] = useState(false);
  const [searches, setSearches] = useState<SearchEntry[]>([]);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const model = useMemo(
    () => gateway.experimental_realtime('openai/gpt-realtime-2'),
    [],
  );

  const { connect, disconnect, startAudioCapture, stopAudioCapture, isCapturing } =
    useRealtime({
      model,
      api: { token: '/api/token' },
      sessionConfig: {
        voice: 'alloy',
        turnDetection: { type: 'server-vad' },
        instructions:
          'You are a helpful voice assistant with access to a knowledge base. ' +
          'Always call search_knowledge_base before answering factual questions. ' +
          'Keep answers brief — two or three sentences.',
      },
      onError: (err) => setError(err instanceof Error ? err.message : String(err)),
      onEvent: (event) => {
        if (event.type === 'session-created') setConnected(true);
        if (event.type === 'audio-delta')      setIsSpeaking(true);
        if (event.type === 'audio-done')       setIsSpeaking(false);
      },
      onToolCall: async ({ toolCall }) => {
        if (toolCall.toolName !== 'search_knowledge_base') return;
        const { query, topK } = toolCall.args as { query: string; topK?: number };
        const res = await fetch('/api/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, topK: topK ?? 5 }),
        });
        const text = await res.text();
        const hits = text.trim() ? text.split('\n\n---\n\n').length : 0;
        setSearches((s) => [{ query, hits }, ...s.slice(0, 4)]);
        return text;
      },
    });

  const handleToggle = async () => {
    setError(null);
    if (connected) {
      stopAudioCapture();
      disconnect();
      setConnected(false);
      setIsSpeaking(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        await connect();
        startAudioCapture(stream);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }
  };

  const phase = !connected ? 'idle'
    : isSpeaking   ? 'speaking'
    : isCapturing  ? 'listening'
    : 'ready';

  const orbGlow = phase === 'speaking'  ? c.brandGlow
    : phase === 'listening' ? 'rgba(255,255,255,0.04)'
    : phase === 'ready'     ? c.greenGlow
    : 'transparent';

  const orbBorder = phase === 'speaking'  ? c.brand
    : phase === 'listening' ? '#3a3a38'
    : phase === 'ready'     ? c.green
    : c.border;

  const statusColor = phase === 'speaking'  ? c.brand
    : phase === 'listening' ? c.text1
    : phase === 'ready'     ? c.green
    : c.text3;

  const statusLabel = phase === 'speaking'  ? 'Speaking'
    : phase === 'listening' ? 'Listening'
    : phase === 'ready'     ? 'Ready'
    : 'Tap to start';

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      position: 'relative',
    }}>

      {/* Subtle radial bg */}
      <div style={{
        position: 'fixed',
        inset: 0,
        background: phase === 'speaking'
          ? `radial-gradient(ellipse 50% 35% at 50% 55%, ${c.brandGlow}, transparent)`
          : 'none',
        transition: 'background 1s ease',
        pointerEvents: 'none',
      }} />

      {/* Logo */}
      <header style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        padding: '1.25rem 2rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: `1px solid ${c.borderSub}`,
        zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <img
            src="/moss-logo.png"
            alt="MOSS"
            width={28}
            height={28}
            style={{ borderRadius: 6, display: 'block' }}
          />
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: c.text1, letterSpacing: '-0.01em' }}>
            MOSS
          </span>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.375rem',
          padding: '0.3rem 0.75rem',
          borderRadius: 6,
          background: c.bgElevated,
          border: `1px solid ${c.border}`,
          fontSize: '0.72rem',
          color: c.text2,
        }}>
          <span style={{
            width: 5, height: 5, borderRadius: '50%',
            background: connected ? (phase === 'speaking' ? c.brand : c.green) : c.border,
            transition: 'background 0.3s',
          }} />
          Voice Agent
        </div>
      </header>

      {/* Main content */}
      <main style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '2.5rem',
        zIndex: 1,
        width: '100%',
        maxWidth: 400,
      }}>

        {/* Orb */}
        <div style={{ position: 'relative' }}>
          {/* Glow ring */}
          <div style={{
            position: 'absolute',
            inset: -16,
            borderRadius: '50%',
            background: orbGlow,
            transition: 'background 0.4s ease',
            pointerEvents: 'none',
          }} />

          <button
            onClick={handleToggle}
            aria-label={connected ? 'End conversation' : 'Start conversation'}
            style={{
              width: 88,
              height: 88,
              borderRadius: '50%',
              border: `1.5px solid ${orbBorder}`,
              cursor: 'pointer',
              background: c.bgElevated,
              boxShadow: phase === 'speaking'
                ? `0 0 0 4px ${c.brandGlow}, inset 0 1px 0 rgba(255,255,255,0.06)`
                : `inset 0 1px 0 rgba(255,255,255,0.04)`,
              transition: 'all 0.3s ease',
              transform: phase === 'speaking' ? 'scale(1.04)' : 'scale(1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Inner shimmer */}
            <div style={{
              position: 'absolute',
              inset: 0,
              background: phase === 'speaking'
                ? `radial-gradient(circle at 40% 35%, ${c.brandGlow}, transparent 60%)`
                : phase === 'listening'
                ? 'radial-gradient(circle at 40% 35%, rgba(255,255,255,0.04), transparent 60%)'
                : 'none',
              transition: 'background 0.3s',
            }} />
            <MicIcon active={connected} speaking={isSpeaking} />
          </button>
        </div>

        {/* Status */}
        <div style={{ textAlign: 'center' }}>
          <p style={{
            margin: 0,
            fontSize: '0.9375rem',
            fontWeight: 500,
            color: statusColor,
            letterSpacing: '-0.01em',
            transition: 'color 0.3s',
          }}>
            {statusLabel}
          </p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: c.text3 }}>
            {connected
              ? 'gpt-realtime-2 · MOSS · server VAD'
              : 'Click to connect · gpt-realtime-2'}
          </p>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            width: '100%',
            padding: '0.6rem 0.875rem',
            borderRadius: 8,
            background: 'rgba(239,68,68,0.06)',
            border: '1px solid rgba(239,68,68,0.18)',
            fontSize: '0.78rem',
            color: '#fca5a5',
          }}>
            {error}
          </div>
        )}

        {/* MOSS search log */}
        {searches.length > 0 && (
          <div style={{ width: '100%' }}>
            <p style={{
              margin: '0 0 0.6rem',
              fontSize: '0.65rem',
              fontWeight: 600,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: c.text3,
            }}>
              Knowledge lookups
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              {searches.map((s, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.625rem',
                  padding: '0.5rem 0.75rem',
                  background: c.bgAlt,
                  border: `1px solid ${c.border}`,
                  borderRadius: 10,
                  fontSize: '0.78rem',
                  transition: 'border-color 0.2s',
                }}>
                  <span style={{ color: c.brand, fontSize: '0.55rem', flexShrink: 0 }}>◆</span>
                  <span style={{
                    flex: 1,
                    color: c.text2,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {s.query}
                  </span>
                  <span style={{
                    color: c.text3,
                    flexShrink: 0,
                    fontSize: '0.72rem',
                  }}>
                    {s.hits} result{s.hits !== 1 ? 's' : ''}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <style>{`
        @keyframes pulse-ring {
          0%, 100% { transform: scale(1); opacity: 0.5; }
          50% { transform: scale(1.06); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function MicIcon({ active, speaking }: { active: boolean; speaking: boolean }) {
  const color = speaking ? '#7200E1' : active ? '#f0f0ee' : '#555';
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ transition: 'all 0.3s', position: 'relative' }}>
      <rect x="9" y="2" width="6" height="12" rx="3" fill={color} />
      <path d="M5 10a7 7 0 0 0 14 0" stroke={color} strokeWidth="1.75" strokeLinecap="round" />
      <line x1="12" y1="17" x2="12" y2="21" stroke={color} strokeWidth="1.75" strokeLinecap="round" />
      <line x1="8" y1="21" x2="16" y2="21" stroke={color} strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}
