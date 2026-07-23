"use client";

import { PipecatClient } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { useCallback, useEffect, useRef, useState } from "react";

type SessionState = "idle" | "connecting" | "active";

type InterviewTrack = {
  id: string;
  label: string;
  blurb: string;
};

type GradeFeedback = {
  topic: string | null;
  score: number;
  maxScore: number;
  summary: string;
  tips: string[];
};

type AssistPanelState = {
  currentQuestion: string | null;
  userAnswer: string | null;
  grading: boolean;
  gradingTurnId: number | null;
  feedback: GradeFeedback | null;
};

type HealthBody = {
  ok?: boolean;
  moss_ready?: boolean;
  grader_worker?: boolean;
  ollama_error?: string | null;
  moss_indexes?: Record<string, { index_name?: string; ready?: boolean }>;
};

const EMPTY_ASSIST: AssistPanelState = {
  currentQuestion: null,
  userAnswer: null,
  grading: false,
  gradingTurnId: null,
  feedback: null,
};

const INTERVIEW_TRACKS: InterviewTrack[] = [
  {
    id: "system-design",
    label: "System Design",
    blurb: "Distributed systems, APIs, scale, and reliability.",
  },
  {
    id: "agent-native-infrastructure",
    label: "Agent-Native Infrastructure",
    blurb: "Agent runtimes, tools, memory, orchestration, and evals.",
  },
  {
    id: "machine-learning-concepts",
    label: "Machine Learning Concepts",
    blurb: "ML fundamentals, evaluation, training, and model systems.",
  },
];

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const CONNECT_TIMEOUT_MS = 30_000;

function parseDataPayload(data: unknown): Record<string, unknown> | null {
  try {
    if (typeof data === "string") {
      return JSON.parse(data) as Record<string, unknown>;
    }
    if (data instanceof ArrayBuffer) {
      return JSON.parse(new TextDecoder().decode(data)) as Record<string, unknown>;
    }
    if (data instanceof Uint8Array) {
      return JSON.parse(new TextDecoder().decode(data)) as Record<string, unknown>;
    }
    if (data && typeof data === "object") {
      return data as Record<string, unknown>;
    }
  } catch {
    return null;
  }
  return null;
}

function extractQuestionFromBotText(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return cleaned;
  const parts = cleaned.split(/(?<=[.?!])\s+/);
  const questions = parts.filter((p) => p.includes("?"));
  return (questions.at(-1) ?? parts.at(-1) ?? cleaned).trim();
}

function mapApiTracks(
  apiTracks: Array<{ id: string; label: string }>,
): InterviewTrack[] {
  return apiTracks.map((track) => ({
    id: track.id,
    label: track.label,
    blurb: INTERVIEW_TRACKS.find((t) => t.id === track.id)?.blurb ?? "",
  }));
}

