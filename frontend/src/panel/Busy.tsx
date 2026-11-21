export function Busy({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="busy" role="status">
      <progress className="loading-spinner" aria-label={label} />
      <div>
        <p>{label}</p>
        {hint && <p className="muted">{hint}</p>}
      </div>
    </div>
  )
}
