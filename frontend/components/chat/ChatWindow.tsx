"use client";

import { FormEvent, useState } from "react";
import Image from "next/image";
import { ArrowUp, ExternalLink, Plus, Sparkles, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { askQuestion, type AskResponse } from "../../lib/api/videos";
import type { PlaylistData } from "../../lib/api/playlists";

type ChatWindowProps = { playlist: PlaylistData; playlistUrl: string; onLoadAnother: () => void };
type ConversationTurn = { query: string; response: AskResponse };

const suggestions = [
  "Explain the two-pointer pattern.",
  "Where is binary search explained?",
  "Compare BFS and DFS.",
];

export function ChatWindow({ playlist, playlistUrl, onLoadAnother }: ChatWindowProps) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const progress = getProgress(currentPlaylist);
  const isIndexing = currentPlaylist.indexing_status === "pending" || currentPlaylist.indexing_status === "indexing";
  const statusText = statusLabel(currentPlaylist.indexing_status, progress.indexed, progress.total);

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
      const response = await askQuestion(query, playlist.playlist.playlist_id);
      setTurns((current) => [...current, { query, response }]);
    } catch {
      setError("I couldn't search the playlist right now. Please try again.");
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
        <h2>{playlist.playlist.title}</h2>
        <p className="source-url">{playlistUrl.replace("https://www.", "")}</p>
        <div className="source-status"><span>READY</span><strong>{playlist.total_videos} videos</strong></div>
        <p className="indexed-note">Indexed and ready to search</p>
      </section>
      <button type="button" onClick={onLoadAnother} className="load-another"><Plus size={16} /> Load another playlist</button>
      <section className="prompt-card" aria-labelledby="prompt-title">
        <h2 id="prompt-title">Ask anything from the playlist</h2>
        <div className="prompt-list">{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => void submitQuestion(suggestion)}>{suggestion}</button>)}</div>
        <p>Answers cite the relevant video.</p>
      </section>
    </aside>
    <section className="conversation-panel">
      <header className="conversation-header"><div><p className="eyebrow">AskTube</p><h2>Ask your playlist</h2></div><div className="ready-label"><span /> Indexed &amp; ready</div></header>
      <p className="conversation-intro"><strong>Your playlist is ready.</strong> Ask a question and I&apos;ll answer using only the videos in this playlist.</p>
      <div className="conversation-body">
        {turns.length === 0 && !isSearching && <div className="empty-prompt"><Sparkles size={18} /><span>Choose a question from the left or ask your own below.</span></div>}
        <div aria-live="polite" aria-atomic="false">
          {turns.map(({ query, response }, index) => <article key={`${index}-${query}`} className="conversation-turn"><div className="user-message">{query}</div><div className="answer-block"><p className="answer-label">ASKTUBE <span>•</span> GROUNDED ANSWER</p><div className="answer-copy"><ReactMarkdown>{response.answer}</ReactMarkdown></div><SourceList sources={response.sources} playlist={playlist} /></div></article>)}
          {isSearching && <div className="searching-state"><Image src="/assets/Searching.gif" alt="Searching playlist animation" width={56} height={56} unoptimized priority /><span>Searching your playlist...</span></div>}
        </div>
        {error && <div role="alert" className="chat-error"><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error"><X size={16} /></button></div>}
      </div>
      <form onSubmit={handleSubmit} className="question-form"><label htmlFor="question" className="sr-only">Ask anything about this playlist</label><input id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about this playlist..." disabled={isSearching} /><button type="submit" aria-label={isSearching ? "Searching" : "Ask AskTube"} disabled={!question.trim() || isSearching}><ArrowUp size={19} /></button></form>
    </section>
  </main>;
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
