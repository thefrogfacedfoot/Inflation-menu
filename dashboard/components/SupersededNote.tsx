export const GRANGER_SUPERSEDED_NOTE =
  "All Granger results shown use an earlier specification and will be replaced by the pre-registered analysis.";

export default function SupersededNote({ className = "" }: { className?: string }) {
  return (
    <p
      className={`text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 leading-relaxed ${className}`}
    >
      {GRANGER_SUPERSEDED_NOTE}
    </p>
  );
}
