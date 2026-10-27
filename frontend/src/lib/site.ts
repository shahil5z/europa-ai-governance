/** Canonical origin. Set NEXT_PUBLIC_SITE_URL on the deployment; localhost is the dev fallback. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/+$/, "");
