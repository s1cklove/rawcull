import { ActionIcon, Box, Button, Group, Kbd, Menu, Switch, Text, Tooltip } from "@mantine/core";
import {
  IconDots, IconFolderOpen, IconFolders, IconInfoCircle, IconPhoto, IconRefresh, IconExternalLink,
} from "@tabler/icons-react";
import type { Snapshot } from "../api";
import { Logo } from "./Logo";

export function Header(props: {
  snap: Snapshot | null;
  scanning: boolean;
  windows: boolean;
  menuInstalled: boolean;
  onOpen(): void;
  onRescan(): void;
  onPickDir(which: "raw" | "jpg"): void;
  onShowFolder(): void;
  onToggleMenu(on: boolean): void;
  onAbout(): void;
}) {
  const { snap } = props;
  return (
    <Group h={48} px="md" justify="space-between" wrap="nowrap" bg="var(--app-header-bg)"
           style={{ borderBottom: "1px solid var(--mantine-color-default-border)", flexShrink: 0 }}>
      <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
        <Logo />
        <Text fw={600}>rawcull</Text>
      </Group>
      <Group gap={6} wrap="nowrap">
        <Tooltip label={<>Open session <Kbd size="xs">Ctrl</Kbd>+<Kbd size="xs">O</Kbd></>}>
          <Button size="xs" variant="default" leftSection={<IconFolderOpen size={15} />} onClick={props.onOpen}>
            Open
          </Button>
        </Tooltip>
        <Tooltip label={<>Rescan <Kbd size="xs">F5</Kbd></>}>
          <ActionIcon variant="default" size={30} onClick={props.onRescan} loading={props.scanning}
                      disabled={!snap} aria-label="Rescan">
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
        <Menu position="bottom-end" width={290} shadow="md" closeOnItemClick>
          <Menu.Target>
            <ActionIcon variant="default" size={30} aria-label="More">
              <IconDots size={16} />
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Label>Session</Menu.Label>
            <Menu.Item leftSection={<IconExternalLink size={15} />} disabled={!snap} onClick={props.onShowFolder}>
              Show session folder
            </Menu.Item>
            <Menu.Item leftSection={<IconFolders size={15} />} onClick={() => props.onPickDir("raw")}>
              Choose RAW folder manually…
            </Menu.Item>
            <Menu.Item leftSection={<IconPhoto size={15} />} onClick={() => props.onPickDir("jpg")}>
              Choose JPG folder manually…
            </Menu.Item>
            {props.windows && (
              <>
                <Menu.Divider />
                <Menu.Label>Windows</Menu.Label>
                <Box px="sm" py={6}>
                  <Switch size="xs" checked={props.menuInstalled}
                          onChange={(e) => props.onToggleMenu(e.currentTarget.checked)}
                          label="“Cull RAWs” in folder right-click menu"
                          description="Right-click a session in Explorer to open it here" />
                </Box>
              </>
            )}
            <Menu.Divider />
            <Menu.Item leftSection={<IconInfoCircle size={15} />} onClick={props.onAbout}>
              About rawcull
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>
    </Group>
  );
}
