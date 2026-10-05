"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ArrowUp, ExternalLink, Info, Plus, Sparkles, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { ApiError, askQuestion, type AskResponse } from "../../lib/api/videos";
import { getStoredPlaylist, type PlaylistData } from "../../lib/api/playlists";

type ChatWindowProps = { playlist: PlaylistData; playlistUrl: string; onLoadAnother: () => void };
type ConversationTurn = { query: string; response: AskResponse };

const suggestions = [
  "Explain the two-pointer pattern.",
  "Where is binary search explained?",
  "Compare BFS and DFS.",
];

export function ChatWindow({ playlist, playlistUrl, onLoadAnother }: ChatWindowProps) {
  const [currentPlaylist, setCurrentPlaylist] = useState(playlist);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isTranscriptAccessModalOpen, setIsTranscriptAccessModalOpen] = useState(false);

  const progress = getProgress(currentPlaylist);
  const isIndexing = currentPlaylist.indexing_status === "PENDING" || currentPlaylist.indexing_status === "INDEXING";
  const statusText = statusLabel(currentPlaylist.indexing_status, progress.indexed, progress.total);
  const transcriptAccessBlocked = hasBlockedTranscript(currentPlaylist);

  useEffect(() => {
    setCurrentPlaylist(playlist);
  }, [playlist]);

  useEffect(() => {
    if (transcriptAccessBlocked) setIsTranscriptAccessModalOpen(true);
  }, [transcriptAccessBlocked]);

  useEffect(() => {
    if (["INDEXING_COMPLETED", "INDEXING_PARTIAL", "INDEXING_FAILED"].includes(currentPlaylist.indexing_status)) return;
    const timer = window.setInterval(() => {
      void getStoredPlaylist(currentPlaylist.playlist.playlist_id)
        .then((storedPlaylist) => setCurrentPlaylist(storedPlaylist))
        .catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [currentPlaylist.indexing_status, currentPlaylist.playlist.playlist_id]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitQuestion(question);
  }

  async function submitQuestion(nextQuestion: string) {
    const query = nextQuestion.trim();
    if (!query || isSearching) return;
    setQuestion("");
    setIsSearching(true);
    setError(null);
    try {
      const response = await askQuestion(query, currentPlaylist.playlist.playlist_id);
      setTurns((current) => [...current, { query, response }]);
    } catch (error) {
      console.error("AskTube question failed", error);
      const fallback = "I couldn't search the playlist right now. Please try again.";
      if (process.env.NODE_ENV === "development" && error instanceof ApiError) {
        setError(`${fallback} (${error.status}: ${error.message})`);
      } else {
        setError(fallback);
      }
    } finally {
      setIsSearching(false);
    }
  }

  return <main className="asktube-shell">
    <aside className="knowledge-panel">
      <div className="wordmark">ASK<span>TUBE</span></div>
      <p className="eyebrow">Knowledge source</p>
      <h1>Your knowledge source</h1>
      <p className="panel-copy">Load a YouTube playlist once, then interact with its content.</p>
      <section className="source-summary" aria-label="Loaded playlist">
        <p className="source-kicker">YouTube playlist</p>
        <h2>{currentPlaylist.playlist.title}</h2>
        <p className="source-url">{playlistUrl.replace("https://www.", "")}</p>
        <div className="source-status"><span>{statusText}</span><strong>{progress.processed} of {progress.total} processed</strong></div>
        <p className="indexed-note">{transcriptAccessBlocked ? "Transcript access temporarily unavailable" : currentPlaylist.indexing_status === "INDEXING_COMPLETED" ? "Indexed and ready to search" : currentPlaylist.indexing_status === "INDEXING_FAILED" ? "Indexing failed; no searchable context is available" : "Indexing playlist; searchable videos will appear progressively"}</p>
      </section>
      <button type="button" onClick={onLoadAnother} className="load-another"><Plus size={16} /> Load another playlist</button>
      <section className="prompt-card" aria-labelledby="prompt-title">
        <h2 id="prompt-title">Ask anything from the playlist</h2>
        <div className="prompt-list">{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => void submitQuestion(suggestion)}>{suggestion}</button>)}</div>
        <p>Answers cite the relevant video.</p>
      </section>
    </aside>
    <section className="conversation-panel">
      <header className="conversation-header"><div><p className="eyebrow">AskTube</p><h2>Ask your playlist</h2></div><div className={`ready-label status-${currentPlaylist.indexing_status}`}><span /> {statusText}</div></header>
      <div className="conversation-intro"><strong>{introTitle(currentPlaylist)}</strong>{isIndexing ? <><div className="indexing-progress" role="progressbar" aria-label="Playlist indexing progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress.percent}><div className="indexing-progress-fill" style={{ width: `${progress.percent}%` }} /></div><span className="indexing-progress-percent">{progress.percent}%</span><p className="indexing-progress-detail">{progressDetail(progress)}</p><p className="indexing-warning">Answers may be incomplete while indexing is in progress.</p></> : <><p className="indexing-progress-detail">{progressDetail(progress)}</p>{currentPlaylist.indexing_status === "INDEXING_FAILED" && !transcriptAccessBlocked && <p className="indexing-warning">No searchable content was created. Try loading the playlist again.</p>}</>}{transcriptAccessBlocked && <div className="indexing-blocked-state" role="status"><strong>Transcript access temporarily unavailable</strong><span>Try again later.</span></div>}</div>
      <div className="conversation-body">
        {turns.length === 0 && !isSearching && <div className="empty-prompt"><Sparkles size={18} /><span>Choose a question from the left or ask your own below.</span></div>}
        <div aria-live="polite" aria-atomic="false">
          {turns.map(({ query, response }, index) => <article key={`${index}-${query}`} className="conversation-turn"><div className="user-message">{query}</div><div className="answer-block"><p className="answer-label">ASKTUBE <span>•</span> GROUNDED ANSWER</p><div className="answer-copy"><ReactMarkdown>{response.answer}</ReactMarkdown></div><SourceList sources={response.sources} playlist={currentPlaylist} /></div></article>)}
          {isSearching && <div className="searching-state"><Image src="/assets/Searching.gif" alt="Searching playlist animation" width={56} height={56} unoptimized priority /><span>Searching your playlist...</span></div>}
        </div>
        {error && <div role="alert" className="chat-error"><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error"><X size={16} /></button></div>}
      </div>
      <form onSubmit={handleSubmit} className="question-form"><label htmlFor="question" className="sr-only">Ask anything about this playlist</label><input id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about this playlist..." disabled={isSearching} /><button type="submit" aria-label={isSearching ? "Searching" : "Ask AskTube"} disabled={!question.trim() || isSearching}><ArrowUp size={19} /></button></form>
    </section>
    {isTranscriptAccessModalOpen && <TranscriptAccessModal onClose={() => setIsTranscriptAccessModalOpen(false)} />}
  </main>;
}

function getProgress(playlist: PlaylistData) {
  const total = safeCount(playlist.total_videos);
  const indexed = total > 0 ? Math.min(total, safeCount(playlist.indexed_videos)) : 0;
  return { total, indexed, processed: total > 0 ? Math.min(total, safeCount(playlist.processed_videos)) : 0, failed: safeCount(playlist.failed_videos), withoutTranscripts: safeCount(playlist.videos_without_transcripts), percent: total > 0 ? Math.round((indexed / total) * 100) : 0 };
}

function safeCount(value: number | null | undefined) {
  return Number.isFinite(value) ? Math.max(0, value as number) : 0;
}

function statusLabel(status: PlaylistData["indexing_status"], indexed: number, total: number) {
  if (status === "INDEXING_FAILED") return "INDEXING FAILED";
  const label = status === "PENDING" ? "PREPARING" : status === "INDEXING" ? "INDEXING" : status === "INDEXING_PARTIAL" ? "PARTIALLY READY" : "READY";
  return `${label} · ${indexed} / ${total} VIDEOS`;
}

function introTitle(playlist: PlaylistData) {
  if (playlist.indexing_status === "INDEXING_COMPLETED") return "Knowledge base ready";
  if (playlist.indexing_status === "INDEXING_PARTIAL") return "Knowledge base partially ready";
  if (playlist.indexing_status === "INDEXING_FAILED") return "Playlist indexing failed";
  return "Indexing playlist...";
}

function progressDetail(progress: ReturnType<typeof getProgress>) {
  const details = [`${progress.indexed} of ${progress.total} videos indexed`, `${progress.processed} processed`];
  if (progress.failed > 0) details.push(`${progress.failed} failed`);
  if (progress.withoutTranscripts > 0) details.push(`${progress.withoutTranscripts} without ${progress.withoutTranscripts === 1 ? "transcript" : "transcripts"}`);
  return details.join(" · ");
}

function hasBlockedTranscript(playlist: PlaylistData) {
  return playlist.transcript_access_blocked === true;
}

function TranscriptAccessModal({ onClose }: { onClose: () => void }) {
  const primaryButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    primaryButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="transcript-modal" role="dialog" aria-modal="true" aria-labelledby="transcript-modal-title" aria-describedby="transcript-modal-description">
      <div className="modal-icon" aria-hidden="true"><Info size={19} /></div>
      <h2 id="transcript-modal-title">Transcript Access Temporarily Unavailable</h2>
      <p id="transcript-modal-description">YouTube is temporarily blocking transcript requests from this network.</p>
      <p className="modal-secondary">This may be a temporary restriction. Please wait a while and try indexing the playlist again.</p>
      <p className="modal-reassurance">Your playlist and video data are safe. No videos were deleted.</p>
      <div className="modal-actions">
        <button ref={primaryButtonRef} type="button" className="modal-primary" onClick={onClose}>Try Again Later</button>
        <button type="button" className="modal-secondary-action" onClick={onClose}>Close</button>
      </div>
    </section>
  </div>;
}

function SourceList({ sources, playlist }: { sources: AskResponse["sources"]; playlist: PlaylistData }) {
  if (!sources.length) return null;
  const uniqueSources = sources.filter((source, index, all) => all.findIndex((candidate) => candidate.video_id === source.video_id) === index).slice(0, 3);
  return <section className="sources-section" aria-labelledby="sources-title"><h2 id="sources-title">Sources from your playlist</h2><div className="source-grid">{uniqueSources.map((source) => { const video = playlist.videos.find((item) => item.video_id === source.video_id); const timestamp = Math.floor(source.start_time); return <article key={source.chunk_id} className="answer-source"><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(source.video_id)}&t=${timestamp}s`} target="_blank" rel="noreferrer"><span className="play-dot"><ExternalLink size={12} /></span><span className="source-title">{video?.title ?? "Relevant video"}</span></a><div><span>Video {video ? video.position + 1 : "source"} • {formatTimestamp(source.start_time)}</span><strong>{Math.round(source.score * 100)}%</strong></div></article>; })}</div></section>;
}

function formatTimestamp(seconds: number) {
  const totalSeconds = Math.max(0, Math.floor(seconds));
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, "0")}`;
}
