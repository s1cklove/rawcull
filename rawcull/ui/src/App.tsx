import {
  Alert, Badge, Box, Button, Center, Checkbox, Group, List, Loader, Overlay, Paper, Stack, Tabs, Text, Title,
} from "@mantine/core";
import { EmptyState } from "@mantine/core";
import { useHotkeys } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import {
  IconAlertOctagon, IconAlertTriangle, IconCircleCheck, IconDragDrop, IconFolderQuestion,
} from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  connect, formatBytes, isSnapshot, plural, type Api, type InitData, type Kind, type Options, type Snapshot,
} from "./api";
import { ActionBar } from "./components/ActionBar";
import { EmptyView } from "./components/EmptyView";
import { FileTable } from "./components/FileTable";
import { Header } from "./components/Header";
import { Stats } from "./components/Stats";

export function App() {
  const [api, setApi] = useState<Api | null>(null);
  const [info, setInfo] = useState<InitData | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [action, setAction] = useState<Kind>("trash");
  const [options, setOptions] = useState<Options>({ caseSensitive: false, sidecars: true });
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [tab, setTab] = useState<string | null>("remove");
  const [dragging, setDragging] = useState(false);
  const [menuInstalled, setMenuInstalled] = useState(false);
  const busyRef = useRef(false);
  busyRef.current = busy;

  // ------------------------------------------------------------------ connect
  useEffect(() => {
    connect().then(async (a) => {
      const data = await a.init();
      setApi(a);
      setInfo(data);
      setAction(data.action);
      setOptions(data.options);
      setMenuInstalled(data.menuInstalled);
      if (data.snapshot) setSnap(data.snapshot);
    });
  }, []);

  const accept = useCallback((x: unknown) => {
    if (isSnapshot(x)) {
      setSnap((prev) => {
        if (prev?.signature !== x.signature) setForce(false); // overrides never carry over to a new plan
        if (prev?.session.path !== x.session.path) setTab("remove");
        return x;
      });
    } else if (x && typeof x === "object" && "problem" in x) {
      notifications.show({ color: "red", title: "Can't open that", message: String((x as { problem: string }).problem) });
    }
  }, []);

  // Python → page pushes
  useEffect(() => {
    window.rawcull = {
      onSnapshot: (s) => !busyRef.current && accept(s),
      onProgress: (done, total) => setProgress({ done, total }),
      onDropFailed: () =>
        notifications.show({ color: "yellow", title: "Couldn't read that drop", message: "Drop a folder or a photo from the session, or use Open." }),
    };
    return () => { delete window.rawcull; };
  }, [accept]);

  // ------------------------------------------------------------------ actions
  const open = useCallback(() => { if (api && !busy) api.pick_session().then(accept); }, [api, busy, accept]);
  const rescan = useCallback(() => {
    if (!api || busy || !snap) return;
    setScanning(true);
    api.rescan().then(accept).finally(() => setScanning(false));
  }, [api, busy, snap, accept]);

  useHotkeys([["mod+O", open], ["F5", rescan], ["mod+R", rescan]]);

  // Desktop-app manners: no browser reload / context menu.
  useEffect(() => {
    const keys = (e: KeyboardEvent) => {
      if (e.key === "F5" || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "r")) e.preventDefault();
    };
    const ctx = (e: MouseEvent) => { if (!import.meta.env.DEV) e.preventDefault(); };
    window.addEventListener("keydown", keys);
    window.addEventListener("contextmenu", ctx);
    return () => { window.removeEventListener("keydown", keys); window.removeEventListener("contextmenu", ctx); };
  }, []);

  // Drag & drop: the page only shows the overlay; Python receives the real path (gui.py).
  useEffect(() => {
    let depth = 0;
    const hasFiles = (e: DragEvent) => !!e.dataTransfer && Array.from(e.dataTransfer.types).includes("Files");
    const enter = (e: DragEvent) => { if (hasFiles(e)) { depth++; setDragging(true); } };
    const over = (e: DragEvent) => { if (hasFiles(e)) e.preventDefault(); };
    const leave = () => { depth = Math.max(0, depth - 1); if (!depth) setDragging(false); };
    const drop = (e: DragEvent) => {
      e.preventDefault();
      depth = 0;
      setDragging(false);
      if (!window.pywebview && api) api.open_session("dropped").then(accept); // browser mock
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  }, [api, accept]);

  const changeAction = (k: Kind) => { setAction(k); api?.set_action(k); };
  const changeOptions = (o: Options) => {
    setOptions(o);
    if (!api) return;
    setScanning(true);
    api.set_options(o.caseSensitive, o.sidecars).then(accept).finally(() => setScanning(false));
  };
  const pickDir = (which: "raw" | "jpg") => api?.pick_dir(which).then(accept);
  const toggleMenu = (on: boolean) => api?.set_context_menu(on).then((v) => {
    setMenuInstalled(v);
    if (v) notifications.show({ color: "teal", title: "Added to Explorer", message: "Right-click a session folder → “Cull RAWs (rawcull)”. On Windows 11 it's under “Show more options”." });
  });
  const about = () => modals.open({
    title: "rawcull",
    children: (
      <Stack gap="xs">
        <Text size="sm">Removes RAW files whose JPG you deleted.</Text>
        <Text size="sm" c="dimmed">Version {info?.version}. Matching uses the part of the name before the first dot.
          Every run writes a log into the session folder.</Text>
      </Stack>
    ),
  });

  const blocked = !!snap?.errors?.length && !force;
  const doRemove = useCallback(async () => {
    if (!api || !snap?.signature) return;
    setBusy(true);
    setProgress(null);
    try {
      const r = await api.remove(action, force, snap.signature);
      if (r.ok) {
        accept(r.snapshot);
        if (r.failed.length) {
          notifications.show({
            color: "red", autoClose: false, title: `${r.done} ${r.verb}, ${r.failed.length} failed`,
            message: (
              <List size="xs">{r.failed.slice(0, 8).map((f) => <List.Item key={f.name}>{f.name}: {f.error}</List.Item>)}</List>
            ),
          });
        } else {
          notifications.show({
            color: "teal", icon: <IconCircleCheck size={18} />, title: `${plural(r.done, "file")} ${r.verb}`,
            message: r.log ? `Log: ${r.log}` : undefined,
          });
        }
      } else {
        if (r.snapshot) accept(r.snapshot);
        notifications.show({ color: r.reason === "stale" ? "yellow" : "red", title: "Nothing was removed", message: r.message });
      }
    } catch (e) {
      notifications.show({ color: "red", title: "Something went wrong", message: String(e) });
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }, [api, snap, action, force, accept]);

  const confirmRemove = () => {
    if (!snap?.stats) return;
    const s = snap.stats;
    const n = s.remove + s.sidecars;
    const bin = info?.platform === "windows" ? "Recycle Bin" : "Trash";
    const what = action === "trash" ? `Send ${plural(n, "file")} to the ${bin}?`
      : action === "move" ? `Move ${plural(n, "file")} to _rejected\\?` : `Permanently delete ${plural(n, "file")}?`;
    modals.openConfirmModal({
      title: <Text fw={600}>{what}</Text>,
      centered: true,
      children: (
        <Stack gap={6}>
          <Text size="sm">
            {plural(s.remove, "RAW")}{s.sidecars ? ` and ${plural(s.sidecars, "sidecar")}` : ""} · {formatBytes(s.bytes)}
          </Text>
          <Text size="sm" c={action === "delete" ? "red" : "dimmed"}>
            {action === "trash" ? `You can restore them from the ${bin} in one go.`
              : action === "move" ? `They go to ${snap.session.name}\\_rejected\\.`
              : "This cannot be undone."}
          </Text>
          {force && <Text size="sm" c="red" fw={500}>Safety checks are overridden.</Text>}
        </Stack>
      ),
      labels: { confirm: action === "delete" ? "Delete permanently" : "Confirm", cancel: "Cancel" },
      confirmProps: { color: action === "delete" ? "red" : undefined, "data-autofocus": action !== "delete" },
      onConfirm: doRemove,
    });
  };

  // ------------------------------------------------------------------ render
  if (!info) {
    return <Center h="100%"><Loader size="sm" /></Center>;
  }
  const windows = info.platform === "windows";
  const files = snap?.files;

  return (
    <Box h="100%" style={{ display: "flex", flexDirection: "column" }}>
      <Header snap={snap} scanning={scanning} windows={windows} menuInstalled={menuInstalled}
              onOpen={open} onRescan={rescan} onPickDir={pickDir}
              onShowFolder={() => api?.open_session_folder()} onToggleMenu={toggleMenu} onAbout={about} />

      <Box style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }} p="md">
        {!snap ? (
          <EmptyView onOpen={open} />
        ) : snap.problem ? (
          <Center h="100%">
            <EmptyState color="yellow" icon={<IconFolderQuestion size={26} />}
                        title="Session folders not found" description={snap.problem}>
              <Group justify="center" mt="md" gap="xs">
                <Button variant="default" onClick={() => pickDir("raw")}>Choose RAW folder…</Button>
                <Button variant="default" onClick={() => pickDir("jpg")}>Choose JPG folder…</Button>
                <Button onClick={open}>Open another session</Button>
              </Group>
            </EmptyState>
          </Center>
        ) : (
          <Stack gap="md" style={{ flex: 1, minHeight: 0 }}>
            <Group justify="space-between" align="flex-end" wrap="nowrap">
              <div style={{ minWidth: 0 }}>
                <Title order={3} lh={1.2} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{snap.session.name}</Title>
                <Text size="sm" c="dimmed" ff="monospace" className="selectable"
                      style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={snap.session.path}>
                  {snap.session.path}  ·  {snap.rawDir} {snap.jpgDir}
                </Text>
              </div>
              <Badge variant="dot" color="teal" size="md" radius="sm" tt="none" fw={500} style={{ flexShrink: 0 }}>
                Watching for changes
              </Badge>
            </Group>

            <Stats snap={snap} />

            {!!snap.errors?.length && (
              <Alert className="status-danger" icon={<IconAlertOctagon size={18} />} title="Removal blocked" py="sm">
                <Stack gap={8}>
                  {snap.errors.map((e) => <Text key={e} size="sm">{e}</Text>)}
                  <Checkbox size="xs" color="red" checked={force} onChange={(e) => setForce(e.currentTarget.checked)}
                            label="I know what I'm doing — override safety checks for this list" />
                </Stack>
              </Alert>
            )}
            {!!snap.warnings?.length && (
              <Alert className="status-warn" icon={<IconAlertTriangle size={18} />} py={8}>
                <Stack gap={2}>{snap.warnings.map((w) => <Text key={w} size="sm">{w}</Text>)}</Stack>
              </Alert>
            )}

            <Paper withBorder radius="md" style={{ flex: 1, minHeight: 220, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <Tabs value={tab} onChange={setTab} style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
                <Tabs.List px="xs">
                  <Tabs.Tab value="remove" rightSection={<Badge size="xs" variant="light" color={files!.remove.length ? "red" : "gray"} circle={files!.remove.length < 10}>{files!.remove.length}</Badge>}>
                    To remove
                  </Tabs.Tab>
                  <Tabs.Tab value="orphan" rightSection={<Badge size="xs" variant="light" color="gray" circle>{files!.orphan.length}</Badge>}>
                    JPGs without RAW
                  </Tabs.Tab>
                  <Tabs.Tab value="ignored" rightSection={<Badge size="xs" variant="light" color="gray" circle>{files!.ignored.length}</Badge>}>
                    Ignored files
                  </Tabs.Tab>
                </Tabs.List>
                {(["remove", "orphan", "ignored"] as const).map((key) => (
                  <Tabs.Panel key={key} value={key} style={{ flex: 1, minHeight: 0 }}>
                    {files![key].length ? (
                      <FileTable rows={files![key]} onReveal={(p) => api?.reveal(p)}
                                 kindHeader={key === "ignored" ? "Folder" : "Type"} />
                    ) : (
                      <Center h="100%" py="xl">
                        <EmptyState size="sm" color={key === "remove" ? "teal" : "gray"}
                          icon={key === "remove" ? <IconCircleCheck size={22} /> : undefined}
                          title={key === "remove" ? "Every RAW still has its JPG" : key === "orphan" ? "Every JPG has a RAW" : "No unknown files"}
                          description={key === "remove" ? "Delete JPGs in Explorer — this list updates by itself." : undefined} />
                      </Center>
                    )}
                  </Tabs.Panel>
                ))}
              </Tabs>
            </Paper>
          </Stack>
        )}
      </Box>

      {snap && !snap.problem && <ActionBar snap={snap} windows={windows} action={action} options={options} blocked={blocked} busy={busy}
                 progress={progress} onAction={changeAction} onOptions={changeOptions} onRemove={confirmRemove} />}

      {dragging && (
        <Overlay fixed backgroundOpacity={0.55} blur={2} zIndex={500}>
          <Center h="100%">
            <Paper radius="lg" p={40} withBorder
                   style={{ border: "2px dashed var(--mantine-primary-color-filled)", pointerEvents: "none" }}>
              <Stack align="center" gap="xs">
                <IconDragDrop size={40} color="var(--mantine-primary-color-filled)" />
                <Text fw={600}>Drop to open this session</Text>
                <Text size="sm" c="dimmed">A session folder, its RAW\ / JPG\, or any photo from it</Text>
              </Stack>
            </Paper>
          </Center>
        </Overlay>
      )}
    </Box>
  );
}
