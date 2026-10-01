import Image from "next/image";
import { Menu, UserRound } from "lucide-react";

export function Header({ onMenu }: { onMenu: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-[68px] items-center gap-3 border-b border-[#e5e7eb] bg-white px-4 sm:px-6">
      <button type="button" onClick={onMenu} className="rounded-full p-2 text-[#60646c] hover:bg-[#f2f3f5] lg:hidden" aria-label="Open navigation"><Menu size={21} /></button>
      <a href="#" className="flex w-[145px] shrink-0 items-center" aria-label="AskTube home"><Image src="/assets/AskTubelogo.png" alt="AskTube" width={145} height={68} className="h-auto max-h-12 w-auto object-contain object-left" priority /></a>
      <div className="ml-auto flex items-center gap-1"><button type="button" className="rounded-full border border-[#e5e7eb] p-2 text-[#60646c] hover:bg-[#f2f3f5]" aria-label="Profile"><UserRound size={18} /></button></div>
    </header>
  );
}