'use client';

import { cn, formatCurrency } from '@/lib/utils';
import { POLICIES, type PolicyData } from '@/lib/policies';

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
      {children}
    </p>
  );
}

function CoverageLine({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between py-1.5">
      <span className={cn('text-xs', highlight ? 'font-semibold text-zinc-200' : 'text-zinc-400')}>
        {label}
      </span>
      <div className="text-right">
        <span className={cn('text-xs font-mono', highlight ? 'text-amber-400 font-semibold' : 'text-zinc-300')}>
          {value}
        </span>
        {sub && <span className="ml-1 text-[10px] text-zinc-600">{sub}</span>}
      </div>
    </div>
  );
}

function Divider() {
  return <div className="my-3 border-t border-[#27272a]" />;
}

export function PolicyPanel({ policyNumber }: { policyNumber: string | null }) {
  const policy: PolicyData | null = policyNumber ? POLICIES[policyNumber] ?? null : null;

  if (!policy) {
    return (
      <aside className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-[#3f3f46] bg-[#18181b]">
          <svg className="h-5 w-5 text-zinc-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <p className="text-xs text-zinc-500">Ask the agent for<br />the policy number</p>
      </aside>
    );
  }

  const stateColorMap: Record<string, string> = {
    FL: 'text-blue-400 bg-blue-950/60 border-blue-800',
    CA: 'text-orange-400 bg-orange-950/60 border-orange-800',
    TX: 'text-red-400 bg-red-950/60 border-red-800',
  };
  const stateColor = stateColorMap[policy.stateCode] ?? 'text-zinc-300 bg-zinc-800 border-zinc-700';

  return (
    <aside className="flex h-full flex-col overflow-y-auto p-4">
      {/* Policy header */}
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <span className="font-mono text-base font-bold text-amber-400">{policy.policyNumber}</span>
          <p className="mt-0.5 text-xs text-zinc-500">{policy.policyType}</p>
        </div>
        <span className={cn('rounded border px-2 py-0.5 text-xs font-bold tracking-wide', stateColor)}>
          {policy.stateCode}
        </span>
      </div>

      {/* Property */}
      <div className="mb-4 rounded-lg border border-[#27272a] bg-[#18181b] p-3">
        <SectionLabel>Property</SectionLabel>
        <p className="text-sm font-medium text-zinc-200">{policy.address}</p>
        <p className="text-xs text-zinc-400">{policy.city}</p>
        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <span className="text-zinc-500">Built <span className="text-zinc-300">{policy.yearBuilt}</span></span>
          <span className="text-zinc-500">Roof <span className="text-zinc-300">{policy.roofYear}</span></span>
          <span className="text-zinc-500 col-span-2">{policy.sqft.toLocaleString()} sqft · {policy.construction}</span>
        </div>
      </div>

      {/* Coverage limits */}
      <div className="mb-4 rounded-lg border border-[#27272a] bg-[#18181b] p-3">
        <SectionLabel>Coverage Limits</SectionLabel>
        <CoverageLine label="A — Dwelling" value={formatCurrency(policy.coverageA)} highlight />
        <CoverageLine label="B — Other Structures" value={formatCurrency(policy.coverageB)} sub="10%" />
        <CoverageLine
          label="C — Personal Property"
          value={formatCurrency(policy.coverageCLimit)}
          sub={policy.coverageC}
        />
        <CoverageLine label="D — Loss of Use" value={formatCurrency(policy.coverageD)} />
        <CoverageLine label="E — Liability" value={formatCurrency(policy.coverageE)} />
        <CoverageLine label="F — Medical Pmts" value={formatCurrency(policy.coverageF)} />
      </div>

      {/* Deductibles */}
      <div className="mb-4 rounded-lg border border-[#27272a] bg-[#18181b] p-3">
        <SectionLabel>Deductibles</SectionLabel>
        <CoverageLine label="All-Peril" value={formatCurrency(policy.standardDeductible)} />
        {policy.specialDeductibleLabel && policy.specialDeductibleAmount != null && (
          <div className="mt-1 rounded-md bg-amber-950/40 px-2.5 py-2">
            <div className="flex items-baseline justify-between">
              <span className="text-xs font-semibold text-amber-300">{policy.specialDeductibleLabel}</span>
              <span className="font-mono text-xs font-bold text-amber-400">
                {formatCurrency(policy.specialDeductibleAmount)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Endorsements */}
      <div className="mb-4 rounded-lg border border-[#27272a] bg-[#18181b] p-3">
        <SectionLabel>Endorsements</SectionLabel>
        <div className="space-y-2">
          {policy.endorsements.map((e) => (
            <div key={e.code} className="flex items-start justify-between gap-2">
              <div>
                <p className="text-xs font-medium text-zinc-200">{e.label}</p>
                <p className="text-[10px] font-mono text-zinc-600">{e.code}</p>
              </div>
              {e.limit && (
                <span className="shrink-0 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
                  {e.limit}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Flood note */}
      {policy.floodNote && (
        <div className="mb-4 rounded-lg border border-blue-900/50 bg-blue-950/30 p-3">
          <SectionLabel>Flood</SectionLabel>
          <p className="text-xs text-blue-300">{policy.floodNote}</p>
        </div>
      )}

      {/* Prior claims */}
      <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-3">
        <SectionLabel>Prior Claims</SectionLabel>
        <p className="text-sm font-semibold text-zinc-200">
          {policy.priorClaimsCount}
          <span className="ml-1 text-xs font-normal text-zinc-500">on record</span>
        </p>
      </div>

      <Divider />
      <p className="text-center text-[10px] text-zinc-600">
        {policy.insurer}
      </p>
    </aside>
  );
}
