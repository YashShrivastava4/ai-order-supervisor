"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function NavItem({ href, label, active = false, icon }: { href: string; label: string; active?: boolean; icon: React.ReactNode }) {
    return (
        <Link
            href={href}
            className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition ${active ? "bg-[#2b3b46] text-white shadow-inner" : "text-[#d8dfe5] hover:bg-[#1d2a33]"
                }`}
        >
            <span className={`flex h-5 w-5 items-center justify-center ${active ? "text-white" : "text-[#c8d0d6]"}`}>
                {icon}
            </span>
            <span>{label}</span>
        </Link>
    );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();

    const isActive = (href: string) => {
        if (href === "/") {
            return pathname === "/" || pathname.startsWith("/runs");
        }

        if (pathname === href) return true;
        return pathname.startsWith(`${href}/`);
    };

    return (
        <div className="min-h-screen bg-[#f3efe8]">
            <aside className="fixed inset-y-0 left-0 z-20 hidden w-[236px] shrink-0 flex-col border-r border-[#1f2a32] bg-[#111c25] text-white lg:flex">
                <div className="px-5 pb-5 pt-6">
                    <div className="flex items-center gap-3">
                        <div className="relative flex h-9 w-9 items-center justify-center rounded-full border border-[#d5dfe8] bg-[#1b2730]">
                            <div className="h-4 w-4 rounded-full border border-[#d5dfe8]" />
                            <div className="absolute h-[2px] w-5 rotate-45 rounded-full bg-[#d5dfe8]" />
                        </div>
                        <div className="leading-none">
                            <div className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#d7dfe6]">Order</div>
                            <div className="mt-1 text-[13px] font-medium tracking-[0.18em] text-[#eff7fb]">Supervisor</div>
                        </div>
                    </div>
                </div>

                <nav className="flex-1 space-y-1.5 px-3 pt-2">
                    <NavItem href="/" label="Runs" active={isActive("/")} icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4"><path d="M4 6.75A2.75 2.75 0 0 1 6.75 4h10.5A2.75 2.75 0 0 1 20 6.75v10.5A2.75 2.75 0 0 1 17.25 20H6.75A2.75 2.75 0 0 1 4 17.25V6.75Z" /><path d="M8 9h8M8 12h8M8 15h5" strokeLinecap="round" /></svg>} />
                    <NavItem href="/supervisors" label="Supervisors" active={isActive("/supervisors")} icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4"><circle cx="12" cy="7.5" r="3.25" /><path d="M5 19c1.2-3.2 4.1-4.5 7-4.5s5.8 1.3 7 4.5" strokeLinecap="round" /></svg>} />
                    <NavItem href="/new-run" label="New Run" active={isActive("/new-run")} icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4"><path d="M12 5v14M5 12h14" strokeLinecap="round" /></svg>} />
                </nav>

                <div className="border-t border-[#212f39] p-4">
                    <div className="mb-3 flex items-center justify-between text-[11px] font-medium uppercase tracking-[0.12em] text-[#9aa8b0]">
                        <span>System status</span>
                        <span className="rounded-full bg-[#1b2d35] px-2 py-0.5 text-[9px] text-[#d0ffe0]">All systems normal</span>
                    </div>
                    <div className="h-10 overflow-hidden rounded-md bg-[#101a21] p-2">
                        <div className="flex h-full items-end gap-[2px]">
                            {[18, 26, 20, 30, 24, 28, 34, 32, 38, 30, 36, 45, 40, 52, 48, 46].map((value, index) => (
                                <span key={index} className="flex-1 rounded-sm bg-gradient-to-t from-[#aaf0bf] to-[#7ce4a4]" style={{ height: `${Math.max(18, value)}%` }} />
                            ))}
                        </div>
                    </div>
                    <div className="mt-5 flex items-center justify-between rounded-xl border border-[#2a3b46] bg-[#111c25] p-2.5">
                        <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#1d3d34] text-[11px] font-semibold text-[#98ebbf]">OS</div>
                            <div className="text-[12px] text-[#dfeaf0]">
                                <div className="font-medium">operator</div>
                                <div className="text-[#9aa8b0]">admin</div>
                            </div>
                        </div>
                    </div>
                </div>
            </aside>

            <main className="min-h-screen w-full lg:pl-[236px]">
                <div className="h-screen overflow-y-auto">
                    <div className="mx-auto w-full max-w-[1500px] px-4 py-5 md:px-6 xl:px-7">{children}</div>
                </div>
            </main>
        </div>
    );
}
