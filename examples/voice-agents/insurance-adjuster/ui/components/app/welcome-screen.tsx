'use client';

import { useState } from 'react';
import { cn, formatCurrency } from '@/lib/utils';
import { POLICIES, type PolicyData } from '@/lib/policies';

interface WelcomeScreenProps {
  onStartCall: (policyNumber: string, adjusterId: string) => void;
}

const STATE_COLORS: Record<string, string> = {
  FL: 'bg-blue-950 text-blue-300 border-blue-800',
  CA: 'bg-orange-950 text-orange-300 border-orange-800',
  TX: 'bg-red-950 text-red-300 border-red-800',
};

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
        'w-full rounded-xl border p-4 text-left transition-all duration-150',
        'bg-[#18181b] hover:bg-[#27272a]',
        selected
          ? 'border-amber-500 ring-1 ring-amber-500/40 shadow-lg shadow-amber-500/10'
          : 'border-[#3f3f46] hover:border-[#52525b]'
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-sm font-semibold text-amber-400">{policy.policyNumber}</p>
          <p className="mt-0.5 text-xs text-zinc-400">{policy.insurer}</p>
        </div>
        <span
          className={cn(
            'rounded border px-2 py-0.5 text-xs font-semibold tracking-wide',
            STATE_COLORS[policy.stateCode] ?? 'bg-zinc-800 text-zinc-300 border-zinc-700'
          )}
        >
          {policy.stateCode}
        </span>
      </div>

      <p className="text-sm font-medium text-zinc-200">{policy.address}</p>
      <p className="text-xs text-zinc-500">{policy.city}</p>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div>
          <span className="text-zinc-500">Dwelling</span>
          <span className="ml-1 font-semibold text-zinc-200">{formatCurrency(policy.coverageA)}</span>
        </div>
        <div>
          <span className="text-zinc-500">Built</span>
          <span className="ml-1 font-semibold text-zinc-200">{policy.yearBuilt}</span>
        </div>
        <div>
          <span className="text-zinc-500">Deductible</span>
          <span className="ml-1 font-semibold text-zinc-200">
            {formatCurrency(policy.standardDeductible)}
          </span>
        </div>
        <div>
          <span className="text-zinc-500">Claims</span>
          <span className="ml-1 font-semibold text-zinc-200">{policy.priorClaimsCount} prior</span>
        </div>
      </div>

      {policy.specialDeductibleLabel && (
        <div className="mt-2 rounded-md bg-amber-950/50 px-2 py-1 text-xs text-amber-300">
          ⚡ {policy.specialDeductibleLabel} = {formatCurrency(policy.specialDeductibleAmount!)}
        </div>
      )}

      {selected && (
        <div className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-amber-400">
          <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 0 1 1.06-1.06L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0z" />
          </svg>
          Selected
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
      setError('Adjuster ID must be in format A-NNNN (e.g. A-4412)');
      return;
    }
    setError('');
    onStartCall(selectedPolicy, cleanId);
  }

  return (
    <div className="flex h-full w-full items-center justify-center bg-[#09090b] p-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mb-4 flex justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 ring-1 ring-amber-500/30">
              <svg className="h-7 w-7 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.955 11.955 0 01.5 12.0a11.955 11.955 0 003.098 5.997 11.959 11.959 0 003.402 2.039 11.959 11.959 0 003 .5c1.063 0 2.112-.143 3.108-.42A11.959 11.959 0 0120.5 12c0-1.647-.332-3.218-.932-4.642" />
              </svg>
            </div>
          </div>
          <h1 className="text-2xl font-bold text-zinc-50">Claims Adjuster Assistant</h1>
          <p className="mt-1.5 text-sm text-zinc-400">
            Sub-10ms policy retrieval · On-device embedding · Powered by Moss
          </p>
        </div>

        {/* Adjuster ID */}
        <div className="mb-6 rounded-xl border border-[#3f3f46] bg-[#18181b] p-5">
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Adjuster ID
          </label>
          <input
            type="text"
            placeholder="e.g. A-4412"
            value={adjusterId}
            onChange={(e) => {
              setAdjusterId(e.target.value);
              setError('');
            }}
            onKeyDown={(e) => e.key === 'Enter' && handleStart()}
            className={cn(
              'w-full rounded-lg border bg-[#09090b] px-4 py-2.5 font-mono text-sm text-zinc-100',
              'placeholder:text-zinc-600 focus:outline-none focus:ring-2',
              error
                ? 'border-rose-500 focus:ring-rose-500/30'
                : 'border-[#3f3f46] focus:border-amber-500 focus:ring-amber-500/20'
            )}
          />
          {error && <p className="mt-1.5 text-xs text-rose-400">{error}</p>}
        </div>

        {/* Policy selector */}
        <div className="mb-6">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Select Policy
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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
          className={cn(
            'w-full rounded-xl py-3.5 text-sm font-semibold transition-all duration-150',
            'bg-amber-500 text-zinc-900 hover:bg-amber-400',
            'focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-[#09090b]',
            'shadow-lg shadow-amber-500/20'
          )}
        >
          Start Inspection Call
        </button>

        <p className="mt-4 text-center text-xs text-zinc-600">
          PII stays on-device · Moss embeds locally · No external embedding API
        </p>
      </div>
    </div>
  );
}
