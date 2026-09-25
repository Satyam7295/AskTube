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

export async function getVideoTranscript(videoId: string, language?: string, signal?: AbortSignal): Promise<TranscriptData> {
  const params = language ? `?language=${encodeURIComponent(language)}` : "";
  const response = await fetch(`${apiUrl}/api/videos/${encodeURIComponent(videoId)}/transcript${params}`, { signal });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.detail ?? "We could not load this transcript.");
  }
  return body as TranscriptData;
}