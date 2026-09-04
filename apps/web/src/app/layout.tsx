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
  icons: { icon: "/clearisbg.png", apple: "/clearisbg.png" },
  openGraph: {
    title: "Clearis — School Management Platform",
    description: "Everything your school needs. One clear platform. Manage students, teachers, results, finances, and more — all in one place.",
    url: "https://clearis.site",
    siteName: "Clearis",
    images: [
      {
        url: "/clearisbg.png",
        width: 512,
        height: 512,
        alt: "Clearis Logo",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Clearis — School Management Platform",
    description: "Everything your school needs. One clear platform.",
    images: ["/clearisbg.png"],
  },
  metadataBase: new URL("https://clearis.site"),
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
