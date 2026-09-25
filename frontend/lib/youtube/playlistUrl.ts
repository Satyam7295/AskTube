export type ValidatedPlaylist = {
  playlistId: string;
  normalizedUrl: string;
};

export type PlaylistUrlResult =
  | ({ valid: true } & ValidatedPlaylist)
  | { valid: false; error: string };

const YOUTUBE_HOSTNAMES = new Set(["youtube.com", "www.youtube.com", "m.youtube.com"]);

export function parseYouTubePlaylistUrl(input: string): PlaylistUrlResult {
  if (!input.trim()) {
    return { valid: false, error: "Please enter a YouTube playlist URL." };
  }

  try {
    const url = new URL(input.trim());

    if (url.protocol !== "https:" || !YOUTUBE_HOSTNAMES.has(url.hostname.toLowerCase())) {
      return { valid: false, error: "This doesn't appear to be a valid YouTube playlist URL." };
    }

    const playlistId = url.searchParams.get("list")?.trim();
    if (!playlistId) {
      return { valid: false, error: "This doesn't appear to be a valid YouTube playlist URL." };
    }

    return {
      valid: true,
      playlistId,
      normalizedUrl: `https://www.youtube.com/playlist?list=${encodeURIComponent(playlistId)}`,
    };
  } catch {
    return { valid: false, error: "This doesn't appear to be a valid YouTube playlist URL." };
  }
}