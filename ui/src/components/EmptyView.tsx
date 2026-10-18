import { Button, Center, Group, Kbd, Paper, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import { IconFolderOpen } from "@tabler/icons-react";
import { Logo } from "./Logo";

const STEPS = [
  ["Copy", "a shoot into RAW\\ and JPG\\"],
  ["Cull", "delete JPGs you don't like"],
  ["Remove", "the RAWs left without a JPG"],
] as const;

export function EmptyView({ onOpen }: { onOpen(): void }) {
  return (
    <Center h="100%" p="xl">
      <Stack align="center" gap="xl" maw={640} w="100%">
        <Paper w="100%" radius="lg" p={40}
               style={{ border: "1.5px dashed var(--mantine-color-default-border)", background: "var(--app-subtle-bg)" }}>
          <Stack align="center" gap="sm">
            <Logo size={52} />
            <Title order={3} mt="xs">Open a photo session</Title>
            <Text c="dimmed" ta="center" size="sm" maw={380}>
              Drag the session folder — or any photo from it — into this window. It should contain
              <Text span ff="monospace" fz="sm"> RAW\</Text> and <Text span ff="monospace" fz="sm">JPG\</Text>.
            </Text>
            <Group gap="xs" mt="sm">
              <Button leftSection={<IconFolderOpen size={16} />} onClick={onOpen}>Choose folder…</Button>
              <Text size="xs" c="dimmed"><Kbd size="xs">Ctrl</Kbd> + <Kbd size="xs">O</Kbd></Text>
            </Group>
          </Stack>
        </Paper>
        <Group gap="xl" justify="center" wrap="nowrap">
          {STEPS.map(([title, text], i) => (
            <Group key={title} gap="xs" wrap="nowrap" align="flex-start" w={190}>
              <ThemeIcon size={22} radius="xl" variant="light">
                <Text fz={11} fw={600}>{i + 1}</Text>
              </ThemeIcon>
              <div>
                <Text size="sm" fw={500} lh={1.3}>{title}</Text>
                <Text size="xs" c="dimmed">{text}</Text>
              </div>
            </Group>
          ))}
        </Group>
      </Stack>
    </Center>
  );
}
