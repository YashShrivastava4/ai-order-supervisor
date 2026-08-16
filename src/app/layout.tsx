import type { Metadata } from "next";
import "./globals.css";
import AppShell from "../components/app-shell";

export const metadata: Metadata = {
  title: "Order Supervisor",
  description: "AI order supervision dashboard",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full bg-[#f3efe8] text-[#1d2a2a]">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
