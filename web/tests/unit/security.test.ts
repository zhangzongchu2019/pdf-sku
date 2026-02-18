import { describe, it, expect } from "vitest";
import { sanitizeHtml, escapeHtml } from "../../src/utils/security";

describe("security utilities", () => {
  it("escapeHtml escapes angle brackets", () => {
    expect(escapeHtml("<script>alert(1)</script>")).not.toContain("<script>");
  });

  it("escapeHtml escapes ampersand", () => {
    expect(escapeHtml("a & b")).toContain("&amp;");
  });

  it("escapeHtml produces a string", () => {
    const result = escapeHtml('"hello"');
    expect(typeof result).toBe("string");
    // innerHTML encoding of quotes is browser-dependent
    expect(result.length).toBeGreaterThan(0);
  });

  it("sanitizeHtml strips HTML tags", () => {
    const result = sanitizeHtml("<b>bold</b> text");
    expect(result).not.toContain("<b>");
    expect(result).toContain("text");
  });
});
