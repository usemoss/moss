'use client';

import { cn, formatCurrency } from '@/lib/utils';
import type { ClaimState, DamageItem, CoverageStatus } from '@/hooks/useClaimState';

const STATUS_STYLE: Record<CoverageStatus, { dot: string; text: string; label: string }> = {
  covered:     { dot: 'bg-[#16a34a]', text: 'text-[#86efac]', label: 'Covered' },
  not_covered: { dot: 'bg-[#dc2626]', text: 'text-[#fca5a5]', label: 'Not Covered' },
};

function DamageRow({ item }: { item: DamageItem }) {
  const s = STATUS_STYLE[item.status];
  return (
    <div className="border-b border-[#1c2438] py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-[#d9e1ec] leading-snug">{item.description}</p>
          {item.note && (
            <p className="mt-0.5 text-[10px] text-[#3f4f63] line-clamp-1">{item.note}</p>
          )}
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-sm font-semibold text-[#d9e1ec]">
            {formatCurrency(item.estimatedValue)}
          </p>
          <span className={cn('flex items-center justify-end gap-1 mt-0.5 text-[10px] font-semibold', s.text)}>
            <span className={cn('h-1.5 w-1.5 rounded-full', s.dot)} />
            {s.label}
          </span>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[#3f4f63]">{label}</p>
      <p className={cn('font-mono text-base font-bold', color)}>{value}</p>
    </div>
  );
}

export function DamageWorksheet({ claimState }: { claimState: ClaimState }) {
  const { damageItems, totalCovered, totalNotCovered, reportSubmitted } = claimState;
  const grandTotal = totalCovered + totalNotCovered;
  const coveredCount = damageItems.filter((i) => i.status === 'covered').length;
  const notCoveredCount = damageItems.filter((i) => i.status === 'not_covered').length;

  return (
    <aside className="flex h-full flex-col overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#263044] px-4 py-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-[#3f4f63]">
          Damage Worksheet
        </span>
        {reportSubmitted && (
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[#16a34a]">
            Submitted
          </span>
        )}
      </div>

      {/* Totals */}
      <div className="grid grid-cols-3 gap-px bg-[#263044] border-b border-[#263044]">
        <div className="bg-[#161c28] px-3 py-3">
          <Stat
            label={`Covered (${coveredCount})`}
            value={formatCurrency(totalCovered)}
            color="text-[#86efac]"
          />
        </div>
        <div className="bg-[#161c28] px-3 py-3">
          <Stat
            label={`Not covered (${notCoveredCount})`}
            value={formatCurrency(totalNotCovered)}
            color="text-[#fca5a5]"
          />
        </div>
        <div className="bg-[#161c28] px-3 py-3">
          <Stat
            label="Total"
            value={formatCurrency(grandTotal)}
            color="text-[#d9e1ec]"
          />
        </div>
      </div>

      {/* Coverage bar */}
      {grandTotal > 0 && (
        <div className="h-1 w-full bg-[#1c2438]">
          <div
            className="h-full bg-[#16a34a] transition-all duration-500"
            style={{ width: `${(totalCovered / grandTotal) * 100}%` }}
          />
        </div>
      )}

      {/* Items */}
      <div className="flex-1 px-4">
        {damageItems.length === 0 ? (
          <div className="flex h-full items-center justify-center py-12">
            <p className="text-center text-xs text-[#3f4f63]">
              Findings appear here as you dictate them
            </p>
          </div>
        ) : (
          damageItems.map((item) => <DamageRow key={item.index} item={item} />)
        )}
      </div>
    </aside>
  );
}
