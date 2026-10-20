/** The FraudLens mark: two overlapping lenses, drawn in the current text colour. */
export function LensMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" fill="none" aria-hidden="true">
      <circle cx="12" cy="15" r="9" stroke="currentColor" strokeWidth="2.3" />
      <path d="M18 6a9 9 0 1 1 0 18" stroke="currentColor" strokeWidth="2.3" />
      <path d="M9 15h12" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
