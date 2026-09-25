import { Clock3, House, Library, ListVideo, X } from "lucide-react";

const items = [{ id: "home", label: "Home", icon: House }, { id: "playlist", label: "My playlists", icon: ListVideo }, { id: "recent", label: "Recent", icon: Clock3 }, { id: "history", label: "History", icon: Library }];

export function Sidebar({ activeView, onNavigate, open, onClose }: { activeView: string; onNavigate: (view: string) => void; open: boolean; onClose: () => void }) {
  return <><aside className={`${open ? "translate-x-0" : "-translate-x-full"} fixed inset-y-[68px] left-0 z-20 w-60 border-r border-[#e5e7eb] bg-white p-3 transition-transform lg:sticky lg:top-[68px] lg:block lg:h-[calc(100vh-68px)] lg:translate-x-0`}>
    <div className="mb-4 flex items-center justify-between px-3 pt-2 lg:hidden"><span className="text-xs font-bold uppercase tracking-[0.15em] text-[#9297a1]">Menu</span><button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-[#f2f3f5]" aria-label="Close navigation"><X size={18} /></button></div>
    <nav aria-label="Primary navigation" className="space-y-1">{items.map(({ id, label, icon: Icon }) => <button type="button" key={id} onClick={() => { onNavigate(id); onClose(); }} className={`flex w-full items-center gap-4 rounded-xl px-4 py-3 text-sm font-semibold transition-colors ${activeView === id ? "bg-[#fff0f0] text-[#d91f26]" : "text-[#60646c] hover:bg-[#f5f6f7] hover:text-[#16181d]"}`}><Icon size={19} strokeWidth={activeView === id ? 2.5 : 2} /><span>{label}</span></button>)}</nav>
    <div className="mt-8 border-t border-[#f0f1f3] px-4 pt-6 text-xs leading-5 text-[#9297a1]">Your playlist workspace. Built for watching closely.</div>
  </aside>{open && <button type="button" className="fixed inset-0 z-10 bg-black/20 lg:hidden" onClick={onClose} aria-label="Close navigation overlay" />}</>;
}