'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { PolicyPanel } from './policy-panel';
import { DamageWorksheet } from './damage-worksheet';
import { VoiceCenter } from './voice-center';
import { useClaimState } from '@/hooks/useClaimState';
import { useMossInsuranceEvents } from '@/hooks/useMossInsuranceEvents';

// Mobile tab strip
type Tab = 'policy' | 'voice' | 'damage';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'policy', label: 'Policy', icon: '📋' },
  { id: 'voice', label: 'Voice', icon: '🎙' },
  { id: 'damage', label: 'Damage', icon: '📝' },
];

interface SessionViewProps {
  policyNumber: string;
  onDisconnect: () => void;
}

export function SessionView({ policyNumber, onDisconnect }: SessionViewProps) {
  const claimState = useClaimState();
  const { events: mossEvents } = useMossInsuranceEvents();
  const [activeTab, setActiveTab] = useState<Tab>('voice');

  // Use the policy from claim state if the agent loaded one, else use the pre-selected one
  const activePolicyNumber = claimState.policyLoaded ?? policyNumber;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#09090b]">
      {/* Desktop: 3-column layout */}
      <div className="hidden h-full md:grid md:grid-cols-[280px_1fr_300px]">
        {/* Left — Policy */}
        <div className="border-r border-[#27272a] overflow-hidden">
          <PolicyPanel policyNumber={activePolicyNumber} />
        </div>

        {/* Center — Voice */}
        <div className="overflow-hidden">
          <VoiceCenter
            claimState={claimState}
            mossEvents={mossEvents}
            onDisconnect={onDisconnect}
          />
        </div>

        {/* Right — Damage worksheet */}
        <div className="border-l border-[#27272a] overflow-hidden">
          <DamageWorksheet claimState={claimState} />
        </div>
      </div>

      {/* Mobile: tab-based layout */}
      <div className="flex h-full flex-col md:hidden">
        {/* Tab bar */}
        <div className="flex border-b border-[#27272a] bg-[#18181b]">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-semibold transition-all',
                activeTab === tab.id
                  ? 'border-b-2 border-amber-500 text-amber-400'
                  : 'text-zinc-500 hover:text-zinc-300'
              )}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.id === 'damage' && claimState.damageItems.length > 0 && (
                <span className="ml-0.5 rounded-full bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-400">
                  {claimState.damageItems.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'policy' && <PolicyPanel policyNumber={activePolicyNumber} />}
          {activeTab === 'voice' && (
            <VoiceCenter
              claimState={claimState}
              mossEvents={mossEvents}
              onDisconnect={onDisconnect}
            />
          )}
          {activeTab === 'damage' && <DamageWorksheet claimState={claimState} />}
        </div>
      </div>
    </div>
  );
}
