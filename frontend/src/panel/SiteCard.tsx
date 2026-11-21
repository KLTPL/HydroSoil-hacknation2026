import type { RetentionSite, SiteKind } from '../api'
import * as fmt from '../format'

const KIND_COPY: Record<SiteKind, { title: string; advice: string }> = {
  pond: {
    title: 'Miejsce na oczko wodne',
    advice:
      'Głębokie zagłębienie: można je pogłębić i uszczelnić jako zbiornik na wodę ze spływu. ' +
      'Przed pracami sprawdź wymagania prawa wodnego.',
  },
  wet_depression: {
    title: 'Obniżenie do zatrzymania wody',
    advice:
      'Płytkie obniżenie: zostaw je jako łąkę lub pas zieleni i nie zaorywaj, ' +
      'żeby woda wsiąkała zamiast spływać.',
  },
}

interface Props {
  site: RetentionSite
  rainMm: number
  selected: boolean
  onSelect: (id: number) => void
}

export function SiteCard({ site, rainMm, selected, onSelect }: Props) {
  const copy = KIND_COPY[site.kind]
  return (
    <li>
      <button
        type="button"
        className={`site-card kind-${site.kind}`}
        aria-pressed={selected}
        onClick={() => onSelect(site.id)}
      >
        <span className="site-title">
          {site.id}. {copy.title}
        </span>
        <span className="site-headline">
          {fmt.m3Range(site.retained_m3)} <small>z deszczu {rainMm} mm</small>
        </span>
        <span className="site-stats">
          <span>
            <span className="site-stat-label">Pojemność</span>{' '}
            <span className="site-stat-value">{fmt.m3(site.storage_m3)}</span>
          </span>
          <span>
            <span className="site-stat-label">Powierzchnia</span>{' '}
            <span className="site-stat-value">{fmt.m2(site.area_m2)}</span>
          </span>
          <span>
            <span className="site-stat-label">Głębokość</span>{' '}
            <span className="site-stat-value">do {fmt.meters(site.max_depth_m)}</span>
          </span>
          <span>
            <span className="site-stat-label">Zlewnia</span>{' '}
            <span className="site-stat-value">{fmt.ha(site.catchment_ha)}</span>
          </span>
        </span>
        {selected && <span className="site-advice">{copy.advice}</span>}
        {site.parcel_share < 0.95 && (
          <span className="site-note">
            Na tej działce leży {fmt.share(site.parcel_share)} obniżenia; resztę zajmują
            działki sąsiadów.
          </span>
        )}
      </button>
    </li>
  )
}
