import { describe, it, expect, beforeEach } from "vitest";
import { useSettingsStore } from "../../src/stores/settingsStore";

describe("settingsStore", () => {
  beforeEach(() => {
    // Reset settings to defaults
    const s = useSettingsStore.getState();
    s.setTheme("dark");
    s.setSkipSubmitConfirm(false);
    s.setEnableRestReminder(true);
    s.setRestReminderMinutes(60);
    s.setEnableSound(true);
    s.setPreferredPageSize(20);
  });

  it("has correct defaults", () => {
    const s = useSettingsStore.getState();
    expect(s.theme).toBe("dark");
    expect(s.skipSubmitConfirm).toBe(false);
    expect(s.enableRestReminder).toBe(true);
    expect(s.restReminderMinutes).toBe(60);
    expect(s.enableSound).toBe(true);
    expect(s.preferredPageSize).toBe(20);
  });

  it("toggles theme", () => {
    const { setTheme } = useSettingsStore.getState();
    setTheme("light");
    expect(useSettingsStore.getState().theme).toBe("light");
    setTheme("dark");
    expect(useSettingsStore.getState().theme).toBe("dark");
  });

  it("sets skipSubmitConfirm", () => {
    useSettingsStore.getState().setSkipSubmitConfirm(true);
    expect(useSettingsStore.getState().skipSubmitConfirm).toBe(true);
  });

  it("sets restReminderMinutes", () => {
    useSettingsStore.getState().setRestReminderMinutes(30);
    expect(useSettingsStore.getState().restReminderMinutes).toBe(30);
  });

  it("sets preferredPageSize", () => {
    useSettingsStore.getState().setPreferredPageSize(50);
    expect(useSettingsStore.getState().preferredPageSize).toBe(50);
  });
});
