import { useState } from "react";
import { ArrowRight, Link2 } from "lucide-react";
import { parseYouTubePlaylistUrl, type ValidatedPlaylist } from "../../lib/youtube/playlistUrl";

type PlaylistInputProps = {
  value: string;
  onChange: (value: string) => void;
  onPlaylistValidated: (playlist: ValidatedPlaylist) => void;
};

type ValidationState =
  | { status: "empty" }
  | { status: "validating" }
  | { status: "invalid"; error: string }
  | { status: "valid"; playlist: ValidatedPlaylist };

export function PlaylistInput({ value, onChange, onPlaylistValidated }: PlaylistInputProps) {
  const [validation, setValidation] = useState<ValidationState>({ status: "empty" });

  function handleChange(nextValue: string) {
    onChange(nextValue);
    setValidation({ status: "empty" });
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (validation.status === "validating" || !value.trim()) return;

    setValidation({ status: "validating" });
    const result = parseYouTubePlaylistUrl(value);
    if (!result.valid) {
      setValidation({ status: "invalid", error: result.error });
      return;
    }

    setValidation({ status: "valid", playlist: result });
    onPlaylistValidated(result);
  }

  const message = validation.status === "invalid"
    ? validation.error
    : validation.status === "valid"
      ? "Playlist URL recognized"
      : null;

  return <form onSubmit={handleSubmit} className="max-w-3xl rounded-2xl border border-[#e5e7eb] bg-white p-2 shadow-[0_8px_30px_rgba(22,24,29,0.04)]" noValidate><div className="flex flex-col gap-2 sm:flex-row"><label htmlFor="playlist-url" className="sr-only">YouTube playlist URL</label><div className="flex min-w-0 flex-1 items-center gap-3 rounded-xl bg-[#f5f6f7] px-4"><Link2 size={18} className="shrink-0 text-[#9297a1]" /><input id="playlist-url" type="text" value={value} onChange={(event) => handleChange(event.target.value)} placeholder="Paste a YouTube playlist URL" className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none placeholder:text-[#9297a1]" aria-invalid={validation.status === "invalid"} aria-describedby={message ? "playlist-url-message" : undefined} /></div><button type="submit" className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#e32626] px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-[#c91e24] disabled:cursor-not-allowed disabled:opacity-50" disabled={!value.trim() || validation.status === "validating"}>{validation.status === "validating" ? "Checking..." : "Load playlist"} <ArrowRight size={17} /></button></div>{message && <p id="playlist-url-message" role={validation.status === "invalid" ? "alert" : "status"} className={`px-2 pt-2 text-sm ${validation.status === "invalid" ? "text-[#c91e24]" : "text-[#18794e]"}`}>{message}</p>}</form>;
}