import { createTheme, rem, type MantineColorsTuple } from "@mantine/core";

// GitLab Pajamas blue ramp. Index 6 is the light-mode primary ($blue-500
// #1f75cb, GitLab's interactive blue); index 4 is the brighter dark-mode
// primary. Send exact hex to fine-tune any step.
const brand: MantineColorsTuple = [
  "#e9f3fc",
  "#cbe2f9",
  "#9dc7f1",
  "#6f9ee8",
  "#418cd8",
  "#2b82d4",
  "#1f75cb",
  "#1068bf",
  "#0b5cad",
  "#064787",
];

// Flat, dense, neutral (GitLab-like) look. Small radius, Inter font, subtle
// borders — the personality lives in the token values, not in component chrome.
export const theme = createTheme({
  fontFamily: "Inter, sans-serif",
  fontFamilyMonospace: "ui-monospace, SFMono-Regular, Menlo, monospace",
  headings: { fontFamily: "Inter, sans-serif", fontWeight: "600" },
  primaryColor: "brand",
  primaryShade: { light: 6, dark: 4 },
  defaultRadius: "sm",
  colors: { brand },
  radius: {
    xs: "4px",
    sm: "4px",
    md: "6px",
    lg: "12px",
    xl: "16px",
  },
  components: {
    // A touch more air between an input's label and the field itself.
    InputWrapper: {
      styles: { label: { marginBottom: rem(5) } },
    },
  },
});
