import { Paper, SimpleGrid, Text } from "@mantine/core";
import { formatBytes, type Snapshot } from "../api";

function Stat({ label, value, color, hint }: { label: string; value: string; color?: string; hint?: string }) {
  return (
    <Paper withBorder radius="md" px="md" py="sm" bg="var(--app-subtle-bg)">
      <Text size="xs" c="dimmed" fw={500} tt="uppercase" style={{ letterSpacing: "0.04em" }}>
        {label}
      </Text>
      <Text fz={26} fw={600} lh={1.25} c={color} style={{ fontVariantNumeric: "tabular-nums" }}>
        {value}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      )}
    </Paper>
  );
}

export function Stats({ snap }: { snap: Snapshot }) {
  const s = snap.stats!;
  return (
    <SimpleGrid cols={5} spacing="sm">
      <Stat label="JPG keepers" value={String(s.keepers)} />
      <Stat label="RAW files" value={String(s.raws)} />
      <Stat label="Kept" value={String(s.kept)} color={s.kept ? "teal.7" : undefined} />
      <Stat label="To remove" value={String(s.remove)} color={s.remove ? "red.7" : undefined}
            hint={s.sidecars ? `+ ${s.sidecars} sidecar${s.sidecars === 1 ? "" : "s"}` : undefined} />
      <Stat label="Space freed" value={s.bytes ? formatBytes(s.bytes) : "—"} />
    </SimpleGrid>
  );
}
