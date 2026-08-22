// Central config for the backend base URL.
//
// Locally this defaults to the FastAPI dev server. In production (e.g. a
// Vercel deployment), set NEXT_PUBLIC_API_URL to wherever the backend is
// reachable — the app will not work without it, since the frontend has no
// backend of its own.
// A trailing slash on NEXT_PUBLIC_API_URL (e.g. "https://api.example.com/")
// produces double-slash request URLs like "POST //api/supervisors", which
// fails with "Failed to fetch" — hit for real against the Render deployment.
// Stripping it here means a stray trailing slash in the env var can't break
// requests again.
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");
