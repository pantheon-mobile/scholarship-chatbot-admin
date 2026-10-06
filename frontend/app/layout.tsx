import { connection } from "next/server";
import { siteMetadata } from "@/lib/siteMetadata";
import "./globals.css";
import { AuthProvider } from "@/components/auth/AuthProvider";

export async function generateMetadata() {
  // Read the deployed container's settings, not the image build environment.
  await connection();
  return siteMetadata();
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body><AuthProvider>{children}</AuthProvider></body>
    </html>
  );
}