export default function HomePage() {
  const [session, setSession] = useState<SessionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [interruptFlash, setInterruptFlash] = useState(false);
  const [interruptCount, setInterruptCount] = useState(0);
  const [aiTalking, setAiTalking] = useState(false);
  const [userTalking, setUserTalking] = useState(false);
  const [localLevel, setLocalLevel] = useState(0);
  const [remoteLevel, setRemoteLevel] = useState(0);
  const [assist, setAssist] = useState<AssistPanelState>(EMPTY_ASSIST);
  const [tracks, setTracks] = useState<InterviewTrack[]>(INTERVIEW_TRACKS);
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);
  const [activeTrackLabel, setActiveTrackLabel] = useState<string | null>(null);

  const clientRef = useRef<PipecatClient | null>(null);
  const botAudioRef = useRef<HTMLAudioElement | null>(null);
  const botTranscriptBuf = useRef("");
  const connectAbortRef = useRef<AbortController | null>(null);
  const userCancelledRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/tracks`);
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as { tracks?: Array<{ id: string; label: string }> };
        if (!Array.isArray(data.tracks) || data.tracks.length === 0 || cancelled) return;
        setTracks(mapApiTracks(data.tracks));
      } catch {
        // Keep hardcoded INTERVIEW_TRACKS fallback.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleServerMessage = useCallback((raw: unknown) => {
    const msg = parseDataPayload(raw);
    if (!msg) return;

    if (msg.type === "interview_track" && typeof msg.label === "string") {
      setActiveTrackLabel(msg.label);
      return;
    }

    if (msg.type === "interruption" && msg.interrupted) {
      setInterruptCount((c) => c + 1);
      setInterruptFlash(true);
      // Drop the current turn so a late grade_result for it cannot land.
      setAssist((prev) => ({ ...prev, grading: false, gradingTurnId: null }));
      window.setTimeout(() => setInterruptFlash(false), 900);
      return;
    }

    if (msg.type === "current_question" && typeof msg.text === "string") {
      const next = msg.text.trim();
      if (!next) return;
      setAssist((prev) =>
        prev.currentQuestion === next ? prev : { ...prev, currentQuestion: next },
      );
      return;
    }

    if (msg.type === "user_answer" && typeof msg.text === "string") {
      const turnId = typeof msg.turn_id === "number" ? msg.turn_id : null;
      const answer = msg.text.trim();
      setAssist((prev) => ({
        ...prev,
        userAnswer: answer,
        grading: true,
        gradingTurnId: turnId ?? prev.gradingTurnId,
        feedback: null,
      }));
      return;
    }

    if (msg.type === "grading_started") {
      const turnId = typeof msg.turn_id === "number" ? msg.turn_id : null;
      setAssist((prev) => ({
        ...prev,
        grading: true,
        gradingTurnId: turnId ?? prev.gradingTurnId,
      }));
      return;
    }

    if (msg.type === "grade_result") {
      const turnId = typeof msg.turn_id === "number" ? msg.turn_id : null;
      const tips = Array.isArray(msg.tips)
        ? msg.tips.filter((t): t is string => typeof t === "string")
        : [];
      setAssist((prev) => {
        // Prefer turn-scoped grades: ignore stale or post-interrupt results.
        if (turnId !== null && turnId !== prev.gradingTurnId) {
          return prev;
        }
        return {
          ...prev,
          grading: false,
          feedback: {
            topic: typeof msg.topic === "string" ? msg.topic : null,
            score: typeof msg.score === "number" ? msg.score : 3,
            maxScore: typeof msg.max_score === "number" ? msg.max_score : 5,
            summary:
              typeof msg.summary === "string"
                ? msg.summary
                : "Review the rubric points for this topic.",
            tips,
          },
        };
      });
      return;
    }
  }, []);

  const attachBotAudio = useCallback((track: MediaStreamTrack) => {
    // SmallWebRTCTransport defaults DailyMediaManager(enablePlayer=false), so
    // remote WebRTC audio must be wired to an <audio> element manually.
    const el = botAudioRef.current;
    if (!el) return;
    el.srcObject = new MediaStream([track]);
    el.muted = false;
    el.volume = 1;
    void el.play().catch((err: unknown) => {
      console.warn("Bot audio autoplay blocked:", err);
    });
  }, []);

  const resetTalkState = useCallback(() => {
    setAiTalking(false);
    setUserTalking(false);
    setLocalLevel(0);
    setRemoteLevel(0);
  }, []);

  const endInterview = useCallback(async () => {
    const client = clientRef.current;
    clientRef.current = null;
    setSession("idle");
    resetTalkState();
    setAssist(EMPTY_ASSIST);
    setActiveTrackLabel(null);
    botTranscriptBuf.current = "";
    if (botAudioRef.current) {
      botAudioRef.current.pause();
      botAudioRef.current.srcObject = null;
    }
    if (client) {
      try {
        await client.disconnect();
      } catch {
        // Best-effort disconnect
      }
    }
  }, [resetTalkState]);

  const cancelConnecting = useCallback(async () => {
    userCancelledRef.current = true;
    connectAbortRef.current?.abort();
    const client = clientRef.current;
    clientRef.current = null;
    setSession("idle");
    resetTalkState();
    setActiveTrackLabel(null);
    botTranscriptBuf.current = "";
    if (botAudioRef.current) {
      botAudioRef.current.pause();
      botAudioRef.current.srcObject = null;
    }
    if (client) {
      try {
        await client.disconnect();
      } catch {
        // Best-effort disconnect
      }
    }
  }, [resetTalkState]);

  const startInterview = useCallback(
    async (trackId: string) => {
      setError(null);
      userCancelledRef.current = false;
      setSession("connecting");
      setInterruptCount(0);
      resetTalkState();
      setAssist(EMPTY_ASSIST);
      setActiveTrackLabel(tracks.find((t) => t.id === trackId)?.label ?? trackId);
      botTranscriptBuf.current = "";

      const abort = new AbortController();
      connectAbortRef.current = abort;
      const timeoutId = window.setTimeout(() => {
        abort.abort(new DOMException("Connection timed out", "AbortError"));
      }, CONNECT_TIMEOUT_MS);

      let client: PipecatClient | null = null;

      try {
        const health = await fetch(`${BACKEND_URL}/health`, { signal: abort.signal });
        if (!health.ok) {
          throw new Error(`Backend health check failed (${health.status})`);
        }
        const body = (await health.json()) as HealthBody;
        if (body.ok === false) {
          const ollamaHint = body.ollama_error ? ` Ollama: ${body.ollama_error}` : "";
          throw new Error(`Backend is not ready.${ollamaHint}`);
        }
        if (body.moss_ready === false) {
          throw new Error(
            "Moss indexes not loaded. Run ingest_knowledge.py and restart the backend.",
          );
        }
        const trackIndex = body.moss_indexes?.[trackId];
        if (trackIndex && trackIndex.ready === false) {
          const name = trackIndex.index_name ?? trackId;
          throw new Error(
            `Moss index "${name}" is not loaded for this track. Run ingest_knowledge.py --recreate and restart the backend.`,
          );
        }
        if (body.grader_worker === false) {
          throw new Error(
            "Grader worker is missing on the backend (grader_worker.py).",
          );
        }

        if (abort.signal.aborted) return;

        client = new PipecatClient({
          transport: new SmallWebRTCTransport({
            iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
            waitForICEGathering: true,
          }),
          enableCam: false,
          enableMic: true,
          callbacks: {
            onConnected: () => {
              if (clientRef.current !== client) return;
              setSession("active");
            },
            onBotReady: () => {
              if (clientRef.current !== client) return;
              setSession("active");
            },
            onDisconnected: () => {
              if (clientRef.current !== client) return;
              clientRef.current = null;
              setSession("idle");
              resetTalkState();
              setAssist(EMPTY_ASSIST);
              setActiveTrackLabel(null);
              botTranscriptBuf.current = "";
              if (botAudioRef.current) {
                botAudioRef.current.pause();
                botAudioRef.current.srcObject = null;
              }
            },
            onBotStartedSpeaking: () => {
              if (clientRef.current !== client) return;
              setAiTalking(true);
              botTranscriptBuf.current = "";
            },
            onBotStoppedSpeaking: () => {
              if (clientRef.current !== client) return;
              setAiTalking(false);
              // Fallback only when server hasn't delivered a question yet — never
              // overwrite a settled server question (prevents sidebar thrash).
              const question = extractQuestionFromBotText(botTranscriptBuf.current);
              if (question && question.includes("?") && question.length >= 12) {
                setAssist((prev) =>
                  prev.currentQuestion ? prev : { ...prev, currentQuestion: question },
                );
              }
            },
            onUserStartedSpeaking: () => {
              if (clientRef.current !== client) return;
              setUserTalking(true);
            },
            onUserStoppedSpeaking: () => {
              if (clientRef.current !== client) return;
              setUserTalking(false);
            },
            onLocalAudioLevel: (level: number) => {
              if (clientRef.current !== client) return;
              setLocalLevel(level);
            },
            onRemoteAudioLevel: (level: number) => {
              if (clientRef.current !== client) return;
              setRemoteLevel(level);
            },
            onUserTranscript: (data) => {
              if (clientRef.current !== client) return;
              // Server tool events own the Assist answer snippet; transcript is
              // only a quiet fallback so Whisper partials don't flicker the panel.
              if (!data.final || !data.text.trim()) return;
              const snippet = data.text.trim();
              setAssist((prev) => {
                if (prev.grading) return prev;
                return { ...prev, userAnswer: snippet };
              });
            },
            onBotTranscript: (data) => {
              if (clientRef.current !== client) return;
              if (!data.text) return;
              botTranscriptBuf.current += data.text;
            },
            onBotLlmText: (data) => {
              if (clientRef.current !== client) return;
              if (!data.text) return;
              botTranscriptBuf.current += data.text;
            },
            onTrackStarted: (track, participant) => {
              if (clientRef.current !== client) return;
              if (track.kind !== "audio") return;
              // Local mic should not be played back into speakers.
              if (participant?.local) return;
              attachBotAudio(track);
            },
            onServerMessage: (data: unknown) => handleServerMessage(data),
            onError: (message) => {
              if (clientRef.current !== client) return;
              const detail =
                typeof message === "object" && message && "data" in message
                  ? JSON.stringify((message as { data?: unknown }).data)
                  : "WebRTC connection error";
              void (async () => {
                await endInterview();
                setError(detail);
              })();
            },
          },
        });

        clientRef.current = client;
        await client.initDevices();
        if (abort.signal.aborted) {
          await client.disconnect();
          return;
        }
        await client.connect({
          webrtcUrl: `${BACKEND_URL}/api/offer?topic=${encodeURIComponent(trackId)}`,
        });
        if (abort.signal.aborted) {
          await client.disconnect();
          return;
        }
        setSession("active");

        // In case the remote track arrived before the callback was wired.
        const remote = client.tracks()?.bot?.audio;
        if (remote) attachBotAudio(remote);
      } catch (err) {
        if (abort.signal.aborted) {
          if (client) {
            clientRef.current = null;
            try {
              await client.disconnect();
            } catch {
              // Best-effort disconnect
            }
          }
          setSession("idle");
          setActiveTrackLabel(null);
          resetTalkState();
          if (!userCancelledRef.current) {
            setError(
              err instanceof Error && err.message.includes("timed out")
                ? "Connection timed out. Check that the backend and Ollama are running."
                : "Unable to connect to the interview backend.",
            );
          }
          return;
        }
        clientRef.current = null;
        if (client) {
          try {
            await client.disconnect();
          } catch {
            // Best-effort disconnect
          }
        }
        setSession("idle");
        setActiveTrackLabel(null);
        resetTalkState();
        setError(err instanceof Error ? err.message : "Unable to start interview");
      } finally {
        window.clearTimeout(timeoutId);
        connectAbortRef.current = null;
      }
    },
    [attachBotAudio, endInterview, handleServerMessage, resetTalkState, tracks],
  );

  useEffect(() => {
    return () => {
      void clientRef.current?.disconnect();
    };
  }, []);

  const activeLevel = Math.max(localLevel, remoteLevel);
  const ringAi = aiTalking || remoteLevel > 0.08;
  const ringUser = userTalking || localLevel > 0.08;

  return (
    <main className="relative min-h-screen overflow-hidden px-6 py-10 md:px-12 md:py-14">
      {/* Bot audio: SmallWebRTC does not autoplay remote tracks by default */}
      <audio ref={botAudioRef} autoPlay playsInline className="hidden" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(232,240,236,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(232,240,236,0.5) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse at center, black 20%, transparent 75%)",
        }}
      />

      {session === "idle" && (
        <IdleView
          tracks={tracks}
          selectedTrack={selectedTrack}
          onSelectTrack={setSelectedTrack}
          onStart={(trackId) => void startInterview(trackId)}
          error={error}
        />
      )}
      {session === "connecting" && (
        <ConnectingView onCancel={() => void cancelConnecting()} />
      )}
      {session === "active" && (
        <ActiveInterview
          trackLabel={activeTrackLabel}
          interruptCount={interruptCount}
          interruptFlash={interruptFlash}
          aiTalking={ringAi}
          userTalking={ringUser}
          activeLevel={activeLevel}
          assist={assist}
          onEnd={() => void endInterview()}
        />
      )}
    </main>
  );
}

function IdleView({
  tracks,
  selectedTrack,
  onSelectTrack,
  onStart,
  error,
}: {
  tracks: InterviewTrack[];
  selectedTrack: string | null;
  onSelectTrack: (id: string) => void;
  onStart: (id: string) => void;
  error: string | null;
}) {
  return (
    <section className="relative z-10 mx-auto flex min-h-[80vh] max-w-3xl flex-col justify-center">
      <p className="mb-4 text-xs font-semibold tracking-[0.28em] text-[var(--accent)] uppercase">
        Moss · Sub-10ms retrieval
      </p>
      <h1 className="font-display text-5xl leading-[1.05] tracking-tight text-[var(--cream)] md:text-7xl">
        Moss Interview Coach
      </h1>
      <p className="mt-6 max-w-xl text-lg leading-relaxed text-[var(--fog)] md:text-xl">
        Choose a track, then start a live voice interview. Rubrics land from Moss in milliseconds —
        Whisper, Piper, and Ollama stay fully local.
      </p>

      <div className="mt-10">
        <p className="mb-4 text-xs tracking-[0.22em] text-[var(--fog)] uppercase">
          Choose a track
        </p>
        <ul className="space-y-1 border-y border-[var(--cream)]/10 py-2">
          {tracks.map((track) => {
            const selected = selectedTrack === track.id;
            return (
              <li key={track.id}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => onSelectTrack(track.id)}
                  className={`flex w-full items-baseline justify-between gap-6 px-1 py-3 text-left transition ${
                    selected
                      ? "text-[var(--accent)]"
                      : "text-[var(--cream)] hover:text-[var(--accent)]"
                  }`}
                >
                  <span className="font-display text-2xl md:text-[1.75rem]">{track.label}</span>
                  {track.blurb ? (
                    <span
                      className={`max-w-[14rem] text-right text-xs leading-snug md:max-w-xs md:text-sm ${
                        selected ? "text-[var(--accent)]/80" : "text-[var(--fog)]"
                      }`}
                    >
                      {track.blurb}
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="mt-10 flex flex-wrap items-center gap-4">
        <button
          type="button"
          disabled={!selectedTrack}
          onClick={() => selectedTrack && onStart(selectedTrack)}
          className="rounded-md bg-[var(--accent)] px-7 py-3.5 text-sm font-semibold tracking-wide text-[var(--ink)] transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Start Interview
        </button>
        <span className="text-sm text-[var(--fog)]">
          {selectedTrack
            ? tracks.find((t) => t.id === selectedTrack)?.label
            : "Select a track to continue"}
        </span>
      </div>
      {error && (
        <p className="mt-6 max-w-xl rounded-md border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}
    </section>
  );
}

function ConnectingView({ onCancel }: { onCancel: () => void }) {
  return (
    <section className="relative z-10 mx-auto flex min-h-[80vh] max-w-lg flex-col items-center justify-center text-center">
      <div className="loading-shimmer mb-6 h-1.5 w-48 rounded-full" />
      <h2 className="font-display text-3xl text-[var(--cream)]">Negotiating WebRTC…</h2>
      <p className="mt-3 text-[var(--fog)]">
        Peer-to-peer SmallWebRTC handshake with the local Pipecat agent.
      </p>
      <button
        type="button"
        onClick={onCancel}
        className="mt-8 rounded-md border border-[var(--cream)]/25 px-5 py-2.5 text-sm font-medium text-[var(--cream)] transition hover:border-[var(--danger)] hover:text-[var(--danger)]"
      >
        Cancel
      </button>
    </section>
  );
}

function ActiveInterview({
  trackLabel,
  interruptCount,
  interruptFlash,
  aiTalking,
  userTalking,
  activeLevel,
  assist,
  onEnd,
}: {
  trackLabel: string | null;
  interruptCount: number;
  interruptFlash: boolean;
  aiTalking: boolean;
  userTalking: boolean;
  activeLevel: number;
  assist: AssistPanelState;
  onEnd: () => void;
}) {
  const ringScale = 1 + activeLevel * 0.45;

  return (
    <section className="relative z-10 mx-auto flex min-h-[82vh] max-w-6xl flex-col">
      <header className="mb-8 flex items-start justify-between gap-6">
        <div>
          <p className="font-display text-3xl text-[var(--cream)] md:text-4xl">
            Moss Interview Coach
          </p>
          <p className="mt-1 text-sm text-[var(--fog)]">
            {trackLabel ? `${trackLabel} · ` : ""}
            SmallWebRTC · local voice stack
          </p>
        </div>
        <button
          type="button"
          onClick={onEnd}
          className="rounded-md border border-[var(--cream)]/25 px-4 py-2 text-sm font-medium text-[var(--cream)] transition hover:border-[var(--danger)] hover:text-[var(--danger)]"
        >
          End Interview
        </button>
      </header>

      <div className="grid flex-1 gap-10 lg:grid-cols-[minmax(0,1.05fr)_minmax(280px,0.85fr)] lg:items-start lg:gap-14">
        <div className="flex flex-col items-center justify-center gap-10 md:flex-row md:items-center md:justify-between lg:flex-col lg:items-center xl:flex-row">
          <div className="relative flex h-64 w-64 items-center justify-center md:h-72 md:w-72">
            <div
              className={`absolute inset-0 ${aiTalking || userTalking ? "ring-pulse" : ""}`}
            >
              <div
                className="absolute inset-0 rounded-full border border-[var(--accent)]/30"
                style={{
                  boxShadow: `0 0 ${24 + activeLevel * 60}px rgba(61, 255, 168, ${0.15 + activeLevel * 0.45})`,
                  transform: `scale(${ringScale})`,
                  transition: "transform 80ms linear, box-shadow 80ms linear",
                  borderColor: userTalking ? "var(--ring-user)" : "var(--ring-ai)",
                }}
              />
            </div>
            <div
              className="absolute inset-6 rounded-full border border-[var(--cream)]/10 bg-[var(--panel)]/80 backdrop-blur-sm"
              style={{
                boxShadow: aiTalking
                  ? "inset 0 0 40px rgba(61,255,168,0.18)"
                  : userTalking
                    ? "inset 0 0 40px rgba(94,234,212,0.18)"
                    : "none",
              }}
            />
            <div className="relative z-10 text-center">
              <p className="text-xs tracking-[0.22em] text-[var(--fog)] uppercase">
                {aiTalking ? "Coach speaking" : userTalking ? "You speaking" : "Listening"}
              </p>
              <p className="font-display mt-2 text-2xl text-[var(--cream)]">
                {aiTalking ? "AI" : userTalking ? "You" : "Ready"}
              </p>
            </div>
          </div>

          <div className="w-full max-w-md">
            <div
              className={`border-y border-[var(--cream)]/10 py-4 ${
                interruptFlash ? "interrupt-flash" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <p className="text-xs tracking-[0.2em] text-[var(--fog)] uppercase">
                  Interruption Meter
                </p>
                <span
                  className={`text-sm font-semibold ${
                    interruptFlash ? "text-[var(--warn)]" : "text-[var(--cream)]"
                  }`}
                >
                  {interruptCount > 0 ? "Barge-in OK" : "Standby"}
                </span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--ink)]">
                <div
                  className="h-full rounded-full bg-[var(--warn)] transition-all duration-300"
                  style={{
                    width: `${Math.min(100, interruptCount * 20 + (interruptFlash ? 40 : 8))}%`,
                  }}
                />
              </div>
              <p className="mt-2 text-xs text-[var(--fog)]">
                Successful interruptions: {interruptCount}
              </p>
            </div>
          </div>
        </div>

        <AssistPanel assist={assist} />
      </div>

      <footer className="mt-auto pt-10 text-center">
        <p className="text-xs tracking-[0.22em] text-[var(--fog)] uppercase">
          Powered by <span className="text-[var(--accent)]">Moss</span>
        </p>
      </footer>
    </section>
  );
}

