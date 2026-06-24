'use client';

import { cn, formatCurrency } from '@/lib/utils';
import type { ClaimState, DamageItem, CoverageStatus } from '@/hooks/useClaimState';

const CATEGORY_ICONS: Record<string, string> = {
  structural: '🏗',
  roofing: '🏠',
  exterior: '🪟',
  interior: '🛋',
  mechanical_electrical: '⚡',
  contents: '📦',
  additional_living_expenses: '🏨',
  default: '📋',
};

const STATUS_STYLES: Record<CoverageStatus, { badge: string; row: string }> = {
  covered: {
    badge: 'bg-emerald-950/60 text-emerald-400 border border-emerald-800',
    row: 'border-l-2 border-l-emerald-600',
  },
  not_covered: {
    badge: 'bg-rose-950/60 text-rose-400 border border-rose-900',
    row: 'border-l-2 border-l-rose-700',
  },
  pending: {
    badge: 'bg-amber-950/50 text-amber-400 border border-amber-900',
    row: 'border-l-2 border-l-amber-700',
  },
};

const STATUS_LABELS: Record<CoverageStatus, string> = {
  covered: 'Covered',
  not_covered: 'Not Covered',
  pending: 'Pending',
};

function DamageRow({ item }: { item: DamageItem }) {
  const styles = STATUS_STYLES[item.status];
  const icon = CATEGORY_ICONS[item.category] ?? CATEGORY_ICONS.default;

  return (
    <div className={cn('rounded-lg border border-[#27272a] bg-[#18181b] p-3', styles.row)}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0">
          <span className="mt-0.5 text-base leading-none">{icon}</span>
          <div className="min-w-0">
            <p className="text-xs font-semibold capitalize text-zinc-200">
              #{item.index} · {item.category.replace(/_/g, ' ')}
            </p>
            {item.description && item.description !== item.category && (
              <p className="mt-0.5 truncate text-xs text-zinc-500">{item.description}</p>
            )}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-sm font-semibold text-zinc-100">
            {formatCurrency(item.estimatedValue)}
          </p>
          <span className={cn('mt-0.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold', styles.badge)}>
            {STATUS_LABELS[item.status]}
          </span>
        </div>
      </div>
    </div>
  );
}

function TotalBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: 'green' | 'red' | 'amber';
}) {
  const colorMap = {
    green: 'text-emerald-400',
    red: 'text-rose-400',
    amber: 'text-amber-400',
  };
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={cn('font-mono text-sm font-bold', colorMap[color])}>
        {formatCurrency(value)}
      </span>
    </div>
  );
}

export function DamageWorksheet({ claimState }: { claimState: ClaimState }) {
  const { damageItems, fieldNotes, totalCovered, totalNotCovered, totalPending, escalations, reportSubmitted } =
    claimState;

  const grandTotal = totalCovered + totalNotCovered + totalPending;
  const hasItems = damageItems.length > 0;

  return (
    <aside className="flex h-full flex-col overflow-y-auto p-4">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
          Damage Worksheet
        </p>
        {reportSubmitted && (
          <span className="rounded bg-emerald-950/60 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-800">
            Report Submitted
          </span>
        )}
      </div>

      {/* Summary totals */}
      <div className="mb-4 rounded-xl border border-[#27272a] bg-[#18181b] p-4">
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
          Claim Estimate
        </p>
        <TotalBar label="Covered" value={totalCovered} color="green" />
        <TotalBar label="Not Covered" value={totalNotCovered} color="red" />
        <TotalBar label="Pending" value={totalPending} color="amber" />
        <div className="my-2 border-t border-[#27272a]" />
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-semibold text-zinc-300">Total Documented</span>
          <span className="font-mono text-base font-bold text-zinc-100">{formatCurrency(grandTotal)}</span>
        </div>

        {/* Coverage bar visualization */}
        {grandTotal > 0 && (
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[#27272a]">
            <div className="flex h-full">
              {totalCovered > 0 && (
                <div
                  className="bg-emerald-500 transition-all duration-500"
                  style={{ width: `${(totalCovered / grandTotal) * 100}%` }}
                />
              )}
              {totalNotCovered > 0 && (
                <div
                  className="bg-rose-600 transition-all duration-500"
                  style={{ width: `${(totalNotCovered / grandTotal) * 100}%` }}
                />
              )}
              {totalPending > 0 && (
                <div
                  className="bg-amber-500 transition-all duration-500"
                  style={{ width: `${(totalPending / grandTotal) * 100}%` }}
                />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Damage items */}
      <div className="mb-4 flex-1">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
          Items ({damageItems.length})
        </p>
        {!hasItems ? (
          <div className="rounded-lg border border-dashed border-[#3f3f46] p-6 text-center">
            <p className="text-xs text-zinc-600">
              Damage items appear here as you<br />describe them to the agent
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {damageItems.map((item) => (
              <DamageRow key={item.index} item={item} />
            ))}
          </div>
        )}
      </div>

      {/* Escalations */}
      {escalations.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
            Escalations
          </p>
          <div className="space-y-1.5">
            {escalations.map((e, i) => (
              <div key={i} className="flex items-center gap-2 rounded-md border border-yellow-900/50 bg-yellow-950/30 px-3 py-2">
                <span className="text-xs">⚠️</span>
                <span className="text-xs capitalize text-yellow-300">{e.replace(/_/g, ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Field notes */}
      {fieldNotes.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
            Field Notes ({fieldNotes.length})
          </p>
          <div className="space-y-1">
            {fieldNotes.map((note, i) => (
              <div key={i} className="rounded-md bg-[#18181b] px-3 py-2 text-xs text-zinc-400">
                {note}
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
