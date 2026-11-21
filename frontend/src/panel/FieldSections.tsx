import type { HydroStatus, LandCover, ModuleResult, SoilProfile, VegetationState } from '../api'
import * as fmt from '../format'
import { ModuleSection } from './ModuleSection'
import { YearBars } from './YearBars'

export function SatelliteSection({
  satellite,
  year,
}: {
  satellite: ModuleResult<VegetationState>
  year: number
}) {
  return (
    <ModuleSection id="satellite" title="Stan roślin z satelity Sentinel-2" module={satellite}>
      {(v) => (
        <>
          {v.current && v.ndmi && v.ndvi ? (
            <>
              <p>
                Zdjęcie z {fmt.longDate(v.current.date)} ({fmt.pct(v.current.clear_pct)} działki
                bez chmur). Uwodnienie roślin NDMI <strong>{fmt.index(v.ndmi.value)}</strong>{' '}
                (średnio {fmt.index(v.ndmi.normal)}), zieleń NDVI{' '}
                <strong>{fmt.index(v.ndvi.value)}</strong> (średnio {fmt.index(v.ndvi.normal)}).
              </p>
              <YearBars
                comparison={v.ndmi}
                year={year}
                format={fmt.index}
                label={`NDMI w tym samym okresie (do ${v.window_days} dni przed datą) w kolejnych latach`}
              />
            </>
          ) : (
            <p>
              {v.history.length} lat z bezchmurnym zdjęciem w tym okresie, ale brak zdjęcia dla
              daty analizy.
            </p>
          )}
          {v.missing_years.length > 0 && (
            <p className="muted">Lata bez bezchmurnego zdjęcia: {v.missing_years.join(', ')}.</p>
          )}
        </>
      )}
    </ModuleSection>
  )
}

export function SoilSection({ soil }: { soil: ModuleResult<SoilProfile> }) {
  return (
    <ModuleSection id="soil" title="Gleba" module={soil}>
      {(s) => (
        <>
          <p>
            <strong>{s.texture}</strong>: kategoria {s.category}, {s.category_label}. Woda
            dostępna dla roślin ok. {fmt.mm(s.awc_mm_per_m)} na 1 m profilu, węgiel organiczny w
            warstwie ornej {fmt.num(s.organic_carbon_pct)} %.
          </p>
          <table className="facts">
            <thead>
              <tr>
                <th scope="col">głębokość</th>
                <th scope="col">piasek</th>
                <th scope="col">ił</th>
                <th scope="col">C org.</th>
              </tr>
            </thead>
            <tbody>
              {s.layers.map((l) => (
                <tr key={l.depth}>
                  <th scope="row">{l.depth}</th>
                  <td>{fmt.pct(l.sand_pct)}</td>
                  <td>{fmt.pct(l.clay_pct)}</td>
                  <td>{fmt.num(l.organic_carbon_pct)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">Model glebowy w siatce {s.resolution_m} m.</p>
        </>
      )}
    </ModuleSection>
  )
}

export function HydroSection({ hydro }: { hydro: ModuleResult<HydroStatus> }) {
  return (
    <ModuleSection id="hydro" title="Susza hydrologiczna (IMGW)" module={hydro}>
      {(h) =>
        h.drought_warnings.length === 0 ? (
          <p>Brak ostrzeżeń o suszy hydrologicznej w woj. {h.voivodeship}.</p>
        ) : (
          <ul className="warnings">
            {h.drought_warnings.map((w) => (
              <li key={w.number + w.area}>
                <strong>
                  Ostrzeżenie nr {w.number}, prawdopodobieństwo {w.probability_pct} %
                </strong>
                <br />
                {w.area}. {w.description}
                <br />
                <span className="muted">
                  Od {w.valid_from}
                  {w.valid_to ? ` do ${w.valid_to}` : ', do odwołania'} · {w.office}
                </span>
              </li>
            ))}
          </ul>
        )
      }
    </ModuleSection>
  )
}

export function LandSection({ land }: { land: ModuleResult<LandCover> }) {
  return (
    <ModuleSection id="land" title="Pokrycie terenu działki" module={land}>
      {(l) => (
        <p>
          {l.classes
            .filter((c) => c.share >= 0.02)
            .map((c) => `${c.name} ${fmt.pct(100 * c.share)}`)
            .join(', ')}{' '}
          <span className="muted">(ESA WorldCover {l.year}, siatka 10 m)</span>
        </p>
      )}
    </ModuleSection>
  )
}
