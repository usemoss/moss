'use client';

import { useEffect, useMemo, useState } from 'react';
import { useChat } from '@livekit/components-react';

export type CoverageStatus = 'covered' | 'not_covered' | 'pending';

export type DamageItem = {
  index: number;
  category: string;
  description: string;
  estimatedValue: number;
  status: CoverageStatus;
  coverageNote: string;
};

export type ClaimState = {
  adjusterVerified: boolean;
  adjusterID: string | null;
  policyLoaded: string | null;
  policyLoadedMs: number | null;
  damageItems: DamageItem[];
  fieldNotes: string[];
  totalCovered: number;
  totalNotCovered: number;
  totalPending: number;
  escalations: string[];
  reportSubmitted: boolean;
};

const EMPTY_STATE: ClaimState = {
  adjusterVerified: false,
  adjusterID: null,
  policyLoaded: null,
  policyLoadedMs: null,
  damageItems: [],
  fieldNotes: [],
  totalCovered: 0,
  totalNotCovered: 0,
  totalPending: 0,
  escalations: [],
  reportSubmitted: false,
};

function recomputeTotals(items: DamageItem[]) {
  let covered = 0, notCovered = 0, pending = 0;
  for (const item of items) {
    if (item.status === 'covered') covered += item.estimatedValue;
    else if (item.status === 'not_covered') notCovered += item.estimatedValue;
    else pending += item.estimatedValue;
  }
  return { totalCovered: covered, totalNotCovered: notCovered, totalPending: pending };
}

export function useClaimState(): ClaimState {
  const { chatMessages } = useChat();
  const [state, setState] = useState<ClaimState>(EMPTY_STATE);

  useEffect(() => {
    // Only process agent messages
    const agentMessages = chatMessages.filter((m) => m.from?.isAgent);

    setState(() => {
      const next: ClaimState = { ...EMPTY_STATE, damageItems: [] };

      for (const msg of agentMessages) {
        const text = typeof msg.message === 'string' ? msg.message : '';

        // Adjuster verified: "Adjuster A-4412 verified."
        const verifiedMatch = text.match(/Adjuster\s+(A-\d{4})\s+verified/i);
        if (verifiedMatch) {
          next.adjusterVerified = true;
          next.adjusterID = verifiedMatch[1];
        }

        // Policy loaded: "Policy FL-HO3-001 loaded in 12ms."
        const policyMatch = text.match(/Policy\s+([\w\-]+)\s+loaded\s+in\s+(\d+)ms/i);
        if (policyMatch) {
          next.policyLoaded = policyMatch[1].toUpperCase();
          next.policyLoadedMs = parseInt(policyMatch[2], 10);
        }

        // Damage item: "Damage item #3 recorded: roofing, $12,500."
        const damageMatch = text.match(/Damage item\s+#(\d+)\s+recorded:\s+([\w_\s]+),\s+\$([\d,]+)/i);
        if (damageMatch) {
          const idx = parseInt(damageMatch[1], 10);
          const category = damageMatch[2].trim();
          const valueStr = damageMatch[3].replace(/,/g, '');
          const value = parseFloat(valueStr);
          // Ensure slot exists
          while (next.damageItems.length < idx) {
            next.damageItems.push({
              index: next.damageItems.length + 1,
              category: '',
              description: '',
              estimatedValue: 0,
              status: 'pending',
              coverageNote: '',
            });
          }
          next.damageItems[idx - 1] = {
            ...next.damageItems[idx - 1],
            index: idx,
            category,
            estimatedValue: value,
            description: category,
            status: 'pending',
          };
        }

        // Coverage determination: "Item #3 marked COVERED. Reason recorded."
        const coveredMatch = text.match(/Item\s+#(\d+)\s+marked\s+(COVERED|NOT COVERED)\./i);
        if (coveredMatch) {
          const idx = parseInt(coveredMatch[1], 10);
          const status: CoverageStatus = coveredMatch[2].trim().toUpperCase() === 'COVERED' ? 'covered' : 'not_covered';
          if (idx >= 1 && idx <= next.damageItems.length) {
            next.damageItems[idx - 1] = { ...next.damageItems[idx - 1], status };
          }
        }

        // Field note: "Field note added."
        if (/Field note added/i.test(text)) {
          next.fieldNotes.push('Note recorded');
        }

        // Escalation
        const escalationMatch = text.match(/Escalation to\s+([\w_\s]+)\s+flagged/i);
        if (escalationMatch) {
          next.escalations.push(escalationMatch[1].trim());
        }

        // Report submitted
        if (/Report saved/i.test(text)) {
          next.reportSubmitted = true;
        }
      }

      return { ...next, ...recomputeTotals(next.damageItems) };
    });
  }, [chatMessages]);

  return useMemo(() => state, [state]);
}
