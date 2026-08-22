# Known Issues

## Temporal workflow state is lost when the Render free-tier backend restarts

**What happens:** after the backend's Render service spins down from inactivity (or is
redeployed) and then wakes back up, actions on runs that were created before the restart fail
with:

```json
{"detail": "This run's live workflow is no longer available on the backend, most likely because
the free-tier server restarted and its in-progress Temporal state was lost. This run's history
above is preserved, but no further actions can be taken on it. This is a known limitation of the
current free-tier deployment, not a problem with this specific run."}
```

The run's UI, order context, and full activity timeline remain visible — that data lives in Neon
Postgres, which is unaffected by the backend restarting. Only the *live* Temporal workflow
execution is gone.

**Why:** the backend runs FastAPI, the Temporal worker, and a Temporal *dev* server
(`temporal server start-dev`) together in one Render container, with the dev server persisting
workflow state to a local sqlite file. Render's free web services have an ephemeral filesystem —
every restart (idle spin-down, redeploy, or manual restart) wipes local disk, taking that sqlite
file with it. The dev server comes back up with no memory of any previously running workflow.
This is inherent to running Temporal's dev server (meant for local development) on free-tier,
spin-down-prone compute — not a bug in the application code.

**Current behavior:** the API detects this specific failure (a Temporal `RPCError` with a
`NOT_FOUND` status — see `WorkflowNotFoundError` in `backend/app/temporal_client.py`) and returns
an HTTP 410 with a clear explanation, instead of a generic 500. The frontend (`src/app/runs/
[run_id]/page.tsx`) shows a dedicated banner on affected runs and disables further actions on
them, rather than letting each button fail one at a time with a raw error.

**What would actually fix it** (not implemented — evaluated and intentionally deferred to keep
this a $0 deployment):
- Upgrade the Render backend service off the Free plan (Starter, $7/mo) — removes the idle
  spin-down that triggers this, with no code changes. Add a small persistent disk too if you also
  want a redeploy to not lose in-flight runs.
- Move Temporal's persistence off local disk entirely — run a real Temporal server (not
  `start-dev`) backed by an external database, or use Temporal Cloud — so a container restart no
  longer matters. More correct, but real infrastructure work, and Temporal Cloud has no free tier
  for production use (starts at $100/mo).

See `notes.md` for the full investigation and reasoning behind choosing the graceful-degradation
path over these instead.
