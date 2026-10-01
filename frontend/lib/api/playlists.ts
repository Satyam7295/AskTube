export type PlaylistData = {
  playlist: {
    playlist_id: string;
    title: string;
    description: string;
    thumbnail: string | null;
    channel_title: string | null;
  };
  videos: Array<{
    video_id: string;
    title: string;
    description: string;
    thumbnail: string | null;
    position: number;
    video_url: string;
    duration: string | null;
  }>;
  total_videos: number;
  indexing_status: "PENDING" | "INDEXING" | "INDEXING_PARTIAL" | "INDEXING_COMPLETED" | "INDEXING_FAILED";
  processed_videos: number;
  indexed_videos: number;
  skipped_videos: number;
  videos_without_transcripts: number;
  failed_videos: number;
  last_error: string | null;
  video_diagnostics: Array<{ video_id: string; title: string; status: string; error: string; technical_details?: string }>;
  transcript_access_blocked: boolean;
};


const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const playlistRequestTimeoutMs = 30000;

async function fetchPlaylist(url: string, signal?: AbortSignal): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), playlistRequestTimeoutMs);
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  try {
    return await fetch(url, { signal: controller.signal });
  } catch (error) {
    if (!signal?.aborted && error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The playlist request timed out. Please check the backend connection and try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

function normalizePlaylistData(body: PlaylistData): PlaylistData {
  return {
    ...body,
    total_videos: body.total_videos ?? 0,
    indexing_status: body.indexing_status ?? "PENDING",
    processed_videos: body.processed_videos ?? 0,
    indexed_videos: body.indexed_videos ?? 0,
    skipped_videos: body.skipped_videos ?? 0,
    videos_without_transcripts: body.videos_without_transcripts ?? body.skipped_videos ?? 0,
    failed_videos: body.failed_videos ?? 0,
    last_error: body.last_error ?? null,
    video_diagnostics: body.video_diagnostics ?? [],
    transcript_access_blocked: body.transcript_access_blocked ?? false,
  };
}


async function parsePlaylistResponse(response: Response): Promise<PlaylistData> {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.detail ?? "We could not load this playlist.");
  }
  return normalizePlaylistData(body as PlaylistData);
}

export async function ingestPlaylist(playlistId: string, signal?: AbortSignal): Promise<PlaylistData> {
  const response = await fetchPlaylist(`${apiUrl}/api/playlists/${encodeURIComponent(playlistId)}`, signal);
  return parsePlaylistResponse(response);
}

export async function getStoredPlaylist(playlistId: string, signal?: AbortSignal): Promise<PlaylistData> {
  const response = await fetchPlaylist(`${apiUrl}/api/playlists/${encodeURIComponent(playlistId)}/stored`, signal);
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("This playlist hasn't been loaded into AskTube yet.");
    }
    throw new Error(body?.detail ?? "We could not load this playlist.");
  }
  return normalizePlaylistData(body as PlaylistData);
}
