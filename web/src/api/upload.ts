const TUS_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export async function tusUpload(
  file: File,
  onProgress?: (p: UploadProgress) => void,
  onComplete?: (fileId: string) => void,
): Promise<string> {
  // 1. Creation request
  const createRes = await fetch(`${TUS_BASE}/uploads`, {
    method: "POST",
    headers: {
      "Upload-Length": String(file.size),
      "Upload-Metadata": `filename ${btoa(file.name)},filetype ${btoa(file.type)}`,
      "Tus-Resumable": "1.0.0",
    },
  });
  if (!createRes.ok) throw new Error(`Upload creation failed: ${createRes.status}`);
  const location = createRes.headers.get("Location") || "";
  const fileId = location.split("/").pop() || "";

  // 2. Chunked PATCH upload
  const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB
  let offset = 0;

  while (offset < file.size) {
    const end = Math.min(offset + CHUNK_SIZE, file.size);
    const chunk = file.slice(offset, end);

    const patchRes = await fetch(`${TUS_BASE}/uploads/${fileId}`, {
      method: "PATCH",
      headers: {
        "Upload-Offset": String(offset),
        "Content-Type": "application/offset+octet-stream",
        "Tus-Resumable": "1.0.0",
      },
      body: chunk,
    });
    if (!patchRes.ok) throw new Error(`Upload patch failed at offset ${offset}`);

    offset = end;
    onProgress?.({
      loaded: offset,
      total: file.size,
      percentage: Math.round((offset / file.size) * 100),
    });
  }

  onComplete?.(fileId);
  return fileId;
}

export async function getUploadOffset(fileId: string): Promise<number> {
  const res = await fetch(`${TUS_BASE}/uploads/${fileId}`, { method: "HEAD",
    headers: { "Tus-Resumable": "1.0.0" } });
  return parseInt(res.headers.get("Upload-Offset") || "0", 10);
}
