import { post } from "@/lib/api/client";

export type OfflineIssue = {
  local_id: string;
  client_request_id: string;
  category_id: string;
  administrative_area_id?: string;
  title: string;
  description: string;
  severity: string;
  latitude: number;
  longitude: number;
  address_text?: string;
  anonymous_public_display: boolean;
  media?: File[];
  created_at: string;
  sync_status: "PENDING_SYNC" | "SYNCING" | "SYNCED" | "FAILED";
};

const DATABASE = "civicgrid-offline";
const STORE = "issue-queue";

function openQueue(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) {
        request.result.createObjectStore(STORE, { keyPath: "local_id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function queueIssue(issue: Omit<OfflineIssue, "local_id" | "created_at" | "sync_status">) {
  const db = await openQueue();
  const queued: OfflineIssue = {
    ...issue,
    local_id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
    sync_status: "PENDING_SYNC",
  };
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE, "readwrite");
    transaction.objectStore(STORE).put(queued);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
  return queued;
}

export async function pendingIssues(): Promise<OfflineIssue[]> {
  const db = await openQueue();
  const items = await new Promise<OfflineIssue[]>((resolve, reject) => {
    const request = db.transaction(STORE).objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return items.filter((item) => item.sync_status !== "SYNCED");
}

async function updateQueued(issue: OfflineIssue) {
  const db = await openQueue();
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE, "readwrite");
    transaction.objectStore(STORE).put(issue);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
}

export async function syncQueuedIssues() {
  if (!navigator.onLine) return;
  for (const issue of await pendingIssues()) {
    await updateQueued({ ...issue, sync_status: "SYNCING" });
    try {
      const payload = {
        client_request_id: issue.client_request_id,
        category_id: issue.category_id,
        administrative_area_id: issue.administrative_area_id,
        title: issue.title,
        description: issue.description,
        severity: issue.severity,
        latitude: issue.latitude,
        longitude: issue.longitude,
        address_text: issue.address_text,
        anonymous_public_display: issue.anonymous_public_display,
      };
      const created = await post<{ id: string }>("/issues", payload);
      for (const file of issue.media ?? []) {
        const body = new FormData();
        body.append("file", file);
        await import("@/lib/api/client").then(({ api }) =>
          api("/issues/" + created.id + "/media", { method: "POST", body }),
        );
      }
      await updateQueued({ ...issue, sync_status: "SYNCED" });
    } catch {
      await updateQueued({ ...issue, sync_status: "FAILED" });
    }
  }
}
