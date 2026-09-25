export default function Home() {
  return (
    <main className="min-h-screen bg-[#f4f1ea] text-[#1d2925]">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-8 sm:px-10 lg:px-16">
        <header className="flex items-center justify-between border-b border-[#1d2925]/15 pb-5">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e35f3f] text-sm font-bold text-white">A</span>
            <span className="text-lg font-semibold tracking-tight">AskTube</span>
          </div>
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-[#1d2925]/60">Playlist intelligence</span>
        </header>

        <section className="grid flex-1 items-center gap-14 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
          <div>
            <p className="mb-6 text-sm font-semibold uppercase tracking-[0.2em] text-[#e35f3f]">A clearer way to watch</p>
            <h1 className="max-w-3xl text-5xl font-semibold leading-[0.98] tracking-[-0.04em] sm:text-7xl">
              Turn a playlist into a conversation.
            </h1>
            <p className="mt-8 max-w-xl text-lg leading-8 text-[#1d2925]/70">
              AskTube will help you explore the ideas, stories, and lessons inside any YouTube playlist, whatever the subject.
            </p>
          </div>

          <div className="relative">
            <div className="absolute -inset-4 rounded-[2rem] border border-[#e35f3f]/20" />
            <div className="relative rounded-[1.5rem] bg-[#1d2925] p-7 text-[#f4f1ea] shadow-2xl shadow-[#1d2925]/15 sm:p-10">
              <div className="mb-16 flex items-center justify-between">
                <span className="text-sm font-medium text-[#f4f1ea]/60">Start with a playlist</span>
                <span className="h-2 w-2 rounded-full bg-[#e35f3f]" />
              </div>
              <label htmlFor="playlist-url" className="mb-3 block text-2xl font-medium tracking-tight">
                YouTube playlist URL
              </label>
              <input
                id="playlist-url"
                type="url"
                placeholder="Paste a playlist link here"
                disabled
                className="w-full border-b border-[#f4f1ea]/30 bg-transparent py-4 text-base text-[#f4f1ea] outline-none placeholder:text-[#f4f1ea]/35"
              />
              <button type="button" disabled className="mt-8 w-full rounded-full bg-[#e35f3f] px-5 py-4 text-sm font-semibold text-white opacity-60">
                Coming in the next step
              </button>
              <p className="mt-5 text-xs leading-5 text-[#f4f1ea]/45">Playlist processing is not enabled in this foundation release.</p>
            </div>
          </div>
        </section>

        <footer className="border-t border-[#1d2925]/15 pt-5 text-xs text-[#1d2925]/50">
          Built for curious minds, across every subject.
        </footer>
      </div>
    </main>
  );
}
