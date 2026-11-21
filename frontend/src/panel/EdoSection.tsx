import type { EdoDrought, ModuleResult } from '../api'
import * as fmt from '../format'
import { ModuleSection } from './ModuleSection'

const CLASS_LEVEL = ['none', 'watch', 'moderate', 'severe', 'none', 'none', 'none'] as const

function agreement(edo: EdoDrought): string {
  if (edo.agrees === null) return ''
  return edo.agrees
    ? 'Zgodne z naszą oceną.'
    : 'Inaczej niż nasza ocena: EDO patrzy na region (siatka ok. 5 km, wszystkie uprawy), ' +
        'my na tę działkę, jej glebę i wybraną uprawę.'
}

/** Independent cross-check against the European Drought Observatory's CDI map. */
export function EdoSection({ edo }: { edo: ModuleResult<EdoDrought> }) {
  return (
    <ModuleSection id="edo" title="Porównanie z Europejskim Obserwatorium Suszy" module={edo}>
      {(e) => (
        <>
          <p className={`level level-${CLASS_LEVEL[e.cdi_class] ?? 'none'}`}>
            CDI: {e.label}
          </p>
          <p className="muted">
            Mapa dla dekady od {fmt.longDate(e.dekad)}. {agreement(e)}
          </p>
        </>
      )}
    </ModuleSection>
  )
}
