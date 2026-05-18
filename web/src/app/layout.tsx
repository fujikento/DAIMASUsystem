import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import AdminKeyGate from "@/components/AdminKeyGate";
import ConditionalShell from "@/components/ConditionalShell";

const inter = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Immersive Dining | 投影制御システム",
  description: "イマーシブダイニング プロジェクションマッピング管理システム",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className="dark">
      <body
        className={`${inter.variable} font-sans antialiased bg-[#080f1a] text-white min-h-screen`}
      >
        <AdminKeyGate />
        <ConditionalShell>{children}</ConditionalShell>
      </body>
    </html>
  );
}
