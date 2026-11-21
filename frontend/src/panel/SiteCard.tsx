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
        <dl className="site-stats">
          <div>
            <dt>Pojemność</dt>
            <dd>{fmt.m3(site.storage_m3)}</dd>
          </div>
          <div>
            <dt>Powierzchnia</dt>
            <dd>{fmt.m2(site.area_m2)}</dd>
          </div>
          <div>
            <dt>Głębokość</dt>
            <dd>do {fmt.meters(site.max_depth_m)}</dd>
          </div>
          <div>
            <dt>Zlewnia</dt>
            <dd>{fmt.ha(site.catchment_ha)}</dd>
          </div>
        </dl>
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
