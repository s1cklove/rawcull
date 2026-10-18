// Crossed-out lens — same mark as the .exe icon.
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <rect x="2" y="2" width="60" height="60" rx="14" fill="var(--mantine-primary-color-filled)" />
      <circle cx="32" cy="32" r="20.5" fill="#fff" />
      <circle cx="32" cy="32" r="14.5" fill="#1d1d1b" />
      <line x1="13.5" y1="50.5" x2="50.5" y2="13.5" stroke="#fff" strokeWidth="4.5" strokeLinecap="round" />
    </svg>
  );
}