function AssistPanel({ assist }: { assist: AssistPanelState }) {
  const { currentQuestion, userAnswer, grading, feedback } = assist;

  return (
    <aside className="assist-panel flex h-full min-h-[28rem] flex-col border-l border-[var(--accent)]/20 pl-0 lg:pl-8">
      <p className="mb-6 text-xs tracking-[0.28em] text-[var(--accent)] uppercase">
        Assist · live feedback
      </p>

      <div className="space-y-8">
        <div>
          <p className="mb-2 text-xs tracking-[0.18em] text-[var(--fog)] uppercase">
            Current question
          </p>
          {currentQuestion ? (
            <p className="font-display text-2xl leading-snug text-[var(--cream)] md:text-[1.65rem]">
              {currentQuestion}
            </p>
          ) : (
            <p className="text-sm text-[var(--fog)]">
              Waiting for the coach to finish asking…
            </p>
          )}
        </div>

        <div>
          <p className="mb-2 text-xs tracking-[0.18em] text-[var(--fog)] uppercase">
            Your answer
          </p>
          {userAnswer ? (
            <p className="text-sm leading-relaxed text-[var(--fog)] line-clamp-5">
              {userAnswer}
            </p>
          ) : (
            <p className="text-sm text-[var(--fog)]/70">
              Speak after the question to see a snippet here.
            </p>
          )}
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-xs tracking-[0.18em] text-[var(--fog)] uppercase">Feedback</p>
            {feedback && (
              <span className="font-mono text-sm font-semibold tabular-nums text-[var(--accent)]">
                {feedback.score}/{feedback.maxScore}
              </span>
            )}
          </div>

          {grading && !feedback && (
            <p className="assist-grading text-sm text-[var(--accent)]/80">
              Grading against Moss rubric…
            </p>
          )}

          {feedback && (
            <div className="space-y-3">
              {feedback.topic && (
                <p className="text-xs text-[var(--fog)]">Topic · {feedback.topic}</p>
              )}
              <p className="text-sm leading-relaxed text-[var(--cream)]">{feedback.summary}</p>
              {feedback.tips.length > 0 && (
                <ul className="space-y-2 border-t border-[var(--cream)]/10 pt-3">
                  {feedback.tips.map((tip, i) => (
                    <li
                      key={`${feedback.score}-${i}`}
                      className="flex gap-2 text-sm leading-snug text-[var(--fog)]"
                    >
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[var(--accent)]" />
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {!grading && !feedback && (
            <p className="text-sm text-[var(--fog)]/70">
              When the coach decides your answer is ready, it calls a grading tool grounded in the
              Moss rubric — score and tips land here without interrupting the interview.
            </p>
          )}
        </div>
      </div>
    </aside>
  );
}
