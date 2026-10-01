"use client";

import { FormEvent, useState } from "react";
import Image from "next/image";
import { ExternalLink, Eye, Sparkles, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { askQuestion, type AskResponse } from "../../lib/api/videos";
import type { PlaylistData } from "../../lib/api/playlists";

type ChatWindowProps = { playlist: PlaylistData };
type ConversationTurn = { query: string; response: AskResponse };

const suggestions = [
  "Explain binary search in simple terms.",
  "Where is dynamic programming explained?",
  "What is the difference between stack and queue?",
  "Which video explains recursion?",
  "Summarize the videos about graphs.",
];

export function ChatWindow({ playlist }: ChatWindowProps) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

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
      const response = await askQuestion(query);
      setTurns((current) => [...current, { query, response }]);
    } catch {
      setError("I couldn't search the playlist right now. Please try again.");
    } finally {
      setIsSearching(false);
    }
  }

  return <div className="relative mx-auto flex min-h-[calc(100vh-68px)] max-w-5xl flex-col px-4 py-7 sm:px-8 sm:py-10">
    <div className="mb-8 flex items-start justify-between gap-4">
      <div><p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-[#e32626]">Knowledge base ready</p><h1 className="text-3xl font-bold tracking-tight">What would you like to learn?</h1><p className="mt-2 text-sm text-[#60646c]">{playlist.total_videos} {playlist.total_videos === 1 ? "video" : "videos"} processed. Ask anything about this playlist.</p></div>
      <button type="button" onClick={() => setShowDetails(true)} className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-[#d7d9de] bg-white px-3 py-2 text-sm font-semibold text-[#60646c] hover:border-[#9297a1] hover:text-[#16181d]"><Eye size={16} /><span className="hidden sm:inline">View playlist details</span><span className="sm:hidden">Details</span></button>
    </div>
    <div className="mb-8 rounded-xl border border-[#cde8d9] bg-[#f2fbf5] px-4 py-3 text-sm text-[#21663f]"><strong>Your playlist is ready.</strong> I&apos;ve processed the content and I&apos;m ready to answer questions about it.</div>
    <div className="flex-1 space-y-8">
      {turns.length === 0 && !isSearching && <section aria-labelledby="suggestions-title"><div className="mb-4 flex items-center gap-2 text-sm font-semibold text-[#60646c]"><Sparkles size={16} className="text-[#e32626]" /><h2 id="suggestions-title">Try asking</h2></div><div className="grid gap-2 sm:grid-cols-2">{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => void submitQuestion(suggestion)} className="rounded-xl border border-[#e5e7eb] bg-white px-4 py-3 text-left text-sm leading-5 text-[#30343b] transition-colors hover:border-[#e32626] hover:bg-[#fffafa]">{suggestion}</button>)}</div></section>}
      {turns.map(({ query, response }) => <article key={`${query}-${response.answer.slice(0, 20)}`} className="space-y-5"><div className="ml-auto max-w-xl rounded-2xl rounded-tr-sm bg-[#16181d] px-5 py-4 text-sm leading-6 text-white">{query}</div><div className="max-w-3xl"><div className="mb-3 flex items-center gap-2 text-sm font-bold"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#fff0f0] text-[#e32626]"><Sparkles size={15} /></span> AskTube</div><div className="text-base leading-7 text-[#30343b] [&_a]:font-semibold [&_a]:text-[#d91f26] [&_a:hover]:underline [&_h1]:mb-4 [&_h1]:mt-6 [&_h1]:text-2xl [&_h1]:font-bold [&_h2]:mb-3 [&_h2]:mt-6 [&_h2]:text-xl [&_h2]:font-bold [&_li]:my-1 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:my-3 [&_strong]:font-bold [&_ul]:my-4 [&_ul]:list-disc [&_ul]:pl-6"><ReactMarkdown>{response.answer}</ReactMarkdown></div><SourceList sources={response.sources} playlist={playlist} /></div></article>)}
      {isSearching && <div className="flex items-center gap-3 rounded-xl border border-[#e5e7eb] bg-white px-4 py-3 text-sm font-medium text-[#60646c]"><Image src="/assets/Searching.gif" alt="Searching playlist animation" width={56} height={56} unoptimized priority /> Finding the relevant explanation...</div>}
      {error && <div role="alert" className="flex items-center justify-between gap-4 rounded-xl border border-[#f3c4c4] bg-[#fff5f5] px-4 py-3 text-sm text-[#a51d2d]"><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error"><X size={16} /></button></div>}
    </div>
    <form onSubmit={handleSubmit} className="sticky bottom-4 mt-10 flex gap-2 rounded-2xl border border-[#d7d9de] bg-white p-2 shadow-[0_8px_30px_rgba(22,24,29,0.08)]"><label htmlFor="question" className="sr-only">Ask anything about this playlist</label><input id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask anything about this playlist..." className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm outline-none" disabled={isSearching} /><button type="submit" disabled={!question.trim() || isSearching} className="rounded-xl bg-[#e32626] px-5 py-3 text-sm font-bold text-white hover:bg-[#c91e24] disabled:cursor-not-allowed disabled:opacity-50">{isSearching ? "Searching..." : "Ask AskTube"}</button></form>
    {showDetails && <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-y-auto border-l border-[#e5e7eb] bg-white p-6 shadow-2xl" aria-label="Playlist details"><div className="mb-8 flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.15em] text-[#e32626]">Knowledge source</p><h2 className="mt-2 text-xl font-bold">{playlist.playlist.title}</h2></div><button type="button" onClick={() => setShowDetails(false)} aria-label="Close playlist details" className="rounded-full p-2 text-[#60646c] hover:bg-[#f5f6f7]"><X size={20} /></button></div><p className="mb-6 text-sm leading-6 text-[#60646c]">{playlist.playlist.description || "This playlist is loaded as the knowledge source for your conversation."}</p><div className="border-t border-[#f0f1f3] pt-5 text-sm text-[#60646c]"><strong className="text-[#16181d]">{playlist.videos.length} videos</strong> available in this knowledge base.</div></aside>}
  </div>;
}

function SourceList({ sources, playlist }: { sources: AskResponse["sources"]; playlist: PlaylistData }) {
  if (!sources.length) return null;
  return <section className="mt-6" aria-labelledby="sources-title"><h2 id="sources-title" className="mb-3 text-xs font-bold uppercase tracking-[0.15em] text-[#9297a1]">Found in</h2><div className="space-y-2">{sources.map((source) => { const video = playlist.videos.find((item) => item.video_id === source.video_id); const timestamp = Math.floor(source.start_time); return <article key={source.chunk_id} className="rounded-xl border border-[#e5e7eb] bg-white p-4"><div className="flex items-start justify-between gap-3"><div><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(source.video_id)}&t=${timestamp}s`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-bold text-[#d91f26] hover:underline">{video?.title ?? "Relevant video"} <ExternalLink size={13} /></a><p className="mt-1 text-xs text-[#60646c]">{formatTimestamp(source.start_time)} in the playlist</p></div><span className="text-xs text-[#9297a1]">{Math.round(source.score * 100)}% match</span></div><p className="mt-2 text-sm leading-6 text-[#60646c]">{source.text}</p></article>; })}</div></section>;
}

function formatTimestamp(seconds: number) { const totalSeconds = Math.max(0, Math.floor(seconds)); return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, "0")}`; }