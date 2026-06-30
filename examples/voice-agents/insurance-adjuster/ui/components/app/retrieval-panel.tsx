'use client';

import { cn } from '@/lib/utils';
import type { MossInsuranceEvent } from '@/hooks/useMossInsuranceEvents';

const SOURCE_STYLE = {
  policy:      { badge: 'text-[#60a5fa]' },
  'claims-kb': { badge: 'text-[#4b5a6d]' },
  unknown:     { badge: 'text-[#4ade80]' },
} as const;

const SOURCE_LABEL: Record<MossInsuranceEvent['source'], string> = {
  policy: 'Policy',
  'claims-kb': 'KB',
  unknown: 'Session',
};

function EventCard({ event }: { event: MossInsuranceEvent }) {
  const s = SOURCE_STYLE[event.source];
  const topMatch = event.matches[0]?.text.slice(0, 160) ?? '';

  return (
    <div className="border-b border-[#1c2438] px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className={cn('text-[9px] font-bold uppercase tracking-widest', s.badge)}>
          {SOURCE_LABEL[event.source]}
        </span>
        {event.timeTakenMs != null && (
          <span className="font-mono text-[10px] text-[#16a34a]">
            {event.timeTakenMs.toFixed(0)}ms
          </span>
        )}
      </div>
      <p className="mt-1 text-[11px] text-[#6b7a8d] line-clamp-1">{event.query}</p>
      {topMatch && (
        <p className="mt-1.5 text-[10px] leading-relaxed text-[#3f4f63] line-clamp-2">
          {topMatch}
        </p>
      )}
    </div>
  );
}

export function RetrievalPanel({ events }: { events: MossInsuranceEvent[] }) {
  const displayed = [...events].reverse();

  return (
    <aside className="flex h-full flex-col border-l border-[#1c2438] overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#1c2438] px-4 py-2.5 shrink-0">
        <span className="text-[9px] font-bold uppercase tracking-widest text-[#263044]">
          Moss Retrieval
        </span>
        {events.length > 0 && (
          <span className="font-mono text-[9px] text-[#263044]">{events.length}</span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <div className="flex h-8 w-8 items-center justify-center border border-[#1c2438]">
              <svg className="h-3.5 w-3.5 text-[#1c2438]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803 7.5 7.5 0 0016.803 15.803z" />
              </svg>
            </div>
            <p className="text-[10px] text-[#263044]">
              Retrieval events appear here as the agent queries knowledge
            </p>
          </div>
        ) : (
          displayed.map((e) => <EventCard key={e.id} event={e} />)
        )}
      </div>
    </aside>
  );
}
