/**
 * Web Worker: 计算文件 SHA-256 Hash (不阻塞主线程)。
 *
 * 用法:
 *   const worker = new Worker(new URL("./hashWorker.ts", import.meta.url), { type: "module" });
 *   worker.postMessage(file);
 *   worker.onmessage = (e) => console.log(e.data.hash);
 */
self.onmessage = async (e: MessageEvent<File>) => {
  const file = e.data;
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  self.postMessage({ hash: hashHex, size: file.size, name: file.name });
};

export {};
