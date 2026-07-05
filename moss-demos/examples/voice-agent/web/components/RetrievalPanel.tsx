"use client";

import { useCallback, useState } from "react";
import { useDataChannel } from "@livekit/components-react";
import type { RetrievalPayload } from "@/lib/types";

// Listens on the "moss.retrieval" data channel and shows the chunks Moss returned
// for the latest turn — the star of the demo.
export function RetrievalPanel() {
  const [data, setData] = useState<RetrievalPayload | null>(null);

  useDataChannel(
    "moss.retrieval",
    useCallback((msg: { payload: Uint8Array }) => {
      try {
        const parsed = JSON.parse(new TextDecoder().decode(msg.payload)) as RetrievalPayload;
        setData(parsed);
      } catch (err) {
        console.error("failed to parse moss.retrieval payload", err);
      }
    }, []),
  );

  return (
    <div className="card">
      <div className="retrieval-head">
        <span className="diamond" />
        Moss · knowledge base
      </div>

      {data ? (
        <>
          <div className="retrieval-query">
            <span className="label">query</span>
            {data.query}
          </div>
          <div className="chunks">
            {data.docs.map((doc, i) => {
              const pct = Math.max(0, Math.min(1, doc.score)) * 100;
              return (
                <div className="chunk" key={doc.id ?? i}>
                  <div className="top">
                    <div className="bar">
                      <span style={{ width: `${pct}%` }} />
                    </div>
                    <span className="score">{doc.score.toFixed(2)}</span>
                  </div>
                  <div className="text">{doc.text}</div>
                </div>
              );
            })}
          </div>
          <div className="retrieval-foot">
            <span className="ms">{data.took_ms.toFixed(1)}ms</span>
            <span>·</span>
            <span>
              {data.docs.length} result{data.docs.length === 1 ? "" : "s"} · on-device
            </span>
          </div>
        </>
      ) : (
        <div className="retrieval-empty">
          Ask the agent a question. The knowledge-base chunks Moss retrieves will appear here, live.
        </div>
      )}
    </div>
  );
}
