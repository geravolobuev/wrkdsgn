import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Design Jobs",
  description: "Clean feed of design vacancies from Telegram channels"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-line bg-white">
          <div className="container-page flex items-center justify-between py-4">
            <a href="/" className="text-lg font-semibold tracking-tight">
              Design Jobs
            </a>
            <nav className="text-sm text-soft">
              <a href="/jobs" className="link">
                Jobs
              </a>
            </nav>
          </div>
        </header>
        <main className="container-page py-8">{children}</main>
      </body>
    </html>
  );
}
