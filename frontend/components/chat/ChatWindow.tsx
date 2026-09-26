"use client";

import { FormEvent, useState } from "react";
import { ExternalLink, Sparkles } from "lucide-react";
import { askQuestion, type AskResponse } from "../../lib/api/videos";

export function ChatWindow() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = question.trim();
    if (!query || isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      setResponse(await askQuestion(query));
    } catch (requestError) {
      setResponse(null);
      setError(requestError instanceof Error ? requestError.message : "We could not answer that question.");
    } finally {
      setIsLoading(false);
    }
  }

  return <div className="mx-auto flex min-h-[calc(100vh-68px)] max-w-5xl flex-col px-4 py-7 sm:px-8 sm:py-10">
    <div className="mb-8"><p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-[#e32626]">Ask about this playlist</p><h1 className="text-3xl font-bold tracking-tight">Ideas worth revisiting</h1><p className="mt-2 text-sm text-[#60646c]">AskTube conversation</p></div>
    <div className="flex-1 space-y-8">
      {response && <><div className="ml-auto max-w-xl rounded-2xl rounded-tr-sm bg-[#16181d] px-5 py-4 text-sm leading-6 text-white">{response.query}</div><div className="max-w-3xl"><div className="mb-3 flex items-center gap-2 text-sm font-bold"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#fff0f0] text-[#e32626]"><Sparkles size={15} /></span> AskTube</div><div className="text-base leading-7 text-[#30343b]">{response.answer}</div><SourceList sources={response.sources} /></div></>}
      {error && <p role="alert" className="rounded-xl border border-[#f3c4c4] bg-[#fff5f5] px-4 py-3 text-sm text-[#a51d2d]">{error}</p>}
      {!response && !error && <p className="text-sm text-[#60646c]">Ask a question about the indexed transcripts.</p>}
    </div>
    <form onSubmit={handleSubmit} className="mt-10 flex gap-2 rounded-2xl border border-[#d7d9de] bg-white p-2 shadow-[0_8px_30px_rgba(22,24,29,0.04)]"><label htmlFor="question" className="sr-only">Ask a question</label><input id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about this playlist" className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm outline-none" disabled={isLoading} /><button type="submit" disabled={!question.trim() || isLoading} className="rounded-xl bg-[#e32626] px-5 py-3 text-sm font-bold text-white hover:bg-[#c91e24] disabled:cursor-not-allowed disabled:opacity-50">{isLoading ? "Thinking..." : "Ask"}</button></form>
  </div>;
}

function SourceList({ sources }: { sources: AskResponse["sources"] }) {
  if (!sources.length) return <p className="mt-6 text-sm text-[#60646c]">No transcript sources matched this question.</p>;
  return <section className="mt-6" aria-labelledby="sources-title"><h2 id="sources-title" className="mb-3 text-xs font-bold uppercase tracking-[0.15em] text-[#9297a1]">Sources</h2><div className="space-y-2">{sources.map((source) => <article key={source.chunk_id} className="rounded-xl border border-[#e5e7eb] bg-white p-3"><div className="flex items-start justify-between gap-3"><div><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(source.video_id)}&t=${Math.floor(source.start_time)}s`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-bold text-[#d91f26] hover:underline">Video {source.video_id} <ExternalLink size={13} /></a><p className="mt-1 text-xs text-[#60646c]">{formatTimestamp(source.start_time)} - {formatTimestamp(source.end_time)}</p></div><span className="text-xs text-[#9297a1]">{Math.round(source.score * 100)}% match</span></div><p className="mt-2 text-sm leading-6 text-[#60646c]">{source.text}</p></article>)}</div></section>;
}

function formatTimestamp(seconds: number) {
  const totalSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  return `${minutes}:${String(totalSeconds % 60).padStart(2, "0")}`;
}
