'use client';

import { experimental_useRealtime as useRealtime } from '@ai-sdk/react';
import { gateway } from '@ai-sdk/gateway';
import { useMemo, useState } from 'react';

export default function Page() {
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const model = useMemo(
    () => gateway.experimental_realtime('openai/gpt-realtime-2'),
    [],
  );

  const { status, connect, disconnect, startAudioCapture, stopAudioCapture, isCapturing } =
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
      onError: (err) => {
        console.error('[realtime error]', err);
        setError(err instanceof Error ? err.message : String(err));
      },
      onToolCall: async ({ toolCall }) => {
        if (toolCall.toolName !== 'search_knowledge_base') return;
        const { query, topK } = toolCall.args as { query: string; topK?: number };
        setLog((l) => [`🔍 "${query}"`, ...l.slice(0, 9)]);

        const res = await fetch('/api/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, topK: topK ?? 5 }),
        });
        const text = await res.json() as string;
        setLog((l) => [`✓ returned context`, ...l.slice(0, 9)]);
        return text;
      },
    });

  const handleButton = async () => {
    setError(null);
    if (status === 'connected') {
      stopAudioCapture();
      disconnect();
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

  return (
    <main style={{ maxWidth: 480, margin: '4rem auto', fontFamily: 'sans-serif', padding: '0 1rem' }}>
      <h1 style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>MOSS Voice Agent</h1>
      <p style={{ color: '#6b7280', fontSize: '0.85rem', marginBottom: '2rem' }}>
        Vercel AI Gateway · gpt-realtime-2 · MOSS retrieval
      </p>

      <button
        onClick={handleButton}
        disabled={status === 'connecting'}
        style={{
          padding: '0.75rem 1.75rem',
          fontSize: '1rem',
          fontWeight: 600,
          borderRadius: 10,
          border: 'none',
          cursor: status === 'connecting' ? 'not-allowed' : 'pointer',
          background: status === 'connected' ? '#dc2626' : '#2563eb',
          color: '#fff',
          transition: 'background 0.15s',
        }}
      >
        {status === 'connecting' ? 'Connecting…'
          : status === 'connected' ? 'Stop'
          : 'Start talking'}
      </button>

      <p style={{ marginTop: '0.6rem', fontSize: '0.8rem', color: '#9ca3af' }}>
        Status: <strong>{status}</strong>
        {isCapturing && <span style={{ color: '#059669' }}> · mic active</span>}
      </p>

      {error && (
        <p style={{ marginTop: '0.5rem', color: '#dc2626', fontSize: '0.8rem' }}>⚠ {error}</p>
      )}

      {log.length > 0 && (
        <ul style={{ marginTop: '1.5rem', fontSize: '0.8rem', color: '#374151', paddingLeft: '1.2rem' }}>
          {log.map((entry, i) => <li key={i}>{entry}</li>)}
        </ul>
      )}
    </main>
  );
}
