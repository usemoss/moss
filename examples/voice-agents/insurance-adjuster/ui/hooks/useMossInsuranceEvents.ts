'use client';

import { useEffect, useMemo, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { useRoomContext } from '@livekit/components-react';

export type MossMatch = { text: string; score?: number };

export type MossInsuranceEvent = {
  id: string;
  source: 'policy' | 'claims-kb' | 'unknown';
  query: string;
  matches: MossMatch[];
  timeTakenMs: number | null;
  timestamp: number;
};

const decoder = new TextDecoder();

function parseEvent(payload: Uint8Array): MossInsuranceEvent | null {
  try {
    const raw = decoder.decode(payload);
    const msg = JSON.parse(raw);
    if (!msg || msg.type !== 'moss_context') return null;

    const data = msg.data as Record<string, unknown>;
    const query = typeof data.query === 'string' ? data.query : '';
    if (!query) return null;

    const indexName = typeof data.index_name === 'string' ? data.index_name : '';
    const source: MossInsuranceEvent['source'] = indexName.startsWith('policy-')
      ? 'policy'
      : indexName === 'claims-kb'
      ? 'claims-kb'
      : 'unknown';

    const matches: MossMatch[] = (Array.isArray(data.matches) ? data.matches : [])
      .filter((m): m is Record<string, unknown> => !!m && typeof m === 'object')
      .map((m) => ({
        text: typeof m.text === 'string' ? m.text : '',
        score: typeof m.score === 'number' ? m.score : undefined,
      }));

    const tsRaw = typeof data.timestamp === 'number' ? data.timestamp : Date.now() / 1000;
    const timeTakenMs = typeof data.time_taken_ms === 'number' ? data.time_taken_ms : null;

    return {
      id: `${tsRaw}-${source}-${query.slice(0, 20)}`,
      source,
      query,
      matches,
      timeTakenMs,
      timestamp: tsRaw * 1000,
    };
  } catch {
    return null;
  }
}

export function useMossInsuranceEvents(maxEvents = 20) {
  const room = useRoomContext();
  const [events, setEvents] = useState<MossInsuranceEvent[]>([]);

  useEffect(() => {
    if (!room) return;
    const handle = (payload: Uint8Array) => {
      const parsed = parseEvent(payload);
      if (!parsed) return;
      setEvents((prev) => {
        const next = [...prev, parsed];
        return maxEvents > 0 && next.length > maxEvents ? next.slice(-maxEvents) : next;
      });
    };
    room.on(RoomEvent.DataReceived, handle);
    return () => { room.off(RoomEvent.DataReceived, handle); };
  }, [room, maxEvents]);

  const policyEvents = useMemo(() => events.filter((e) => e.source === 'policy'), [events]);
  const kbEvents = useMemo(() => events.filter((e) => e.source === 'claims-kb'), [events]);

  return { events, policyEvents, kbEvents };
}
