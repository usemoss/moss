'use client';

import { useState } from 'react';
import { cn, formatCurrency } from '@/lib/utils';
import { POLICIES, type PolicyData } from '@/lib/policies';

interface WelcomeScreenProps {
  onStartCall: (policyNumber: string, adjusterId: string) => void;
}

function PolicyCard({
  policy,
  selected,
  onSelect,
}: {
  policy: PolicyData;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full border p-4 text-left transition-all duration-100',
        'bg-[#161c28] hover:bg-[#1c2438]',
        selected
          ? 'border-[#2563eb] border-l-2 border-l-[#3b82f6]'
          : 'border-[#263044] hover:border-[#2d3a52]'
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-xs font-bold tracking-widest text-[#3b82f6] uppercase">
            {policy.policyNumber}
          </p>
          <p className="mt-0.5 text-xs text-[#6b7a8d]">{policy.insurer}</p>
        </div>
        <span className="rounded-sm bg-[#1c2438] border border-[#263044] px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-[#6b7a8d] uppercase">
          {policy.stateCode}
        </span>
      </div>

      <p className="text-sm font-medium text-[#d9e1ec]">{policy.address}</p>
      <p className="text-xs text-[#6b7a8d]">{policy.city}</p>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <div className="flex justify-between">
          <span className="text-[#6b7a8d]">Dwelling</span>
          <span className="font-mono font-semibold text-[#d9e1ec]">{formatCurrency(policy.coverageA)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[#6b7a8d]">Built</span>
          <span className="font-mono font-semibold text-[#d9e1ec]">{policy.yearBuilt}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[#6b7a8d]">Deductible</span>
          <span className="font-mono font-semibold text-[#d9e1ec]">{formatCurrency(policy.standardDeductible)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[#6b7a8d]">Prior claims</span>
          <span className="font-mono font-semibold text-[#d9e1ec]">{policy.priorClaimsCount}</span>
        </div>
      </div>

      {policy.specialDeductibleLabel && (
        <div className="mt-3 border border-[#263044] bg-[#0f1620] px-2.5 py-1.5 text-xs">
          <span className="text-[#6b7a8d]">{policy.specialDeductibleLabel}</span>
          <span className="ml-1 font-mono font-semibold text-[#d9e1ec]">
            {formatCurrency(policy.specialDeductibleAmount!)}
          </span>
        </div>
      )}
    </button>
  );
}

export function WelcomeScreen({ onStartCall }: WelcomeScreenProps) {
  const [selectedPolicy, setSelectedPolicy] = useState<string>('FL-HO3-001');
  const [adjusterId, setAdjusterId] = useState('');
  const [error, setError] = useState('');

  function handleStart() {
    const cleanId = adjusterId.trim().toUpperCase();
    if (!cleanId.match(/^A-\d{4}$/)) {
      setError('Format: A-NNNN (e.g. A-4412)');
      return;
    }
    setError('');
    onStartCall(selectedPolicy, cleanId);
  }

  return (
    <div className="flex h-full w-full items-center justify-center bg-[#0d1117] p-6">
      <div className="w-full max-w-xl">

        {/* Header */}
        <div className="mb-8">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-[#2563eb]">
            Moss Field Intelligence
          </p>
          <h1 className="text-xl font-semibold text-[#d9e1ec]">Claims Adjuster</h1>
          <p className="mt-1 text-xs text-[#6b7a8d]">
            Sub-10ms retrieval · On-device embedding · Multi-index ambient search
          </p>
        </div>

        {/* Adjuster ID */}
        <div className="mb-5">
          <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-widest text-[#6b7a8d]">
            Adjuster ID
          </label>
          <input
            type="text"
            placeholder="A-4412"
            value={adjusterId}
            onChange={(e) => { setAdjusterId(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleStart()}
            className={cn(
              'w-full border bg-[#0d1117] px-3 py-2.5 font-mono text-sm text-[#d9e1ec]',
              'placeholder:text-[#3f4f63] focus:outline-none',
              error
                ? 'border-[#dc2626]'
                : 'border-[#263044] focus:border-[#2563eb]'
            )}
          />
          {error && <p className="mt-1 text-xs text-[#dc2626]">{error}</p>}
        </div>

        {/* Policy selector */}
        <div className="mb-5">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-[#6b7a8d]">
            Select Policy
          </p>
          <div className="grid grid-cols-3 gap-px bg-[#263044]">
            {Object.values(POLICIES).map((policy) => (
              <PolicyCard
                key={policy.policyNumber}
                policy={policy}
                selected={selectedPolicy === policy.policyNumber}
                onSelect={() => setSelectedPolicy(policy.policyNumber)}
              />
            ))}
          </div>
        </div>

        {/* Start button */}
        <button
          onClick={handleStart}
          className="w-full bg-[#2563eb] py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1d4ed8] focus:outline-none focus:ring-1 focus:ring-[#2563eb] focus:ring-offset-1 focus:ring-offset-[#0d1117]"
        >
          Start Inspection Call
        </button>

        <p className="mt-4 text-center text-[10px] text-[#3f4f63]">
          PII stays on-device · No external embedding API
        </p>
      </div>
    </div>
  );
}
