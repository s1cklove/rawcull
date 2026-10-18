import { Box, Button, Center, Group, Progress, SegmentedControl, Switch, Text, Tooltip } from "@mantine/core";
import { IconFolderShare, IconRecycle, IconTrashX } from "@tabler/icons-react";
import { formatBytes, plural, type Kind, type Options, type Snapshot } from "../api";

export function ActionBar(props: {
  snap: Snapshot | null;
  windows: boolean;
  action: Kind;
  options: Options;
  blocked: boolean;
  busy: boolean;
  progress: { done: number; total: number } | null;
  onAction(k: Kind): void;
  onOptions(o: Options): void;
  onRemove(): void;
}) {
  const { snap, action } = props;
  const files = snap?.files?.remove ?? [];
  const n = files.length;
  const bin = props.windows ? "Recycle Bin" : "Trash";
  const seg = (icon: React.ReactNode, label: string) => (
    <Center style={{ gap: 6 }}>{icon}<span>{label}</span></Center>
  );
  const label = !n ? "Nothing to remove"
    : action === "trash" ? `Send ${plural(n, "file")} to ${bin}`
    : action === "move" ? `Move ${plural(n, "file")} to _rejected`
    : `Delete ${plural(n, "file")}`;
  const why = !snap || snap.problem ? "Open a session first"
    : !n ? "Every RAW still has its JPG"
    : props.blocked ? "Blocked by a safety check — see above" : null;
  const pct = props.progress ? (100 * props.progress.done) / Math.max(1, props.progress.total) : 0;

  return (
    <Box pos="relative" px="md" py={10} bg="var(--app-subtle-bg)"
         style={{ borderTop: "1px solid var(--mantine-color-default-border)", flexShrink: 0 }}>
      {props.busy && (
        <Progress value={props.progress ? pct : 100} animated={!props.progress || props.progress.total <= 1}
                  size={3} radius={0} pos="absolute" top={-1} left={0} right={0} />
      )}
      <Group justify="space-between" wrap="nowrap" gap="md">
        <Group gap="lg" wrap="nowrap">
          <SegmentedControl size="xs" value={action} onChange={(v) => props.onAction(v as Kind)} disabled={props.busy}
            data={[
              { value: "trash", label: seg(<IconRecycle size={14} />, bin) },
              { value: "move", label: seg(<IconFolderShare size={14} />, "Move to _rejected") },
              { value: "delete", label: seg(<IconTrashX size={14} />, "Delete") },
            ]} />
          <Tooltip label="Also remove .xmp / .pp3 / .dop files that belong to a removed RAW" openDelay={500}>
            <Switch size="xs" label="Sidecars" checked={props.options.sidecars} disabled={props.busy}
                    onChange={(e) => props.onOptions({ ...props.options, sidecars: e.currentTarget.checked })} />
          </Tooltip>
          <Tooltip label="Treat DSC0001 and dsc0001 as different shots" openDelay={500}>
            <Switch size="xs" label="Case-sensitive" checked={props.options.caseSensitive} disabled={props.busy}
                    onChange={(e) => props.onOptions({ ...props.options, caseSensitive: e.currentTarget.checked })} />
          </Tooltip>
        </Group>
        <Group gap="md" wrap="nowrap">
          {n > 0 && (
            <Text size="sm" c="dimmed" style={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
              {props.busy && props.progress ? `${props.progress.done} / ${props.progress.total}` : formatBytes(snap!.stats!.bytes)}
            </Text>
          )}
          <Tooltip label={why} disabled={!why || props.busy}>
            <Button color={action === "delete" ? "red" : undefined} data-disabled={!!why || undefined}
                    loading={props.busy} miw={210}
                    onClick={(e) => (why ? e.preventDefault() : props.onRemove())}
                    leftSection={action === "delete" ? <IconTrashX size={16} /> : action === "move" ? <IconFolderShare size={16} /> : <IconRecycle size={16} />}>
              {label}
            </Button>
          </Tooltip>
        </Group>
      </Group>
    </Box>
  );
}
