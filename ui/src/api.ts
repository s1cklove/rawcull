// Typed view of rawcull.bridge.SessionApi (Python). Keep in sync with bridge.py.

export type Kind = "trash" | "move" | "delete";

export interface FileRow {
  name: string;
  path: string;
  kind: "raw" | "sidecar" | "jpg";
  size: number;
}

export interface Snapshot {
  session: { path: string; name: string };
  rawDir: string | null;
  jpgDir: string | null;
  problem: string | null;
  stats?: { keepers: number; raws: number; kept: number; remove: number; sidecars: number; bytes: number };
  errors?: string[];
  warnings?: string[];
  files?: { remove: FileRow[]; orphan: FileRow[]; ignored: FileRow[] };
  signature?: string;
}

export interface Options {
  caseSensitive: boolean;
  sidecars: boolean;
}

export interface InitData {
  version: string;
  platform: "windows" | "other";
  action: Kind;
  options: Options;
  menuInstalled: boolean;
  snapshot: Snapshot | null;
}

export type RemoveResult =
  | { ok: true; done: number; verb: string; failed: { name: string; error: string }[]; log: string | null; snapshot: Snapshot }
  | { ok: false; reason: "busy" | "no-session" | "stale" | "blocked" | "empty" | "action"; message: string; snapshot?: Snapshot };

export interface Api {
  init(): Promise<InitData>;
  pick_session(): Promise<Snapshot | { problem: string } | null>;
  open_session(path: string): Promise<Snapshot | { problem: string }>;
  pick_dir(which: "raw" | "jpg"): Promise<Snapshot | null>;
  rescan(): Promise<Snapshot | null>;
  set_options(caseSensitive: boolean, sidecars: boolean): Promise<Snapshot | null>;
  set_action(kind: Kind): Promise<void>;
  remove(kind: Kind, force: boolean, signature: string): Promise<RemoveResult>;
  reveal(path: string): Promise<void>;
  open_session_folder(): Promise<void>;
  set_context_menu(on: boolean): Promise<boolean>;
}

/** Callbacks Python pushes into the page (bridge.SessionApi._push). */
export interface PushHandlers {
  onSnapshot(s: Snapshot): void;
  onProgress(done: number, total: number): void;
  onDropFailed(): void;
}

declare global {
  interface Window {
    pywebview?: { api: Api };
    rawcull?: Partial<PushHandlers>;
  }
}

export function isSnapshot(x: unknown): x is Snapshot {
  return !!x && typeof x === "object" && "session" in (x as object);
}

/** Resolves with the Python API, or with an in-browser mock for `npm run dev` / `?mock`. */
export function connect(): Promise<Api> {
  const params = new URLSearchParams(location.search);
  if (params.has("mock") || (import.meta.env.DEV && !window.pywebview)) {
    return import("./mock").then((m) => m.createMockApi(params.get("mock") || "session"));
  }
  if (window.pywebview?.api?.init) return Promise.resolve(window.pywebview.api);
  return new Promise((resolve) => {
    window.addEventListener("pywebviewready", () => resolve(window.pywebview!.api), { once: true });
  });
}

export function formatBytes(n: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return i === 0 ? `${n} B` : `${n.toFixed(n >= 100 ? 0 : 1)} ${units[i]}`;
}

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
