import { describe, it, expect } from "vitest";
import { formatDate, formatDuration, formatPercent, formatBytes } from "../../src/utils/format";

describe("format utilities", () => {
  describe("formatPercent", () => {
    it("formats 0 as 0.0%", () => {
      expect(formatPercent(0)).toBe("0.0%");
    });

    it("formats 1 as 100.0%", () => {
      expect(formatPercent(1)).toBe("100.0%");
    });

    it("formats 0.753 as 75.3%", () => {
      expect(formatPercent(0.753)).toBe("75.3%");
    });

    it("formats small decimals", () => {
      expect(formatPercent(0.001)).toBe("0.1%");
    });
  });

  describe("formatBytes", () => {
    it("formats 0 bytes", () => {
      expect(formatBytes(0)).toBe("0 B");
    });

    it("formats KB", () => {
      expect(formatBytes(1024)).toBe("1.0 KB");
    });

    it("formats MB", () => {
      expect(formatBytes(1024 * 1024)).toBe("1.0 MB");
    });

    it("formats GB", () => {
      expect(formatBytes(1024 * 1024 * 1024)).toBe("1.0 GB");
    });
  });

  describe("formatDuration", () => {
    it("formats milliseconds", () => {
      expect(formatDuration(45)).toBe("45ms");
    });

    it("formats seconds", () => {
      expect(formatDuration(5000)).toBe("5.0s");
    });

    it("formats minutes and seconds", () => {
      expect(formatDuration(125000)).toBe("2m 5s");
    });
  });

  describe("formatDate", () => {
    it("returns a formatted date string", () => {
      const result = formatDate("2024-01-15T10:30:00Z");
      expect(result).toBeTruthy();
      expect(typeof result).toBe("string");
    });
  });
});
