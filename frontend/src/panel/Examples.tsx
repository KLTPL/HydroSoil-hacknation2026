import { todayIso } from '../useParcelReport'

export interface Example {
  parcelId: string
  crop: string
  date: string
}

// Parcels whose terrain is pre-computed on the server (warm_cache.py), so they answer at once.
const EXAMPLES: { label: string; detail: string; example: Example }[] = [
  {
    label: 'Kujawy, susza 2019',
    detail: 'kukurydza, 20.07.2019',
    example: { parcelId: '040706_5.0016.51/1', crop: 'kukurydza_ziarno', date: '2019-07-20' },
  },
  {
    label: 'Kujawy, czerwiec 2025',
    detail: 'zboża ozime, 15.06.2025',
    example: { parcelId: '040706_5.0016.51/1', crop: 'zboza_ozime', date: '2025-06-15' },
  },
  {
    label: 'Mazowsze, dziś',
    detail: 'zboża ozime, Piaseczno',
    example: { parcelId: '141804_5.0029.14/108', crop: 'zboza_ozime', date: todayIso() },
  },
]

export function Examples({ onPick }: { onPick: (example: Example) => void }) {
  return (
    <section className="examples" aria-labelledby="examples-title">
      <h2 id="examples-title">Albo zobacz przykład</h2>
      <ul>
        {EXAMPLES.map(({ label, detail, example }) => (
          <li key={label}>
            <button type="button" onClick={() => onPick(example)}>
              <strong>{label}</strong>
              <span>{detail}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
