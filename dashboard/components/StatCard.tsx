interface Props {
  label: string;
  value: string | number | null;
  unit?: string;
  sub?: string;
  highlight?: boolean;
}

export default function StatCard({ label, value, unit, sub, highlight }: Props) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        highlight ? "border-blue-200 bg-blue-50" : "border-gray-200 bg-white"
      }`}
    >
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">
        {value == null ? (
          <span className="text-gray-400 text-base">Pending</span>
        ) : (
          <>
            {value}
            {unit && <span className="text-sm font-normal text-gray-500 ml-1">{unit}</span>}
          </>
        )}
      </p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  );
}
