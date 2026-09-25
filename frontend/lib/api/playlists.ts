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
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getStoredPlaylist(playlistId: string, signal?: AbortSignal): Promise<PlaylistData> {
  const response = await fetch(`${apiUrl}/api/playlists/${encodeURIComponent(playlistId)}/stored`, { signal });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("This playlist hasn't been loaded into AskTube yet.");
    }
    throw new Error(body?.detail ?? "We could not load this playlist.");
  }
  return body as PlaylistData;
}
