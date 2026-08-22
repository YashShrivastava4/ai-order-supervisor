"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api";

interface Supervisor {
    id: string;
    name: string;
    base_instruction: string;
    available_actions: string[];
}

export default function NewRunPage() {
    const router = useRouter();
    const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    const [formData, setFormData] = useState({
        supervisor_id: "",
        order_id: "",
        order_context: "",
    });

    // Loads the list of supervisors to pick from, and defaults to the first one
    const fetchSupervisors = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/supervisors`);
            if (!res.ok) throw new Error("Failed to fetch supervisors");
            const data = await res.json();
            setSupervisors(Array.isArray(data) ? data : []);

            if (Array.isArray(data) && data.length > 0) {
                setFormData((prev) => ({ ...prev, supervisor_id: prev.supervisor_id || data[0].id }));
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Error loading supervisors");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void fetchSupervisors();
    }, []);

    // Creates the run, then jumps straight to its detail page
    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        setError(null);
        setSuccess(null);

        if (!formData.supervisor_id || !formData.order_id.trim()) {
            setError("Supervisor and order ID are required.");
            return;
        }

        setSubmitting(true);

        try {
            const res = await fetch(`${API_BASE_URL}/api/runs`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    supervisor_id: formData.supervisor_id,
                    order_id: formData.order_id.trim(),
                    order_context: formData.order_context.trim() || null,
                }),
            });

            if (!res.ok) {
                const detail = await res.text();
                throw new Error(detail || "Failed to create run");
            }

            const run = await res.json();
            setSuccess("Run created successfully.");
            router.push(`/runs/${run.id}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Error creating run");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="mx-auto w-full max-w-[760px]">
            <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                    <h1 className="text-[32px] font-bold tracking-[-0.05em] text-[#1b252b]">New Run</h1>
                    <p className="mt-1 text-[14px] text-[#6d726d]">Create a new order run using a live supervisor configuration.</p>
                </div>
                <button
                    type="button"
                    onClick={() => router.push("/")}
                    className="rounded-xl border border-[#d0c9c2] bg-[#f4f0eb] px-4 py-2.5 text-[14px] font-medium text-[#1d2a2a] transition hover:bg-[#ece5dd]"
                >
                    Back
                </button>
            </div>

            {error && (
                <div className="mb-4 rounded-xl border border-[#f0c5c8] bg-[#fdf2f3] px-4 py-3 text-sm text-[#b24d59]">
                    {error}
                </div>
            )}

            {success && (
                <div className="mb-4 rounded-xl border border-[#bfdac6] bg-[#edf8ef] px-4 py-3 text-sm text-[#285e3d]">
                    {success}
                </div>
            )}

            {loading ? (
                <div className="rounded-[22px] border border-[#d9d0c7] bg-[#f8f5f1] p-8 text-center text-[#586663]">Loading supervisors...</div>
            ) : supervisors.length === 0 ? (
                <div className="rounded-[22px] border border-dashed border-[#d2c8c0] bg-[#f8f5f1] p-8 text-center text-[#586663]">
                    <p className="text-base font-medium text-[#243237]">No supervisors available.</p>
                    <a href="/supervisors" className="mt-3 inline-block text-[14px] font-medium text-[#1e2d36] underline underline-offset-4">
                        Create a supervisor first
                    </a>
                </div>
            ) : (
                <form onSubmit={handleSubmit} className="rounded-[22px] border border-[#d9d0c7] bg-[#f8f5f1] p-6 shadow-[var(--shadow)]">
                    <div className="space-y-6">
                        <div>
                            <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.12em] text-[#586663]">Supervisor</label>
                            <select
                                value={formData.supervisor_id}
                                onChange={(event) => setFormData((prev) => ({ ...prev, supervisor_id: event.target.value }))}
                                required
                                className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none"
                            >
                                {supervisors.map((supervisor) => (
                                    <option key={supervisor.id} value={supervisor.id}>
                                        {supervisor.name}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.12em] text-[#586663]">Order ID</label>
                            <input
                                type="text"
                                value={formData.order_id}
                                onChange={(event) => setFormData((prev) => ({ ...prev, order_id: event.target.value }))}
                                required
                                placeholder="e.g. ORD-1001"
                                className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                            />
                        </div>

                        <div>
                            <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.12em] text-[#586663]">Order Context</label>
                            <textarea
                                value={formData.order_context}
                                onChange={(event) => setFormData((prev) => ({ ...prev, order_context: event.target.value }))}
                                rows={6}
                                placeholder="Optional order notes, customer context, or shipping notes..."
                                className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                            />
                        </div>

                        <div className="flex flex-col gap-3 sm:flex-row">
                            <button
                                type="submit"
                                disabled={submitting}
                                className="flex-1 rounded-xl bg-[#1d2a2a] px-5 py-3 text-[14px] font-medium text-white transition hover:bg-[#131d22] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {submitting ? "Starting run..." : "Create Run"}
                            </button>
                            <button
                                type="button"
                                onClick={() => router.push("/")}
                                className="flex-1 rounded-xl border border-[#d0c9c2] bg-[#f4f0eb] px-5 py-3 text-[14px] font-medium text-[#1d2a2a] transition hover:bg-[#ece5dd]"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </form>
            )}
        </div>
    );
}
