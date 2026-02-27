import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

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
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 pl-[260px]">
            <div className="max-w-[1400px] mx-auto px-8 py-8">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
