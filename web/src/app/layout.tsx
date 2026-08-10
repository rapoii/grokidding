import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme-provider";
import { Sidebar } from "@/components/sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Grokidding",
  description: "Grok account farming panel",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        style={{
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", var(--font-geist-sans), system-ui, sans-serif',
        }}
      >
        <ThemeProvider>
          <div className="relative flex min-h-[100dvh]">
            {/* Ambient orbs for glass vibrancy */}
            <div
              className="pointer-events-none fixed inset-0 z-0"
              aria-hidden
            >
              <div
                className="absolute -left-20 top-0 h-[600px] w-[600px] rounded-full opacity-[0.25]"
                style={{ background: "radial-gradient(circle, #0071e3, transparent 70%)" }}
              />
              <div
                className="absolute right-0 top-1/3 h-[500px] w-[500px] rounded-full opacity-[0.20]"
                style={{ background: "radial-gradient(circle, #5e5ce6, transparent 70%)" }}
              />
              <div
                className="absolute bottom-0 left-1/3 h-[400px] w-[400px] rounded-full opacity-[0.18]"
                style={{ background: "radial-gradient(circle, #bf5af2, transparent 70%)" }}
              />
            </div>
            <div className="relative z-10 flex min-h-[100dvh] w-full">
              <Sidebar />
              <main className="flex-1 min-w-0">{children}</main>
            </div>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
