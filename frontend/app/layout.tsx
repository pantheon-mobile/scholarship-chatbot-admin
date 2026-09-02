import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/auth/AuthProvider";

export const metadata: Metadata = {
  title: "Scholarship Chatbot Admin",
  description: "Admin frontend for the scholarship chatbot",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body><AuthProvider>{children}</AuthProvider></body>
    </html>
  );
}
