'use client';

import { useEffect, useMemo, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { useRoomContext } from '@livekit/components-react';

export type CoverageStatus = 'covered' | 'not_covered';

export type DamageItem = {
  index: number;
  description: string;
  estimatedValue: number;
  status: CoverageStatus;
  note: string;
};

export type ClaimState = {
  policyLoaded: string | null;
  damageItems: DamageItem[];
  totalCovered: number;
  totalNotCovered: number;
  reportSubmitted: boolean;
};

const EMPTY: ClaimState = {
  policyLoaded: null,
  damageItems: [],
  totalCovered: 0,
  totalNotCovered: 0,
  reportSubmitted: false,
};

const decoder = new TextDecoder();

type RawFinding = {
  description: string;
  estimated_value: number;
  covered: boolean;
  note: string;
};

function fromFindings(policy: string | null, findings: RawFinding[]): ClaimState {
  const items: DamageItem[] = findings.map((f, i) => ({
    index: i + 1,
    description: f.description,
    estimatedValue: f.estimated_value,
    status: f.covered ? 'covered' : 'not_covered',
    note: f.note,
  }));

  let covered = 0, notCovered = 0;
  for (const item of items) {
    if (item.status === 'covered') covered += item.estimatedValue;
    else notCovered += item.estimatedValue;
  }

  return { policyLoaded: policy, damageItems: items, totalCovered: covered, totalNotCovered: notCovered, reportSubmitted: false };
}

export function useClaimState(): ClaimState {
  const room = useRoomContext();
  const [state, setState] = useState<ClaimState>(EMPTY);

  useEffect(() => {
    if (!room) return;

    const handle = (payload: Uint8Array) => {
      try {
        const msg = JSON.parse(decoder.decode(payload));
        if (msg.type === 'claim_update') {
          setState({ ...fromFindings(msg.policy ?? null, msg.findings ?? []), reportSubmitted: false });
        } else if (msg.type === 'report_submitted') {
          setState((prev) => ({ ...prev, reportSubmitted: true }));
        }
      } catch {
        // not a claim message, ignore
      }
    };

    room.on(RoomEvent.DataReceived, handle);
    return () => { room.off(RoomEvent.DataReceived, handle); };
  }, [room]);

  return useMemo(() => state, [state]);
}
