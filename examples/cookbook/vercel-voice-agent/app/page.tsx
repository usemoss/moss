'use client';

import { useRef, useState } from 'react';

type Status = 'idle' | 'recording' | 'processing' | 'speaking';

export default function Page() {
  const [status, setStatus] = useState<Status>('idle');
  const [transcript, setTranscript] = useState('');
  const [reply, setReply] = useState('');
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    if (status !== 'idle') return;
    setError(null);

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });

    const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    chunksRef.current = [];

    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      runPipeline(new Blob(chunksRef.current, { type: 'audio/webm' }));
    };

    recorder.start();
    recorderRef.current = recorder;
    setStatus('recording');
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop();
      recorderRef.current = null;
      setStatus('processing');
    }
  };

  const runPipeline = async (blob: Blob) => {
    try {
      const res = await fetch('/api/pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'audio/webm' },
        body: blob,
      });

      if (res.status === 204) {
        setError('No speech detected');
        setStatus('idle');
        return;
      }
      if (!res.ok) throw new Error(`Pipeline failed: ${res.status}`);

      const raw = res.headers.get('X-Transcript');
      if (raw) setTranscript(decodeURIComponent(raw));

      const rawReply = res.headers.get('X-Reply');
      if (rawReply) setReply(decodeURIComponent(rawReply));

      const audioBlob = await res.blob();
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      setStatus('speaking');
      audio.onended = () => { URL.revokeObjectURL(url); setStatus('idle'); };
      audio.onerror = () => { URL.revokeObjectURL(url); setStatus('idle'); };
      audio.play();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus('idle');
    }
  };

  const busy = status !== 'idle';

  return (
    <main style={{ maxWidth: 520, margin: '4rem auto', fontFamily: 'sans-serif', padding: '0 1rem' }}>
      <h1 style={{ fontSize: '1.6rem', marginBottom: '0.25rem' }}>MOSS Voice Agent</h1>
      <p style={{ color: '#6b7280', fontSize: '0.85rem', marginBottom: '2rem' }}>
        Deepgram STT · GPT-4.1 Mini · Deepgram TTS · MOSS retrieval
      </p>

      <button
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onTouchStart={(e) => { e.preventDefault(); startRecording(); }}
        onTouchEnd={(e) => { e.preventDefault(); stopRecording(); }}
        disabled={status === 'processing' || status === 'speaking'}
        style={{
          padding: '1rem 2.5rem',
          fontSize: '1rem',
          fontWeight: 600,
          borderRadius: 12,
          border: 'none',
          cursor: busy && status !== 'recording' ? 'not-allowed' : 'pointer',
          background:
            status === 'recording'  ? '#dc2626' :
            status === 'processing' ? '#6b7280' :
            status === 'speaking'   ? '#059669' : '#2563eb',
          color: '#fff',
          userSelect: 'none',
          WebkitUserSelect: 'none',
          transition: 'background 0.15s',
        }}
      >
        {status === 'recording'  ? '🎙 Release to send'
          : status === 'processing' ? 'Transcribing…'
          : status === 'speaking'   ? '🔊 Speaking…'
          : '● Hold to speak'}
      </button>

      <p style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#9ca3af' }}>
        {status === 'idle' ? 'Press and hold, speak, then release.' : `Status: ${status}`}
      </p>

      {error && (
        <p style={{ marginTop: '0.75rem', color: '#dc2626', fontSize: '0.82rem' }}>⚠ {error}</p>
      )}

      {transcript && (
        <div style={{ marginTop: '1.5rem', padding: '0.75rem 1rem', background: '#f3f4f6', borderRadius: 8 }}>
          <p style={{ fontSize: '0.72rem', color: '#9ca3af', margin: '0 0 0.25rem' }}>YOU</p>
          <p style={{ margin: 0, fontSize: '0.9rem' }}>{transcript}</p>
        </div>
      )}

      {reply && (
        <div style={{ marginTop: '0.75rem', padding: '0.75rem 1rem', background: '#eff6ff', borderRadius: 8 }}>
          <p style={{ fontSize: '0.72rem', color: '#93c5fd', margin: '0 0 0.25rem' }}>AGENT</p>
          <p style={{ margin: 0, fontSize: '0.9rem' }}>{reply}</p>
        </div>
      )}
    </main>
  );
}
