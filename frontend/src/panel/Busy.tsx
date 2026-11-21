export function Busy({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="busy" role="status">
      <progress className="loading-spinner" aria-hidden="true" />
      <div>
        <p>{label}</p>
        {hint && <p className="muted">{hint}</p>}
      </div>
    </div>
  )
}
