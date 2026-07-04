'use client';

import { cn, formatCurrency } from '@/lib/utils';
import { POLICIES, type PolicyData } from '@/lib/policies';

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-[#1c2438]">
      <p className="px-4 pt-3 pb-1 text-[9px] font-semibold uppercase tracking-widest text-[#3f4f63]">
        {label}
      </p>
      <div className="px-4 pb-3">{children}</div>
    </div>
  );
}

function Row({ label, value, mono, accent }: { label: string; value: string; mono?: boolean; accent?: boolean }) {
  return (
    <div className="flex items-baseline justify-between py-1">
      <span className="text-xs text-[#6b7a8d]">{label}</span>
      <span className={cn(
        'text-xs',
        mono && 'font-mono',
        accent ? 'font-semibold text-[#d9e1ec]' : 'text-[#93a3b8]'
      )}>
        {value}
      </span>
    </div>
  );
}

export function PolicyPanel({ policyNumber }: { policyNumber: string | null }) {
  const policy: PolicyData | null = policyNumber ? POLICIES[policyNumber] ?? null : null;

  if (!policy) {
    return (
      <aside className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
        <p className="text-xs text-[#3f4f63]">No policy loaded</p>
      </aside>
    );
  }

  return (
    <aside className="flex h-full flex-col overflow-y-auto">
      {/* Header */}
      <div className="border-b border-[#263044] px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-mono text-xs font-bold uppercase tracking-widest text-[#3b82f6]">
              {policy.policyNumber}
            </p>
            <p className="mt-0.5 text-[10px] text-[#6b7a8d]">{policy.policyType}</p>
          </div>
          <span className="border border-[#263044] bg-[#1c2438] px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-[#6b7a8d] uppercase">
            {policy.stateCode}
          </span>
        </div>
        <p className="mt-2 text-sm font-medium text-[#d9e1ec]">{policy.address}</p>
        <p className="text-xs text-[#6b7a8d]">{policy.city}</p>
      </div>

      {/* Property */}
      <Section label="Property">
        <Row label="Year built" value={String(policy.yearBuilt)} />
        <Row label="Roof" value={String(policy.roofYear)} />
        <Row label="Area" value={`${policy.sqft.toLocaleString()} sqft`} />
        <Row label="Construction" value={policy.construction} />
      </Section>

      {/* Coverage */}
      <Section label="Coverage Limits">
        <Row label="A: Dwelling" value={formatCurrency(policy.coverageA)} mono accent />
        <Row label="B: Other Structures" value={`${formatCurrency(policy.coverageB)} (10%)`} mono />
        <Row label={`C: Personal Property (${policy.coverageC})`} value={formatCurrency(policy.coverageCLimit)} mono />
        <Row label="D: Loss of Use" value={formatCurrency(policy.coverageD)} mono />
        <Row label="E: Liability" value={formatCurrency(policy.coverageE)} mono />
        <Row label="F: Medical" value={formatCurrency(policy.coverageF)} mono />
      </Section>

      {/* Deductibles */}
      <Section label="Deductibles">
        <Row label="All-peril" value={formatCurrency(policy.standardDeductible)} mono />
        {policy.specialDeductibleLabel && policy.specialDeductibleAmount != null && (
          <div className="mt-1.5 border border-[#263044] bg-[#0f1a2e] px-2.5 py-2">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] text-[#93c5fd]">{policy.specialDeductibleLabel}</span>
              <span className="font-mono text-xs font-bold text-[#60a5fa]">
                {formatCurrency(policy.specialDeductibleAmount)}
              </span>
            </div>
          </div>
        )}
      </Section>

      {/* Endorsements */}
      <Section label="Endorsements">
        {policy.endorsements.map((e) => (
          <div key={e.code} className="flex items-center justify-between py-1">
            <div className="min-w-0">
              <p className="text-xs text-[#93a3b8]">{e.label}</p>
              <p className="font-mono text-[9px] text-[#3f4f63]">{e.code}</p>
            </div>
            {e.limit && (
              <span className="ml-2 shrink-0 text-[10px] text-[#6b7a8d]">{e.limit}</span>
            )}
          </div>
        ))}
      </Section>

      {policy.floodNote && (
        <Section label="Flood">
          <p className="text-xs text-[#93a3b8]">{policy.floodNote}</p>
        </Section>
      )}

      <Section label="Prior Claims">
        <p className="text-sm font-mono font-semibold text-[#d9e1ec]">
          {policy.priorClaimsCount}
          <span className="ml-1 text-xs font-normal text-[#6b7a8d]">on record</span>
        </p>
      </Section>

      <div className="px-4 py-3">
        <p className="text-[10px] text-[#3f4f63]">{policy.insurer}</p>
      </div>
    </aside>
  );
}
