"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { formatTimeOnly, normalizeUtcTimestamp } from "@/lib/format-time";

interface Run {
  id: string;
  order_id: string;
  supervisor_id: string;
  status: string;
  memory_summary: string | null;
  next_wakeup_at: string | null;
  created_at: string;
  updated_at: string;
}

const statusStyles: Record<string, { pill: string; label: string }> = {
  running: { pill: "bg-[#dfeee3] text-[#2d6d4b]", label: "Running" },
  sleeping: { pill: "bg-[#f8eac7] text-[#a06b1f]", label: "Sleeping" },
  paused: { pill: "bg-[#f4e7d1] text-[#9b6e2f]", label: "Paused" },
  completed: { pill: "bg-[#dfe9ed] text-[#3d5f71]", label: "Completed" },
  terminated: { pill: "bg-[#f8dfe1] text-[#bc3d4c]", label: "Terminated" },
};

const formatMemorySnippet = (value: string | null) => {
  if (!value) return "No memory summary available.";
  return value.length > 110 ? `${value.slice(0, 107).trim()}...` : value;
};

// Purely a display computation: the backend status stays "running" while asleep,
// so we show "Sleeping" whenever there's a real future wake-up time.
const getDisplayStatus = (status: string, nextWakeupAt: string | null) => {
  if (status !== "running" || !nextWakeupAt) return status;
  const normalized = normalizeUtcTimestamp(nextWakeupAt);
  const wakeupTime = normalized ? new Date(normalized).getTime() : NaN;
  if (!Number.isNaN(wakeupTime) && wakeupTime > Date.now()) return "sleeping";
  return status;
};

