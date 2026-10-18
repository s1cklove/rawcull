import { ActionIcon, Badge, ScrollArea, Table, Text, Tooltip } from "@mantine/core";
import { IconFolderSearch } from "@tabler/icons-react";
import { formatBytes, type FileRow } from "../api";
import classes from "./FileTable.module.css";

const KIND: Record<FileRow["kind"], { label: string; color: string }> = {
  raw: { label: "RAW", color: "gray" },
  sidecar: { label: "Sidecar", color: "violet" },
  jpg: { label: "JPG", color: "brand" },
};

export function FileTable({ rows, onReveal, kindHeader = "Type" }: {
  rows: FileRow[];
  onReveal: (p: string) => void;
  kindHeader?: string;
}) {
  return (
    <ScrollArea h="100%" type="auto" offsetScrollbars={false}>
      <Table stickyHeader highlightOnHover verticalSpacing={5} horizontalSpacing="md" fz="sm" className={classes.table}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>File</Table.Th>
            <Table.Th w={110}>{kindHeader}</Table.Th>
            <Table.Th w={110} ta="right">Size</Table.Th>
            <Table.Th w={52} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((r) => (
            <Table.Tr key={r.path} className={classes.row} onDoubleClick={() => onReveal(r.path)}>
              <Table.Td>
                <Text ff="monospace" fz="sm" className="selectable">{r.name}</Text>
              </Table.Td>
              <Table.Td>
                <Badge size="sm" radius="sm" variant="light" color={KIND[r.kind].color}>{KIND[r.kind].label}</Badge>
              </Table.Td>
              <Table.Td ta="right" c="dimmed" style={{ fontVariantNumeric: "tabular-nums" }}>{formatBytes(r.size)}</Table.Td>
              <Table.Td>
                <Tooltip label="Show in Explorer" openDelay={400}>
                  <ActionIcon variant="subtle" color="gray" size="sm" className={classes.reveal}
                              onClick={() => onReveal(r.path)} aria-label="Show in Explorer">
                    <IconFolderSearch size={15} />
                  </ActionIcon>
                </Tooltip>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
}
