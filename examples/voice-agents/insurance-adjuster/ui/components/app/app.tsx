'use client';

import { useState, useCallback } from 'react';
import { LiveKitRoom } from '@livekit/components-react';
import { WelcomeScreen } from './welcome-screen';
import { SessionView } from './session-view';

type ConnectionState =
  | { status: 'idle' }
  | { status: 'connecting'; policyNumber: string; adjusterId: string }
  | { status: 'connected'; policyNumber: string; serverUrl: string; token: string }
  | { status: 'error'; message: string };

export function App() {
  const [conn, setConn] = useState<ConnectionState>({ status: 'idle' });

  const handleStart = useCallback(async (policyNumber: string, adjusterId: string) => {
    setConn({ status: 'connecting', policyNumber, adjusterId });
    try {
      const res = await fetch('/api/connection-details', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ policyNumber }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setConn({
        status: 'connected',
        policyNumber,
        serverUrl: data.serverUrl,
        token: data.participantToken,
      });
    } catch (e) {
      setConn({ status: 'error', message: e instanceof Error ? e.message : 'Failed to connect' });
    }
  }, []);

  const handleDisconnect = useCallback(() => {
    setConn({ status: 'idle' });
  }, []);

  if (conn.status === 'idle') {
    return <WelcomeScreen onStartCall={handleStart} />;
  }

  if (conn.status === 'connecting') {
    return (
      <div className="flex h-full items-center justify-center gap-3 bg-[#09090b]">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
        <span className="text-sm text-zinc-400">Connecting…</span>
      </div>
    );
  }

  if (conn.status === 'error') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-[#09090b] p-8 text-center">
        <p className="text-sm text-rose-400">{conn.message}</p>
        <button
          onClick={() => setConn({ status: 'idle' })}
          className="rounded-lg bg-[#27272a] px-4 py-2 text-sm text-zinc-300 hover:bg-[#3f3f46]"
        >
          Back
        </button>
      </div>
    );
  }

  // Connected
  return (
    <LiveKitRoom
      serverUrl={conn.serverUrl}
      token={conn.token}
      connect={true}
      audio={true}
      video={false}
      onDisconnected={handleDisconnect}
      className="h-full"
    >
      <SessionView policyNumber={conn.policyNumber} onDisconnect={handleDisconnect} />
    </LiveKitRoom>
  );
}
