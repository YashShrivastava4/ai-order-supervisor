// Central config for the backend base URL.
//
// Locally this defaults to the FastAPI dev server. In production (e.g. a
// Vercel deployment), set NEXT_PUBLIC_API_URL to wherever the backend is
// reachable — the app will not work without it, since the frontend has no
// backend of its own.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
