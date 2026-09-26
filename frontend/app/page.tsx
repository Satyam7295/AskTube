"use client";

import { useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { ChatWindow } from "../components/chat/ChatWindow";
import { PlaylistInput } from "../components/playlist/PlaylistInput";
import { PlaylistView } from "../components/playlist/PlaylistView";
import { ingestPlaylist } from "../lib/api/playlists";
import type { ValidatedPlaylist } from "../lib/youtube/playlistUrl";

type View = "home" | "playlist" | "chat";

export default function Home() {
  const [view, setView] = useState<View>("home");
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [validatedPlaylist, setValidatedPlaylist] = useState<ValidatedPlaylist | null>(null);

  async function handlePlaylistValidated(playlist: ValidatedPlaylist) {
    await ingestPlaylist(playlist.playlistId);
    setValidatedPlaylist(playlist);
    setView("playlist");
  }

  return (
    <AppShell activeView={view} onNavigate={(nextView) => setView(nextView as View)}>
      {view === "home" && (
        <div className="mx-auto max-w-6xl px-4 py-7 sm:px-8 sm:py-10">
          <div className="mb-9 max-w-3xl">
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-[#e32626]">Your playlist, understood</p>
            <h1 className="max-w-2xl text-3xl font-bold tracking-[-0.03em] text-[#16181d] sm:text-5xl">Turn a YouTube playlist into a knowledge base.</h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-[#60646c] sm:text-lg">Paste a playlist and ask questions about its videos, ideas, and moments.</p>
          </div>
          <PlaylistInput value={playlistUrl} onChange={setPlaylistUrl} onPlaylistValidated={handlePlaylistValidated} />
          <section className="mt-14 border-t border-[#e5e7eb] pt-8" aria-labelledby="empty-state-title">
            <div className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr] lg:items-center">
              <div>
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-[#fff0f0] text-[#e32626]" aria-hidden="true">▶</div>
                <h2 id="empty-state-title" className="text-2xl font-bold tracking-tight">Start with something worth exploring.</h2>
                <p className="mt-3 max-w-xl leading-7 text-[#60646c]">AskTube keeps the videos in view while you explore the bigger picture. Answers will point back to the exact video and timestamp that matters.</p>
                <div className="mt-6 flex flex-wrap gap-2 text-sm text-[#60646c]">
                  <span className="rounded-full border border-[#e5e7eb] bg-white px-3 py-2">Browse the playlist</span>
                  <span className="rounded-full border border-[#e5e7eb] bg-white px-3 py-2">Ask naturally</span>
                  <span className="rounded-full border border-[#e5e7eb] bg-white px-3 py-2">Jump to the source</span>
                </div>
              </div>
              <div className="rounded-2xl border border-[#e5e7eb] bg-white p-5">
                <div className="mb-4 flex items-center justify-between text-xs font-bold uppercase tracking-[0.14em] text-[#9297a1]"><span>What you can ask</span><span className="h-2 w-2 rounded-full bg-[#e32626]" /></div>
                <p className="border-b border-[#f0f1f3] pb-4 text-sm font-semibold">“Where does the speaker explain the core idea?”</p>
                <p className="pt-4 text-sm font-semibold text-[#60646c]">“Compare the examples from videos 2 and 5.”</p>
              </div>
            </div>
          </section>
        </div>
      )}
      {view === "playlist" && validatedPlaylist && <PlaylistView playlistId={validatedPlaylist.playlistId} onOpenChat={() => setView("chat")} />}
      {view === "chat" && validatedPlaylist && <ChatWindow />}
    </AppShell>
  );
}
