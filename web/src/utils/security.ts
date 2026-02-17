export function sanitizeFilename(name: string): string {
  return name.replace(/[^\w\s.-]/g, "_").trim();
}

export function isValidMerchantId(id: string): boolean {
  return /^[a-zA-Z0-9_-]{1,64}$/.test(id);
}

export function escapeHtml(str: string): string {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
