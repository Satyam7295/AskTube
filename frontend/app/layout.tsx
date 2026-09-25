import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AskTube",
  description: "Ask questions about the ideas inside any YouTube playlist.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
