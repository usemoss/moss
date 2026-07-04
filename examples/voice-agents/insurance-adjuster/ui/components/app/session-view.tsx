'use client';

import { useState, useEffect } from 'react';
import { VoiceCenter } from './voice-center';
import { PolicyPanel } from './policy-panel';
import { DamageWorksheet } from './damage-worksheet';
import { RetrievalPanel } from './retrieval-panel';
import { useClaimState } from '@/hooks/useClaimState';
import type { ClaimState } from '@/hooks/useClaimState';
import { useMossInsuranceEvents } from '@/hooks/useMossInsuranceEvents';
import { cn } from '@/lib/utils';

interface SessionViewProps {
  onDisconnect: () => void;
}

function RightPanel({ claimState }: { claimState: ClaimState }) {
  const [tab, setTab] = useState<'policy' | 'findings'>('policy');

  // Auto-switch to findings when the first damage item is logged
  useEffect(() => {
    if (claimState.damageItems.length > 0) setTab('findings');
  }, [claimState.damageItems.length]);

  return (
    <aside className="flex h-full flex-col border-r border-[#1c2438] overflow-hidden">
      {/* Tab switcher */}
      <div className="flex shrink-0 border-b border-[#1c2438]">
        {(['policy', 'findings'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              'relative flex-1 py-2.5 text-[9px] font-bold uppercase tracking-widest transition-colors',
              tab === t ? 'text-[#d9e1ec]' : 'text-[#3f4f63] hover:text-[#6b7a8d]'
            )}
          >
            {tab === t && (
              <span className="absolute bottom-0 left-0 right-0 h-px bg-[#3b82f6]" />
            )}
            {t === 'policy' ? (
              'Policy'
            ) : (
              <span className="flex items-center justify-center gap-1">
                Findings
                {claimState.damageItems.length > 0 && (
                  <span className="font-mono text-[8px] text-[#16a34a]">
                    {claimState.damageItems.length}
                  </span>
                )}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Panel content */}
      <div className="flex-1 overflow-hidden">
        {tab === 'policy' ? (
          <PolicyPanel policyNumber={claimState.policyLoaded} />
        ) : (
          <DamageWorksheet claimState={claimState} />
        )}
      </div>
    </aside>
  );
}

export function SessionView({ onDisconnect }: SessionViewProps) {
  const claimState = useClaimState();
  const { events: mossEvents } = useMossInsuranceEvents();

  return (
    <div className="h-full grid grid-cols-[280px_1fr_260px] overflow-hidden bg-[#0d1117]">
      <RightPanel claimState={claimState} />
      <VoiceCenter claimState={claimState} onDisconnect={onDisconnect} />
      <RetrievalPanel events={mossEvents} />
    </div>
  );
}
