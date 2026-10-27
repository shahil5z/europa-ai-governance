import { afterEach, describe, expect, it, vi } from "vitest";

async function loadSiteUrl() {
  vi.resetModules();
  return (await import("./site")).SITE_URL;
}

describe("SITE_URL", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("falls back to localhost when the variable is not set", async () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", undefined);
    expect(await loadSiteUrl()).toBe("http://localhost:3000");
  });

  it("removes trailing slashes", async () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://example.com//");
    expect(await loadSiteUrl()).toBe("https://example.com");
  });
});
