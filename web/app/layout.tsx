import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "agentmesh · polyglot agent mesh",
  description: "Drag-and-drop agent workflows across a TypeScript / Go / Python / Rust mesh.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
