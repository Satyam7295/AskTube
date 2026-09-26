export type TranscriptSegment = {
  text: string;
  start: number;
  duration: number;
};

export type TranscriptData = {
  video_id: string;
  language: string | null;
  is_generated: boolean | null;
  segments: TranscriptSegment[];
  total_segments: number;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AskResponse = {
  query: string;
  answer: string;
  sources: Array<{
    chunk_id: number;
    video_id: string;
    score: number;
    text: string;
    start_time: number;
    end_time: number;
    chunk_index: number;
    language_code: string | null;
    segment_start_index: number | null;
    segment_end_index: number | null;
    character_count: number | null;
    word_count: number | null;
  }>;
  provider: string | null;
  model: string | null;
  insufficient_context: boolean;
};

export async function askQuestion(query: string, signal?: AbortSignal): Promise<AskResponse> {
  const response = await fetch(`${apiUrl}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    signal,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.detail ?? "We could not answer that question.");
  }
  return body as AskResponse;
}

export async function getVideoTranscript(videoId: string, language?: string, signal?: AbortSignal): Promise<TranscriptData> {
  const params = language ? `?language=${encodeURIComponent(language)}` : "";
  const response = await fetch(`${apiUrl}/api/videos/${encodeURIComponent(videoId)}/transcript${params}`, { signal });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.detail ?? "We could not load this transcript.");
  }
  return body as TranscriptData;
}