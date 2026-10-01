import Image from "next/image";
import { useState } from "react";
import { ArrowRight, Link2 } from "lucide-react";
import { parseYouTubePlaylistUrl, type ValidatedPlaylist } from "../../lib/youtube/playlistUrl";

type PlaylistInputProps = {
  value: string;
  onChange: (value: string) => void;
  onPlaylistValidated: (playlist: ValidatedPlaylist) => Promise<void>;
  isProcessingPlaylist?: boolean;
  processingMessage?: string;
};

type ValidationState =
  | { status: "empty" }
  | { status: "validating" }
  | { status: "invalid"; error: string }
  | { status: "error"; error: string }
  | { status: "valid"; playlist: ValidatedPlaylist };

export function PlaylistInput({ value, onChange, onPlaylistValidated, isProcessingPlaylist = false, processingMessage = "Reading playlist..." }: PlaylistInputProps) {
  const [validation, setValidation] = useState<ValidationState>({ status: "empty" });

  function handleChange(nextValue: string) {
    onChange(nextValue);
    setValidation({ status: "empty" });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (validation.status === "validating" || isProcessingPlaylist || !value.trim()) return;

    setValidation({ status: "validating" });
    const result = parseYouTubePlaylistUrl(value);
    if (!result.valid) {
      setValidation({ status: "invalid", error: result.error });
      return;
    }

    try {
      await onPlaylistValidated(result);
      setValidation({ status: "valid", playlist: result });
    } catch (error) {
      setValidation({ status: "error", error: "We couldn't process this playlist. Try again or check the playlist link." });
    }
  }

  const message = validation.status === "invalid"
    ? validation.error
    : validation.status === "error"
      ? validation.error
    : validation.status === "valid"
      ? "Playlist URL recognized"
      : null;

  if (isProcessingPlaylist) {
    return (
      <div className="flex max-w-3xl flex-col items-center gap-4 rounded-2xl border border-[#e3e6ea] bg-white px-6 py-8 text-center shadow-[0_8px_30px_rgba(32,36,43,0.04)]" role="status" aria-live="polite">
        <Image
          src="/assets/Scan.gif"
          alt="Scanning playlist animation"
          width={160}
          height={160}
          unoptimized
          priority
        />
        <p className="text-sm font-semibold text-[#30343b]">{processingMessage}</p>
        <p className="max-w-sm text-xs leading-5 text-[#9297a1]">AskTube is studying the playlist so your answers can stay grounded in its videos.</p>
      </div>
    );
  }

  return <form onSubmit={handleSubmit} className="max-w-3xl rounded-2xl border border-[#e3e6ea] bg-white p-2 shadow-[0_8px_30px_rgba(32,36,43,0.04)]" noValidate><div className="flex flex-col gap-2 sm:flex-row"><label htmlFor="playlist-url" className="sr-only">YouTube playlist URL</label><div className="flex min-w-0 flex-1 items-center gap-3 rounded-xl bg-[#f1f3f6] px-4"><Link2 size={18} className="shrink-0 text-[#9297a1]" /><input id="playlist-url" type="text" value={value} onChange={(event) => handleChange(event.target.value)} placeholder="Paste a YouTube playlist URL..." className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none placeholder:text-[#9297a1]" aria-invalid={validation.status === "invalid" || validation.status === "error"} aria-describedby={message ? "playlist-url-message" : undefined} /></div><button type="submit" className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#3468f5] px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-[#2858d9] disabled:cursor-not-allowed disabled:opacity-50" disabled={!value.trim() || validation.status === "validating"}>{validation.status === "validating" ? "Loading..." : "Load Playlist"} <ArrowRight size={17} /></button></div>{message && <p id="playlist-url-message" role={validation.status === "invalid" || validation.status === "error" ? "alert" : "status"} className={`px-2 pt-2 text-sm ${validation.status === "invalid" || validation.status === "error" ? "text-[#a13939]" : "text-[#238b5a]"}`}>{message}</p>}</form>;
}