"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

interface Supervisor {
    id: string;
    name: string;
    base_instruction: string;
    available_actions: string[];
    default_wakeup_behavior?: string | null;
    model_config?: string | null;
    wakeup_aggressiveness?: string | null;
}

const allActions = [
    "message_customer",
    "message_fulfillment_team",
    "message_payments_team",
    "message_logistics_team",
    "create_internal_note",
];

export default function SupervisorsPage() {
    const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    const [formData, setFormData] = useState({
        name: "",
        base_instruction: "",
        available_actions: ["message_customer"],
        default_wakeup_behavior: "",
        model_config: "",
        wakeup_aggressiveness: "medium",
    });

    const fetchSupervisors = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/supervisors`);
            if (!res.ok) throw new Error("Failed to fetch supervisors");
            const data = await res.json();
            setSupervisors(Array.isArray(data) ? data : []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Error loading supervisors");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void fetchSupervisors();
    }, []);

    const handleActionToggle = (action: string) => {
        setFormData((prev) => ({
            ...prev,
            available_actions: prev.available_actions.includes(action)
                ? prev.available_actions.filter((item) => item !== action)
                : [...prev.available_actions, action],
        }));
    };

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        setError(null);
        setSuccess(null);

        if (!formData.name.trim() || !formData.base_instruction.trim()) {
            setError("Name and base instruction are required.");
            return;
        }

        setSubmitting(true);

        try {
            const res = await fetch(`${API_BASE_URL}/api/supervisors`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ...formData,
                    name: formData.name.trim(),
                    base_instruction: formData.base_instruction.trim(),
                    default_wakeup_behavior: formData.default_wakeup_behavior.trim() || null,
                    model_config: formData.model_config.trim() || null,
                }),
            });

            if (!res.ok) throw new Error("Failed to create supervisor");
            setSuccess("Supervisor created successfully.");
            setFormData({
                name: "",
                base_instruction: "",
                available_actions: ["message_customer"],
                default_wakeup_behavior: "",
                model_config: "",
                wakeup_aggressiveness: "medium",
            });
            await fetchSupervisors();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Error creating supervisor");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="mx-auto w-full max-w-[1200px]">
            <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                    <h1 className="text-[32px] font-bold tracking-[-0.05em] text-[#1b252b]">Supervisors</h1>
                    <p className="mt-1 text-[14px] text-[#6d726d]">Configure the rules and capabilities used when a new order run starts.</p>
                </div>
                <button
                    type="button"
                    onClick={() => window.history.back()}
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
            ) : (
                <div className="grid gap-6 xl:grid-cols-[1.1fr_1.3fr]">
                    <section className="flex max-h-[calc(100vh-190px)] min-h-0 flex-col overflow-hidden rounded-[22px] border border-[#d9d0c7] bg-[#f8f5f1] p-5 shadow-[var(--shadow)]">
                        <div className="mb-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Existing supervisors</div>

                        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                            {supervisors.length === 0 ? (
                                <div className="rounded-2xl border border-dashed border-[#d2c8c0] bg-[#f4f0eb] p-8 text-center text-[#586663]">
                                    No supervisors yet. Create one to get started.
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {supervisors.map((supervisor) => (
                                        <article key={supervisor.id} className="rounded-2xl border border-[#d9d0c7] bg-[#f3efe9] p-4">
                                            <div className="flex items-start justify-between gap-3">
                                                <div>
                                                    <h2 className="text-[17px] font-semibold text-[#1f2d35]">{supervisor.name}</h2>
                                                    <p className="mt-2 text-[13px] leading-6 text-[#4f5a5d]">{supervisor.base_instruction || "No base instruction provided."}</p>
                                                </div>
                                            </div>

                                            <div className="mt-4 flex flex-wrap gap-2">
                                                {supervisor.available_actions?.length ? (
                                                    supervisor.available_actions.map((action) => (
                                                        <span key={action} className="rounded-full bg-[#dfe9ee] px-2 py-1 text-[10px] font-medium uppercase tracking-[0.1em] text-[#3f5662]">
                                                            {action}
                                                        </span>
                                                    ))
                                                ) : (
                                                    <span className="text-[12px] text-[#64706b]">No actions configured.</span>
                                                )}
                                            </div>

                                            <div className="mt-4 grid gap-2 text-[12px] text-[#586663] sm:grid-cols-2">
                                                <div>
                                                    <div className="font-medium uppercase tracking-[0.12em] text-[#68736c]">Wake-up aggressiveness</div>
                                                    <div className="mt-1">{supervisor.wakeup_aggressiveness || "Not set"}</div>
                                                </div>
                                                <div>
                                                    <div className="font-medium uppercase tracking-[0.12em] text-[#68736c]">Model config</div>
                                                    <div className="mt-1">{supervisor.model_config || "Not set"}</div>
                                                </div>
                                            </div>
                                        </article>
                                    ))}
                                </div>
                            )}
                        </div>
                    </section>

                    <section className="rounded-[22px] border border-[#d9d0c7] bg-[#f8f5f1] p-5 shadow-[var(--shadow)]">
                        <div className="mb-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Create supervisor</div>

                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div>
                                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Identity</div>
                                <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Name</label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(event) => setFormData((prev) => ({ ...prev, name: event.target.value }))}
                                    required
                                    placeholder="Example: Standard Order Supervisor"
                                    className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                                />
                            </div>

                            <div>
                                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Behavior</div>
                                <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Base instruction</label>
                                <textarea
                                    value={formData.base_instruction}
                                    onChange={(event) => setFormData((prev) => ({ ...prev, base_instruction: event.target.value }))}
                                    rows={5}
                                    required
                                    placeholder="Describe how the supervisor should think and act..."
                                    className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                                />

                                <div className="mt-4 grid gap-4 md:grid-cols-2">
                                    <div>
                                        <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Wake-up aggressiveness</label>
                                        <select
                                            value={formData.wakeup_aggressiveness}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, wakeup_aggressiveness: event.target.value }))}
                                            className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none"
                                        >
                                            <option value="low">Low</option>
                                            <option value="medium">Medium</option>
                                            <option value="high">High</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Default wake-up behavior</label>
                                        <input
                                            type="text"
                                            value={formData.default_wakeup_behavior}
                                            onChange={(event) => setFormData((prev) => ({ ...prev, default_wakeup_behavior: event.target.value }))}
                                            placeholder="e.g. check order status"
                                            className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                                        />
                                    </div>
                                </div>
                            </div>

                            <div>
                                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Capabilities</div>
                                <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Available actions</label>
                                <div className="grid gap-2 sm:grid-cols-2">
                                    {allActions.map((action) => (
                                        <label key={action} className="flex items-center gap-2 rounded-xl border border-[#d8d0c7] bg-[#f3efe9] px-3 py-2 text-[13px] text-[#2e3a40]">
                                            <input
                                                type="checkbox"
                                                checked={formData.available_actions.includes(action)}
                                                onChange={() => handleActionToggle(action)}
                                                className="h-4 w-4 rounded border-[#8a8f8a]"
                                            />
                                            <span>{action}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#68736c]">Model</div>
                                <label className="mb-2 block text-[12px] font-medium uppercase tracking-[0.1em] text-[#586663]">Model config</label>
                                <input
                                    type="text"
                                    value={formData.model_config}
                                    onChange={(event) => setFormData((prev) => ({ ...prev, model_config: event.target.value }))}
                                    placeholder="Optional model or provider configuration"
                                    className="w-full rounded-xl border border-[#d0c9c2] bg-[#f3efe9] px-3 py-2.5 text-[14px] text-[#243237] outline-none placeholder:text-[#7a817d]"
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={submitting}
                                className="w-full rounded-xl bg-[#1d2a2a] px-5 py-3 text-[14px] font-medium text-white transition hover:bg-[#131d22] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {submitting ? "Creating supervisor..." : "Create Supervisor"}
                            </button>
                        </form>
                    </section>
                </div>
            )}
        </div>
    );
}
