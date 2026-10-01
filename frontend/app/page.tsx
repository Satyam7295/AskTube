"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { ChatWindow } from "../components/chat/ChatWindow";
import { PlaylistInput } from "../components/playlist/PlaylistInput";
import { ingestPlaylist, type PlaylistData } from "../lib/api/playlists";
import type { ValidatedPlaylist } from "../lib/youtube/playlistUrl";

type View = "home" | "chat";

const processingMessages = ["Reading playlist...", "Processing videos...", "Preparing transcripts...", "Building your knowledge base..."];

export default function Home() {
  const [view, setView] = useState<View>("home");
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [validatedPlaylist, setValidatedPlaylist] = useState<ValidatedPlaylist | null>(null);
  const [playlistData, setPlaylistData] = useState<PlaylistData | null>(null);
  const [isProcessingPlaylist, setIsProcessingPlaylist] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);

  useEffect(() => {
    if (!isProcessingPlaylist) return;
    const timer = window.setInterval(() => setProcessingStep((step) => Math.min(step + 1, processingMessages.length - 1)), 2200);
    return () => window.clearInterval(timer);
  }, [isProcessingPlaylist]);

  async function handlePlaylistValidated(playlist: ValidatedPlaylist) {
    setIsProcessingPlaylist(true);
    setProcessingStep(0);
    try {
      const data = await ingestPlaylist(playlist.playlistId);
      setValidatedPlaylist(playlist);
      setPlaylistData(data);
      setView("chat");
    } finally {
      setIsProcessingPlaylist(false);
    }
  }

  return (
    <AppShell activeView={view} onNavigate={(nextView) => setView(nextView as View)}>
      {view === "home" && (
        <div className="mx-auto flex min-h-[calc(100vh-68px)] max-w-5xl flex-col justify-center px-4 py-12 sm:px-8 sm:py-16">
          <div className="max-w-3xl"><p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-[#e32626]">Your playlist, understood</p><h1 className="max-w-2xl text-4xl font-bold tracking-[-0.04em] text-[#16181d] sm:text-6xl">Ask questions. Find answers. Learn from any YouTube playlist.</h1><p className="mt-5 max-w-xl text-base leading-7 text-[#60646c] sm:text-lg">AskTube studies the playlist for you, then finds the explanations that answer your questions.</p></div>
          <div className="mt-10"><PlaylistInput value={playlistUrl} onChange={setPlaylistUrl} onPlaylistValidated={handlePlaylistValidated} isProcessingPlaylist={isProcessingPlaylist} processingMessage={processingMessages[processingStep]} /></div>
          <div className="mt-10 flex flex-wrap gap-x-7 gap-y-3 text-sm text-[#60646c]"><span><strong className="text-[#16181d]">Paste</strong> a playlist</span><span><strong className="text-[#16181d]">Ask</strong> what you want to know</span><span><strong className="text-[#16181d]">Get</strong> the source video</span></div>
        </div>
      )}
      {view === "chat" && validatedPlaylist && playlistData && <ChatWindow playlist={playlistData} />}
    </AppShell>
  );
}
