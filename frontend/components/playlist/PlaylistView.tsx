"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { ExternalLink, MessageCircle, Play } from "lucide-react";
import { getStoredPlaylist, type PlaylistData } from "../../lib/api/playlists";

type PlaylistViewProps = { playlistId: string; onOpenChat: () => void };

export function PlaylistView({ playlistId, onOpenChat }: PlaylistViewProps) {
  const [data, setData] = useState<PlaylistData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    void getStoredPlaylist(playlistId, controller.signal)
      .then(setData)
      .catch((fetchError: unknown) => {
        if (fetchError instanceof DOMException && fetchError.name === "AbortError") return;
        setError(fetchError instanceof Error ? fetchError.message : "We could not load this playlist.");
      });
    return () => controller.abort();
  }, [playlistId]);

  if (error) return <PlaylistState title="Could not load this playlist" message={error} />;
  if (!data) return <PlaylistState title="Loading saved playlist" message="Loading saved playlist..." loading />;

  const { playlist, videos } = data;
  return <div className="mx-auto max-w-6xl px-4 py-7 sm:px-8 sm:py-10">
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div><p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-[#e32626]">YouTube playlist</p><h1 className="text-3xl font-bold tracking-tight">{playlist.title}</h1><p className="mt-2 text-sm text-[#60646c]">{videos.length} {videos.length === 1 ? "video" : "videos"}{playlist.channel_title ? ` · ${playlist.channel_title}` : ""}</p></div>
      <button type="button" onClick={onOpenChat} disabled={!videos.length} className="inline-flex items-center gap-2 rounded-xl bg-[#e32626] px-4 py-3 text-sm font-bold text-white hover:bg-[#c91e24] disabled:cursor-not-allowed disabled:opacity-50"><MessageCircle size={17} /> Ask about this playlist</button>
    </div>
    <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
      <section className="overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white"><div className="relative aspect-video bg-[#202b38]">{playlist.thumbnail ? <Image src={playlist.thumbnail} alt="" fill unoptimized className="object-cover" /> : <div className="absolute inset-0 flex items-center justify-center"><Play className="text-white" fill="currentColor" size={36} /></div>}</div><div className="p-5"><h2 className="text-xl font-bold">{playlist.title}</h2><p className="mt-3 whitespace-pre-line text-sm leading-6 text-[#60646c]">{playlist.description || "No description provided."}</p></div></section>
      <section aria-labelledby="video-list-title"><div className="mb-3 flex items-center justify-between"><h2 id="video-list-title" className="text-lg font-bold">Videos in this playlist</h2><span className="text-sm text-[#9297a1]">{videos.length} total</span></div>{videos.length === 0 ? <p className="rounded-xl border border-dashed border-[#d9dce1] p-6 text-sm text-[#60646c]">This playlist does not contain any videos.</p> : <div className="space-y-2">{videos.map((video) => <article key={`${video.position}-${video.video_id}`} className="group flex gap-3 rounded-xl border border-transparent p-2 transition-colors hover:border-[#e5e7eb] hover:bg-white"><div className="flex w-7 shrink-0 items-center justify-center text-xs font-bold text-[#9297a1]">{video.position + 1}</div><a href={video.video_url} target="_blank" rel="noreferrer" className="relative aspect-video w-36 shrink-0 overflow-hidden rounded-lg bg-[#eef0f2] sm:w-48">{video.thumbnail && <Image src={video.thumbnail} alt="" fill unoptimized className="object-cover" />} {video.duration && <span className="absolute bottom-1 right-1 rounded bg-black/80 px-1 text-[10px] font-bold text-white">{video.duration}</span>}</a><div className="min-w-0 flex-1"><a href={video.video_url} target="_blank" rel="noreferrer" className="line-clamp-2 text-sm font-bold hover:text-[#d91f26]">{video.title}</a><p className="mt-1 line-clamp-2 text-xs leading-5 text-[#9297a1]">{video.description || "No description provided."}</p><a href={video.video_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-[#d91f26]">Watch on YouTube <ExternalLink size={13} /></a></div></article>)}</div>}</section>
    </div>
  </div>;
}

function PlaylistState({ title, message, loading = false }: { title: string; message: string; loading?: boolean }) {
  return <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-8"><div className={`mx-auto mb-5 h-10 w-10 rounded-full border-4 border-[#ffd2d2] ${loading ? "animate-spin border-t-[#e32626]" : "border-t-[#e32626]"}`} /><h1 className="text-2xl font-bold">{title}</h1><p className="mt-3 text-sm leading-6 text-[#60646c]">{message}</p></div>;
}
