'use client';

import { VoiceCenter } from './voice-center';
import { useClaimState } from '@/hooks/useClaimState';
import { useMossInsuranceEvents } from '@/hooks/useMossInsuranceEvents';

interface SessionViewProps {
  onDisconnect: () => void;
}

export function SessionView({ onDisconnect }: SessionViewProps) {
  const claimState = useClaimState();
  const { events: mossEvents } = useMossInsuranceEvents();

  return (
    <div className="h-full bg-[#0d1117]">
      <VoiceCenter
        claimState={claimState}
        mossEvents={mossEvents}
        onDisconnect={onDisconnect}
      />
    </div>
  );
}
