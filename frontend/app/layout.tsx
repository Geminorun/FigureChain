import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FigureChain 人物链查找",
  description: "搜索历史人物之间可回溯证据的人物链。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
