import Image from "next/image";
import { Bell, Menu, Search, UserRound } from "lucide-react";

export function Header({ onMenu }: { onMenu: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-[68px] items-center gap-3 border-b border-[#e5e7eb] bg-white px-4 sm:px-6">
      <button type="button" onClick={onMenu} className="rounded-full p-2 text-[#60646c] hover:bg-[#f2f3f5] lg:hidden" aria-label="Open navigation"><Menu size={21} /></button>
      <a href="#" className="flex w-[145px] shrink-0 items-center" aria-label="AskTube home"><Image src="/assets/AskTubelogo.png" alt="AskTube" width={145} height={68} className="h-auto max-h-12 w-auto object-contain object-left" priority /></a>
      <div className="mx-auto hidden w-full max-w-xl items-center md:flex">
        <label htmlFor="header-search" className="sr-only">Search AskTube</label>
        <div className="flex h-10 w-full items-center rounded-full border border-[#d7d9de] bg-[#f8f8f8] pl-4 focus-within:border-[#9a9da5] focus-within:bg-white"><input id="header-search" className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#9297a1]" placeholder="Search your playlists" /><button type="button" className="flex h-10 w-12 items-center justify-center rounded-r-full border-l border-[#e5e7eb] text-[#60646c] hover:bg-[#f0f1f3]" aria-label="Search"><Search size={18} /></button></div>
      </div>
      <div className="ml-auto flex items-center gap-1"><button type="button" className="hidden rounded-full p-2 text-[#60646c] hover:bg-[#f2f3f5] sm:block" aria-label="Notifications"><Bell size={19} /></button><button type="button" className="rounded-full border border-[#e5e7eb] p-2 text-[#60646c] hover:bg-[#f2f3f5]" aria-label="Profile"><UserRound size={18} /></button></div>
    </header>
  );
}