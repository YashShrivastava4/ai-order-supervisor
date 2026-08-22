"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { formatDateTime, normalizeUtcTimestamp } from "@/lib/format-time";
import { API_BASE_URL } from "@/lib/api";

interface TimelineEntry {
    id: string;
    type: string;
    payload: Record<string, unknown>;
    created_at: string;
}

interface Run {
    id: string;
    order_id: string;
    supervisor_id: string;
    order_context: string | null;
    status: string;
    memory_summary: string | null;
    wakeup_guidance: string[] | null;
    next_wakeup_at: string | null;
    final_summary: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
    timeline: TimelineEntry[];
}

const EVENT_TYPES = [
    "order_created",
    "payment_confirmed",
    "payment_failed",
    "shipment_created",
    "shipment_delayed",
    "delivered",
    "refund_requested",
    "customer_message_received",
    "no_update_for_n_hours",
];

// Backend errors come back as JSON ({"detail": "..."}) but the calling code
// was previously using the raw response body as the error message, so a
// failed action showed the user a literal {"detail":"..."} blob instead of
// the message inside it. This pulls the detail out, falling back to the raw
// text for any non-JSON error body.
async function parseErrorDetail(res: Response, fallback: string): Promise<string> {
    const raw = await res.text();
    try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.detail === "string") return parsed.detail;
    } catch {
        // Not JSON — fall through to the raw text below.
    }
    return raw || fallback;
}

const statusStyles: Record<string, { pill: string; label: string }> = {
    running: { pill: "bg-[#dfeee3] text-[#2d6d4b]", label: "Running" },
    sleeping: { pill: "bg-[#f8eac7] text-[#a06b1f]", label: "Sleeping" },
    paused: { pill: "bg-[#f4e7d1] text-[#9b6e2f]", label: "Paused" },
    completed: { pill: "bg-[#dfe9ed] text-[#3d5f71]", label: "Completed" },
    terminated: { pill: "bg-[#f8dfe1] text-[#bc3d4c]", label: "Terminated" },
};

