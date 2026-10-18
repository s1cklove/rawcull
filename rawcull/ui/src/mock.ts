// In-browser stand-in for the Python bridge: `npm run dev`, or open index.html?mock=<scenario>.
// Scenarios: session (default) | empty | blocked | problem | clean
import type { Api, FileRow, InitData, Kind, RemoveResult, Snapshot } from "./api";

const MB = 1024 * 1024;

export function createMockApi(scenario: string): Api {
  const session = { path: "D:\\Photos\\2026-10-18 Autumn walk", name: "2026-10-18 Autumn walk" };
  const raws = Array.from({ length: 180 }, (_, i) => `DSC0${4120 + i}`);
  let jpgs = new Set(raws.filter((_, i) => i % 4 !== 1 && i % 11 !== 3));
  if (scenario === "blocked") jpgs = new Set();
  if (scenario === "clean") jpgs = new Set(raws);
  const sidecars = new Set(["DSC04121", "DSC04125"]);
  let rawLeft = new Set(raws);
  let options = { caseSensitive: false, sidecars: true };
  let action: Kind = "trash";
  let opened = scenario !== "empty";
  const size = (k: string) => Math.round((22 + ((k.charCodeAt(7) * 7) % 9)) * MB);

  const snapshot = (): Snapshot => {
    if (scenario === "problem") {
      return { session, rawDir: "RAW\\", jpgDir: null, problem: "Couldn't find a JPG folder here. Open the session folder itself, or choose the folders manually." };
    }
    const remove: FileRow[] = [];
    for (const k of [...rawLeft].sort()) {
      if (jpgs.has(k)) continue;
      remove.push({ name: `${k}.ARW`, path: `${session.path}\\RAW\\${k}.ARW`, kind: "raw", size: size(k) });
      if (options.sidecars && sidecars.has(k))
        remove.push({ name: `${k}.ARW.xmp`, path: `${session.path}\\RAW\\${k}.ARW.xmp`, kind: "sidecar", size: 4812 });
    }
    const kept = [...rawLeft].filter((k) => jpgs.has(k)).length;
    const nRaw = remove.filter((r) => r.kind === "raw").length;
    const errors: string[] = [];
    if (jpgs.size === 0 && rawLeft.size) errors.push(`No JPGs found in ${session.path}\\JPG — this would remove EVERY RAW. Wrong folder?`);
    return {
      session,
      rawDir: "RAW\\",
      jpgDir: "JPG\\",
      problem: null,
      stats: { keepers: jpgs.size + 2, raws: rawLeft.size, kept, remove: nRaw, sidecars: remove.length - nRaw, bytes: remove.reduce((a, r) => a + r.size, 0) },
      errors,
      warnings: [
        "2 JPG(s) have no matching RAW (shot JPG-only, or names don't match?)",
        "1 unrecognised file(s) in the RAW folder are left untouched",
      ],
      files: {
        remove,
        orphan: [
          { name: "IMG_0001.JPG", path: `${session.path}\\JPG\\IMG_0001.JPG`, kind: "jpg", size: 6.1 * MB },
          { name: "IMG_0002.JPG", path: `${session.path}\\JPG\\IMG_0002.JPG`, kind: "jpg", size: 5.8 * MB },
        ],
        ignored: [{ name: "Thumbs.db", path: `${session.path}\\RAW\\Thumbs.db`, kind: "raw", size: 24576 }],
      },
      signature: remove.map((r) => r.name).join("|"),
    };
  };

  const delay = <T,>(v: T, ms = 120) => new Promise<T>((r) => setTimeout(() => r(v), ms));

  return {
    init: () =>
      delay<InitData>({ version: "0.2.0 (mock)", platform: "windows", action, options, menuInstalled: false, snapshot: opened ? snapshot() : null }),
    pick_session: () => {
      opened = true;
      return delay(snapshot(), 300);
    },
    open_session: () => {
      opened = true;
      return delay(snapshot());
    },
    pick_dir: () => delay(snapshot()),
    rescan: () => delay(opened ? snapshot() : null),
    set_options: (caseSensitive, sidecarsOn) => {
      options = { caseSensitive, sidecars: sidecarsOn };
      return delay(snapshot());
    },
    set_action: (k) => {
      action = k;
      return delay(undefined);
    },
    remove: async (kind, force, signature): Promise<RemoveResult> => {
      const s = snapshot();
      if (s.signature !== signature) return { ok: false, reason: "stale", message: "The folders changed since the list was shown. Nothing was removed — check the updated list.", snapshot: s };
      if (s.errors!.length && !force) return { ok: false, reason: "blocked", message: s.errors!.join(" ") };
      const files = s.files!.remove;
      for (let i = 0; i < files.length; i++) {
        window.rawcull?.onProgress?.(i + 1, files.length);
        await delay(null, 8);
      }
      for (const f of files) rawLeft.delete(f.name.split(".")[0]);
      const verb = kind === "trash" ? "sent to the Recycle Bin" : kind === "move" ? "moved to _rejected\\" : "deleted";
      return { ok: true, done: files.length, verb, failed: [], log: "rawcull-20261018-201544.log", snapshot: snapshot() };
    },
    reveal: () => delay(undefined),
    open_session_folder: () => delay(undefined),
    set_context_menu: (on) => delay(on),
  };
}
