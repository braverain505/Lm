import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Providers } from "@/providers/providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Clearis — School Management Platform",
  description: "Everything your school needs. One clear platform.",
  icons: { icon: "/clearis.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} ${inter.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
