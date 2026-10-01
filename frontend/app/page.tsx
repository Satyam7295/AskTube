"use client";

import { useEffect, useState } from "react";
import { ChatWindow } from "../components/chat/ChatWindow";
import { PlaylistInput } from "../components/playlist/PlaylistInput";
import { ingestPlaylist, type PlaylistData } from "../lib/api/playlists";
import type { ValidatedPlaylist } from "../lib/youtube/playlistUrl";

const processingMessages = ["Reading playlist...", "Processing videos...", "Understanding transcripts...", "Building your knowledge base..."];

export default function Home() {
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [validatedPlaylist, setValidatedPlaylist] = useState<ValidatedPlaylist | null>(null);
  const [playlistData, setPlaylistData] = useState<PlaylistData | null>(null);
  const [isProcessingPlaylist, setIsProcessingPlaylist] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);
  const [processingError, setProcessingError] = useState<string | null>(null);

  useEffect(() => {
    if (!isProcessingPlaylist) return;
    const timer = window.setInterval(() => setProcessingStep((step) => Math.min(step + 1, processingMessages.length - 1)), 2200);
    return () => window.clearInterval(timer);
  }, [isProcessingPlaylist]);

  async function handlePlaylistValidated(playlist: ValidatedPlaylist) {
    setProcessingError(null);
    setPlaylistData(null);
    setValidatedPlaylist(null);
    setIsProcessingPlaylist(true);
    setProcessingStep(0);
    try {
      const data = await ingestPlaylist(playlist.playlistId);
      setValidatedPlaylist(playlist);
      setPlaylistData(data);
    } catch (error) {
      setProcessingError(error instanceof Error ? error.message : "We couldn't process this playlist. Try again.");
      throw error;
    } finally {
      setIsProcessingPlaylist(false);
    }
  }

  if (validatedPlaylist && playlistData) {
    return <ChatWindow playlist={playlistData} playlistUrl={validatedPlaylist.normalizedUrl} onLoadAnother={() => { setPlaylistData(null); setValidatedPlaylist(null); setPlaylistUrl(""); }} />;
  }

  return <main className="landing-page">
    <div className="landing-mark">ASK<span>TUBE</span></div>
    <div className="landing-content">
      <p className="eyebrow">Your playlist, understood</p>
      <h1>AskTube</h1>
      <p className="landing-copy">Ask questions and learn from any YouTube playlist. AskTube studies the ideas inside so you can get straight to what matters.</p>
      <PlaylistInput value={playlistUrl} onChange={setPlaylistUrl} onPlaylistValidated={handlePlaylistValidated} isProcessingPlaylist={isProcessingPlaylist} processingMessage={processingMessages[processingStep]} />
      {processingError && <div role="alert" className="landing-error">{processingError}</div>}
      <div className="landing-steps"><span><strong>Paste</strong> a playlist</span><span><strong>Ask</strong> what you want to know</span><span><strong>Get</strong> the source video</span></div>
    </div>
  </main>;
}
