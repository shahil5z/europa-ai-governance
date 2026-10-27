export const MIN_CHARS = 30;
export const MAX_CHARS = 6000;

/** Mirrors the server: strip control and zero-width characters, collapse excess blank lines, trim. */
export function cleanDescription(text: string): string {
  return text
    .replace(/\r\n?/g, "\n")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]/g, "")
    .replace(/\n{4,}/g, "\n\n\n")
    .trim();
}

export type DescriptionCheck = { ok: true } | { ok: false; message: string };

export function checkDescription(text: string): DescriptionCheck {
  const n = cleanDescription(text).length;
  if (n === 0) return { ok: false, message: "Describe the AI system to assess." };
  if (n < MIN_CHARS) return { ok: false, message: `Add more detail: ${MIN_CHARS - n} more character(s) needed (minimum ${MIN_CHARS}).` };
  if (n > MAX_CHARS) return { ok: false, message: `Too long: remove ${n - MAX_CHARS} character(s) (maximum ${MAX_CHARS}).` };
  return { ok: true };
}
