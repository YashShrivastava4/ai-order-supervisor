// Backend base URL. Defaults to the local FastAPI dev server; in production
// set NEXT_PUBLIC_API_URL to the deployed backend. Trailing slashes are
// stripped so a misconfigured env var can't produce double-slash requests.
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");