export default function RunsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const fetchRuns = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/runs");
      if (!res.ok) throw new Error("Failed to fetch runs");
      const data = await res.json();
      setRuns(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading runs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchRuns();
    const interval = setInterval(() => {
      void fetchRuns();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const statusOptions = useMemo(() => {
    return Array.from(new Set(runs.map((run) => run.status).filter(Boolean))).sort();
  }, [runs]);

  const filteredRuns = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return runs.filter((run) => {
      const matchesQuery = !query || run.order_id.toLowerCase().includes(query);
      const matchesStatus = statusFilter === "all" || run.status === statusFilter;
      return matchesQuery && matchesStatus;
    });
  }, [runs, searchQuery, statusFilter]);

  useEffect(() => {
    if (!filteredRuns.length) {
      setSelectedId(null);
      return;
    }

    if (!selectedId || !filteredRuns.some((run) => run.id === selectedId)) {
      setSelectedId(filteredRuns[0].id);
    }
  }, [filteredRuns, selectedId]);

  const selectedRun = useMemo(
    () => filteredRuns.find((run) => run.id === selectedId) ?? null,
    [filteredRuns, selectedId]
  );

  const handleSelectRun = (runId: string) => {
    setSelectedId(runId);
    router.push(`/runs/${runId}`);
  };

  return (
    <div className="mx-auto w-full max-w-[1480px]">
      <div className="mb-7 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[32px] font-bold tracking-[-0.05em] text-[#1b252b]">Runs</h1>
          <p className="mt-1 text-[14px] text-[#6d726d]">Live overview of all order runs</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-[#f0c5c8] bg-[#fdf2f3] px-4 py-3 text-sm text-[#b24d59]">
          {error}
        </div>
      )}

      <div className="grid h-[calc(100vh-170px)] min-h-[620px] gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="flex min-h-0 flex-col overflow-hidden rounded-[20px] border border-[#d9d0c7] bg-[#f8f5f1] p-3 shadow-[var(--shadow)]">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row">
            <div className="flex w-full items-center gap-3 rounded-xl border border-[#cfc8c1] bg-[#f4f0eb] px-3 py-2.5 shadow-sm">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className="h-4 w-4 text-[#7d807a]">
                <circle cx="11" cy="11" r="6" />
                <path d="M16 16l4 4" strokeLinecap="round" />
              </svg>
              <input
                aria-label="Search by order id"
                placeholder="Search by order id..."
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                className="w-full border-0 bg-transparent text-[14px] text-[#28363c] placeholder:text-[#7d807a] focus:outline-none"
              />
            </div>

            <div className="relative min-w-[170px]">
              <select
                aria-label="Filter by status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="w-full appearance-none rounded-xl border border-[#cfc8c1] bg-[#f4f0eb] px-3 py-2.5 pr-9 text-[14px] text-[#2b343d] shadow-sm outline-none"
              >
                <option value="all">All Status</option>
                {statusOptions.map((status) => (
                  <option key={status} value={status}>
                    {statusStyles[status]?.label ?? status}
                  </option>
                ))}
              </select>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#4a5a63]">
                <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            <div className="space-y-3">
              {loading ? (
                <div className="rounded-2xl border border-[#ddd4cc] bg-[#f6f1ec] p-6 text-center text-[#68716c]">
                  Loading runs...
                </div>
              ) : filteredRuns.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-[#d2c8c0] bg-[#f8f5f1] p-8 text-center text-[#586663]">
                  <p className="text-base font-medium text-[#243237]">No matching runs</p>
                  <p className="mt-2 text-sm">Try a different order ID or status filter.</p>
                </div>
              ) : (
                filteredRuns.map((run) => {
                  const isSelected = selectedRun?.id === run.id;
                  const displayStatus = getDisplayStatus(run.status, run.next_wakeup_at);
                  const statusStyle = statusStyles[displayStatus] ?? { pill: "bg-[#eceae7] text-[#46515a]", label: displayStatus };

                  return (
                    <button
                      key={run.id}
                      type="button"
                      onClick={() => handleSelectRun(run.id)}
                      className={`flex w-full items-center justify-between gap-4 rounded-2xl border px-4 py-4 text-left transition ${isSelected
                        ? "border-[#cfc4b9] bg-[#f3efea] shadow-[0_2px_8px_rgba(10,18,25,0.04)]"
                        : "border-[#d7d0c8] bg-[#f6f2ee] hover:bg-[#f1ece7]"
                        }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-3">
                          <div className="font-mono text-[14px] font-semibold tracking-[0.04em] text-[#1d272d]">{run.order_id}</div>
                          <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusStyle.pill}`}>
                            {statusStyle.label}
                          </span>
                        </div>
                        <p className="mt-2 text-[12px] leading-5 text-[#5a6767]">{formatMemorySnippet(run.memory_summary)}</p>
                      </div>

                      <div className="flex shrink-0 items-center gap-3 text-right">
                        <div>
                          <div className="text-[11px] uppercase tracking-[0.12em] text-[#717874]">Next wake</div>
                          <div className="mt-1 text-[14px] font-medium text-[#28363c]">{formatTimeOnly(run.next_wakeup_at)}</div>
                        </div>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 text-[#5b6a72]">
                          <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </section>

        <section className="flex min-h-0 flex-col overflow-hidden rounded-[22px] border border-[#d9d0c7] bg-[#f5f1eb] p-4 shadow-[var(--shadow)]">
          {selectedRun ? (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="mb-4 flex flex-col gap-4 border-b border-[#ded5ce] pb-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-[15px] font-semibold tracking-[0.04em] text-[#1e282d]">{selectedRun.order_id}</h2>
                    {(() => {
                      const displayStatus = getDisplayStatus(selectedRun.status, selectedRun.next_wakeup_at);
                      const statusStyle = statusStyles[displayStatus] ?? { pill: "bg-[#e1e9e7] text-[#465c5a]", label: displayStatus };
                      return (
                        <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusStyle.pill}`}>
                          {statusStyle.label}
                        </span>
                      );
                    })()}
                  </div>
                  <p className="mt-2 text-[14px] text-[#5f665f]">{selectedRun.memory_summary || "No memory summary available for this run."}</p>
                </div>

                <div className="text-left sm:text-right">
                  <div className="text-[12px] text-[#707974]">Next wake-up</div>
                  <div className="mt-1 text-[22px] font-semibold tracking-[-0.05em] text-[#1d292d]">{formatTimeOnly(selectedRun.next_wakeup_at)}</div>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                <div className="space-y-5 pb-2">
                  <div className="rounded-2xl border border-[#d8d0c7] bg-[#f8f5f1] p-4">
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Current state</div>
                    <p className="text-[15px] leading-6 text-[#2d383d]">{selectedRun.memory_summary || "No current state recorded."}</p>
                  </div>

                  <div className="rounded-2xl border border-[#d8d0c7] bg-[#f8f5f1] p-4">
                    <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Activity timeline</div>
                    <div className="space-y-3">
                      <Link href={`/runs/${selectedRun.id}`} className="inline-flex items-center rounded-full border border-[#d0c9c2] bg-[#f1ede9] px-2.5 py-1.5 text-[12px] font-medium text-[#213036] hover:bg-[#e7e0d9]">
                        Open full run detail
                      </Link>
                      <p className="text-sm text-[#5c665f]">Timeline data is fetched from the backend for this run.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex min-h-[240px] items-center justify-center rounded-2xl border border-dashed border-[#d2c8c0] bg-[#f8f5f1] p-8 text-center text-[#586663]">
              <div>
                <p className="text-base font-medium text-[#243237]">No run selected</p>
                <p className="mt-2 text-sm">Choose a run from the list to inspect its details.</p>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