const formatSummaryValue = (value: unknown) => {
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.join(", ");
    if (value && typeof value === "object") return JSON.stringify(value, null, 2);
    return "No details available.";
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

export default function RunDetailPage() {
    const params = useParams();
    const router = useRouter();
    const run_id = params.run_id as string;

    const [run, setRun] = useState<Run | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
    // Set once any action gets a 410 back: this run's Temporal workflow is
    // permanently gone (not a transient error), so we stop offering actions
    // on it for the rest of this page visit rather than let every button
    // fail the same way one at a time.
    const [workflowUnavailable, setWorkflowUnavailable] = useState(false);

    const [eventType, setEventType] = useState(EVENT_TYPES[0]);
    const [eventPayload, setEventPayload] = useState("");
    const [sendingEvent, setSendingEvent] = useState(false);

    const [instruction, setInstruction] = useState("");
    const [sendingInstruction, setSendingInstruction] = useState(false);
    const [sendingControl, setSendingControl] = useState<string | null>(null);

    const fetchRun = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/runs/${run_id}`);
            if (!res.ok) throw new Error("Failed to fetch run");
            const data = await res.json();
            setRun(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Error loading run");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void fetchRun();
        const interval = setInterval(() => {
            void fetchRun();
        }, 2000);
        return () => clearInterval(interval);
    }, [run_id]);

    const handleSendEvent = async () => {
        if (!run) return;

        try {
            const parsedPayload = eventPayload.trim() ? JSON.parse(eventPayload) : null;
            setSendingEvent(true);
            const res = await fetch(`${API_BASE_URL}/api/runs/${run_id}/events`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ event_type: eventType, payload: parsedPayload }),
            });

            if (!res.ok) {
                if (res.status === 410) setWorkflowUnavailable(true);
                throw new Error(await parseErrorDetail(res, "Failed to send event"));
            }
            setEventPayload("");
            setFeedback({ type: "success", message: "Event sent successfully." });
            await fetchRun();
        } catch (err) {
            const message = err instanceof Error ? err.message : "Error sending event";
            setFeedback({ type: "error", message: message.includes("JSON") ? "Event payload must be valid JSON." : message });
        } finally {
            setSendingEvent(false);
        }
    };

    const handleAddInstruction = async () => {
        if (!run || !instruction.trim()) {
            setFeedback({ type: "error", message: "Instruction text is required." });
            return;
        }

        try {
            setSendingInstruction(true);
            const res = await fetch(`${API_BASE_URL}/api/runs/${run_id}/instructions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: instruction.trim() }),
            });

            if (!res.ok) {
                if (res.status === 410) setWorkflowUnavailable(true);
                throw new Error(await parseErrorDetail(res, "Failed to add instruction"));
            }
            setInstruction("");
            setFeedback({ type: "success", message: "Instruction added." });
            await fetchRun();
        } catch (err) {
            setFeedback({ type: "error", message: err instanceof Error ? err.message : "Error adding instruction" });
        } finally {
            setSendingInstruction(false);
        }
    };

    const handleControl = async (action: "interrupt" | "resume" | "terminate") => {
        if (!run) return;

        if (action === "terminate") {
            const confirmed = window.confirm("Terminate this run? This action cannot be undone.");
            if (!confirmed) return;
        }

        try {
            setSendingControl(action);
            const res = await fetch(`${API_BASE_URL}/api/runs/${run_id}/${action}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
            });

            if (!res.ok) {
                if (res.status === 410) setWorkflowUnavailable(true);
                throw new Error(await parseErrorDetail(res, `Failed to ${action}`));
            }
            setFeedback({ type: "success", message: `${action.charAt(0).toUpperCase() + action.slice(1)} sent successfully.` });
            await fetchRun();
        } catch (err) {
            setFeedback({ type: "error", message: err instanceof Error ? err.message : `Error on ${action}` });
        } finally {
            setSendingControl(null);
        }
    };

    if (loading) {
        return <div className="mx-auto w-full max-w-[1200px] rounded-2xl border border-[#d8d0c7] bg-[#faf7f3] p-8 text-center text-[#60706a]">Loading run...</div>;
    }

    if (error && !run) {
        return <div className="mx-auto w-full max-w-[1200px] rounded-2xl border border-[#f0c5c8] bg-[#fdf2f3] p-6 text-[#b24d59]">{error}</div>;
    }

    if (!run) {
        return <div className="mx-auto w-full max-w-[1200px] rounded-2xl border border-dashed border-[#d2c8c0] bg-[#faf7f3] p-8 text-center text-[#586663]">Run not found.</div>;
    }

    const displayStatus = getDisplayStatus(run.status, run.next_wakeup_at);
    const statusStyle = statusStyles[displayStatus] ?? { pill: "bg-[#eceae7] text-[#46515a]", label: displayStatus };
    const normalizedStatus = run.status.toLowerCase();
    const canInterrupt = ["running", "sleeping"].includes(normalizedStatus);
    const canResume = normalizedStatus === "paused";
    const canTerminate = !["completed", "terminated"].includes(normalizedStatus);

    return (
        <div className="mx-auto w-full max-w-[1200px] space-y-6">
            <div className="rounded-[22px] border border-[#d9d0c7] bg-[#f8f5f1] p-5 shadow-[var(--shadow)]">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#697772]">Run detail</div>
                        <div className="mt-3 flex flex-wrap items-center gap-3">
                            <h1 className="text-[30px] font-bold tracking-[-0.06em] text-[#1d2a2a]">{run.order_id}</h1>
                            <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusStyle.pill}`}>
                                {statusStyle.label}
                            </span>
                        </div>
                    </div>

                    <div className="text-left md:text-right">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#717874]">Next wake-up</div>
                        <div className="mt-1 text-[22px] font-semibold tracking-[-0.05em] text-[#1d292d]">{formatDateTime(run.next_wakeup_at, "No wake-up scheduled")}</div>
                    </div>
                </div>
            </div>

            {feedback && (
                <div className={`rounded-xl border px-4 py-3 text-sm ${feedback.type === "success" ? "border-[#bfdac6] bg-[#edf8ef] text-[#285e3d]" : "border-[#f0c5c8] bg-[#fdf2f3] text-[#b24d59]"}`}>
                    {feedback.message}
                </div>
            )}

            <div className="grid gap-6 xl:grid-cols-[1.5fr_0.95fr]">
                <div className="space-y-6">
                    <section className="rounded-[20px] border border-[#d9d0c7] bg-[#f8f5f1] p-5">
                        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Order context</div>
                        <p className="text-[15px] leading-7 text-[#2d383d]">{run.order_context || "No order context provided."}</p>
                    </section>

                    <section className="rounded-[20px] border border-[#d9d0c7] bg-[#f8f5f1] p-5">
                        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Memory / current state</div>
                        <p className="text-[15px] leading-7 text-[#2d383d]">{run.memory_summary || "No memory summary available for this run."}</p>
                    </section>

                    <section className="rounded-[20px] border border-[#d9d0c7] bg-[#f8f5f1] p-5">
                        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Activity timeline</div>
                        {run.timeline && run.timeline.length > 0 ? (
                            <div className="space-y-3">
                                {run.timeline.map((entry) => (
                                    <div key={entry.id} className="rounded-2xl border border-[#d9d0c7] bg-[#f2eee8] p-4">
                                        <div className="flex items-center justify-between gap-3">
                                            <div className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[#3b4850]">{entry.type}</div>
                                            <div className="text-[12px] text-[#6c746f]">{formatDateTime(entry.created_at)}</div>
                                        </div>
                                        <pre className="mt-3 overflow-x-auto rounded-xl bg-[#f8f5f1] p-3 text-[12px] leading-5 text-[#2c373f] whitespace-pre-wrap break-words">
                                            {JSON.stringify(entry.payload ?? {}, null, 2)}
                                        </pre>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-[15px] text-[#586663]">No activity has been recorded for this run yet.</p>
                        )}
                    </section>
                </div>

                <aside className="space-y-6">
                    <section className="rounded-[20px] border border-[#d9d0c7] bg-[#f8f5f1] p-5">
                        <div className="mb-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Operator actions</div>

                        {workflowUnavailable && (
                            <div className="mb-4 rounded-xl border border-[#d8c7a4] bg-[#f4e7d1] px-4 py-3 text-[13px] leading-5 text-[#7b4b0f]">
                                This run&apos;s live workflow is gone from the backend — most likely the
                                free-tier server restarted and its in-progress state was lost. The
                                history to the left is preserved, but no further actions can be sent
                                to this run. This is a known limitation of the current deployment, not
                                a problem with this run specifically.
                            </div>
                        )}

                        <div className="space-y-5">
                            <div>
                                <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Inject Event</label>
                                <select
                                    value={eventType}
                                    onChange={(event) => setEventType(event.target.value)}
                                    className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none"
                                >
                                    {EVENT_TYPES.map((type) => (
                                        <option key={type} value={type}>
                                            {type}
                                        </option>
                                    ))}
                                </select>
                                <textarea
                                    value={eventPayload}
                                    onChange={(event) => setEventPayload(event.target.value)}
                                    rows={4}
                                    placeholder='{"order_id":"..."}'
                                    className="mt-3 w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                                />
                                <button
                                    type="button"
                                    onClick={handleSendEvent}
                                    disabled={sendingEvent || workflowUnavailable}
                                    className="mt-3 w-full rounded-xl bg-[#1d2a2a] px-4 py-2.5 text-[14px] font-medium text-white transition hover:bg-[#131d22] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {sendingEvent ? "Sending event..." : "Send Event"}
                                </button>
                            </div>

                            <div>
                                <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Add Instruction</label>
                                <textarea
                                    value={instruction}
                                    onChange={(event) => setInstruction(event.target.value)}
                                    rows={4}
                                    placeholder="Add guidance for this run..."
                                    className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                                />
                                <button
                                    type="button"
                                    onClick={handleAddInstruction}
                                    disabled={sendingInstruction || workflowUnavailable}
                                    className="mt-3 w-full rounded-xl bg-[#1d2a2a] px-4 py-2.5 text-[14px] font-medium text-white transition hover:bg-[#131d22] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {sendingInstruction ? "Adding instruction..." : "Add Instruction"}
                                </button>
                            </div>

                            <div>
                                <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Controls</div>
                                <div className="space-y-2">
                                    {canInterrupt && (
                                        <button
                                            type="button"
                                            onClick={() => handleControl("interrupt")}
                                            disabled={sendingControl !== null || workflowUnavailable}
                                            className="w-full rounded-xl border border-[#d8c7a4] bg-[#f4e7d1] px-4 py-2.5 text-[14px] font-medium text-[#7b4b0f] transition hover:bg-[#eedbb0] disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            {sendingControl === "interrupt" ? "Interrupting..." : "Interrupt"}
                                        </button>
                                    )}
                                    {canResume && (
                                        <button
                                            type="button"
                                            onClick={() => handleControl("resume")}
                                            disabled={sendingControl !== null || workflowUnavailable}
                                            className="w-full rounded-xl border border-[#c7dbc9] bg-[#dfeee3] px-4 py-2.5 text-[14px] font-medium text-[#2d6d4b] transition hover:bg-[#d3e8d4] disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            {sendingControl === "resume" ? "Resuming..." : "Resume"}
                                        </button>
                                    )}
                                    {canTerminate && (
                                        <button
                                            type="button"
                                            onClick={() => handleControl("terminate")}
                                            disabled={sendingControl !== null || workflowUnavailable}
                                            className="w-full rounded-xl border border-[#e9b7bd] bg-[#f8dfe1] px-4 py-2.5 text-[14px] font-medium text-[#9e2c38] transition hover:bg-[#f0cfd5] disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            {sendingControl === "terminate" ? "Terminating..." : "Terminate"}
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    </section>

                    {run.wakeup_guidance && run.wakeup_guidance.length > 0 && (
                        <section className="rounded-[20px] border border-[#d9d0c7] bg-[#f8f5f1] p-5">
                            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Wake-up guidance</div>
                            <ul className="space-y-2 text-[14px] leading-6 text-[#30404a]">
                                {run.wakeup_guidance.map((item, index) => (
                                    <li key={`${item}-${index}`} className="flex gap-2">
                                        <span className="mt-1 h-1.5 w-1.5 rounded-full bg-[#1d2a2a]" />
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    )}

                    {run.final_summary && Object.keys(run.final_summary).length > 0 && (
                        <section className="rounded-[20px] border border-[#d9d0c7] bg-[#f8f5f1] p-5">
                            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Final summary</div>
                            <div className="space-y-3 text-[14px] leading-6 text-[#2f3a3d]">
                                {Object.entries(run.final_summary).map(([key, value]) => (
                                    <div key={key}>
                                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#697873]">{key.replace(/_/g, " ")}</div>
                                        <div className="rounded-xl bg-[#f3efe9] p-3">{formatSummaryValue(value)}</div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}
                </aside>
            </div>

            <div className="flex justify-start">
                <button
                    type="button"
                    onClick={() => router.push("/")}
                    className="rounded-xl border border-[#d0c9c2] bg-[#f4f0eb] px-4 py-2.5 text-[14px] font-medium text-[#1d2a2a] transition hover:bg-[#ece5dd]"
                >
                    Back to runs
                </button>
            </div>
        </div>
    );
}
