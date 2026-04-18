export interface QueryResultDocumentInfo {
    readonly id: string;
    readonly text: string;
    readonly metadata: Record<string, string>;
}

interface SearchImagesResponse {
    readonly results: QueryResultDocumentInfo[];
    readonly timeTakenInMs: number;
    readonly status: "fulfilled" | "rejected";
    readonly errorMessage?: string;
}

export interface TierInfo {
    readonly value: string;
    readonly label: string;
    readonly docCount: string;
}

export const TIERS: readonly TierInfo[] = [
    { value: "1k", label: "1K images", docCount: "1,000" },
    { value: "10k", label: "10K images", docCount: "10,000" },
    { value: "50k", label: "50K images", docCount: "50,000" },
];

const currentTier = "1k";

export const getCurrentTier = (): string => currentTier;

export const getCurrentTierInfo = (): TierInfo =>
    TIERS.find((t) => t.value === currentTier) ?? TIERS[0];

export const PYTHON_API_BASE = (import.meta.env.MOSS_PYTHON_API_URL as string | undefined) || "http://localhost:8000";
export const API_PREFIX = `${PYTHON_API_BASE}/demo/image-search`;

export const searchImagesViaPythonApi = async (
    term: string,
    tier: string,
    topK = 5
): Promise<SearchImagesResponse> => {
    const trimmedTerm = term.trim();
    if (!trimmedTerm) {
        return { results: [], timeTakenInMs: 0, status: "fulfilled" };
    }

    try {
        const url = `${API_PREFIX}/search?query=${encodeURIComponent(trimmedTerm)}&tier=${encodeURIComponent(tier)}&top_k=${topK}`;
        const response = await fetch(url);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text}`);
        }
        const data = (await response.json()) as { docs: QueryResultDocumentInfo[]; timeTakenInMs: number };
        const docs: QueryResultDocumentInfo[] = (data.docs ?? []).map((doc) => ({
            ...doc,
            metadata: doc.metadata ?? ({} as Record<string, string>),
        }));
        return { results: docs, timeTakenInMs: data.timeTakenInMs ?? 0, status: "fulfilled" };
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error("Python API search failed:", errorMessage);
        return { results: [], timeTakenInMs: 0, status: "rejected", errorMessage };
    }
};

export const checkPythonApiHealth = async (): Promise<boolean> => {
    try {
        const response = await fetch(`${API_PREFIX}/health`);
        return response.ok;
    } catch {
        return false;
    }
};
