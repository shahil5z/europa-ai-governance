import { describe, expect, it } from "vitest";
import { checkDescription, cleanDescription, MAX_CHARS, MIN_CHARS } from "./validation";

describe("validation", () => {
  it("strips control characters and trims", () => {
    expect(cleanDescription("  a\u0000b\u0007c \n")).toBe("abc");
  });
  it("enforces the length bounds", () => {
    expect(checkDescription("x".repeat(MIN_CHARS - 1)).ok).toBe(false);
    expect(checkDescription("x".repeat(MIN_CHARS)).ok).toBe(true);
    expect(checkDescription("x".repeat(MAX_CHARS)).ok).toBe(true);
    expect(checkDescription("x".repeat(MAX_CHARS + 1)).ok).toBe(false);
  });
});
