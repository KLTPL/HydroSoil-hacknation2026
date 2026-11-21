import { useId, useState, type FormEvent } from 'react'
import { errorMessage } from '../useParcelReport'
import type { Account } from './useAccount'

export function LoginForm({ account }: { account: Account }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const userId = useId()
  const passId = useId()
  const registering = mode === 'register'

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await account.signIn(mode, username.trim(), password)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card account-login" aria-labelledby={`${userId}-h`}>
      <h3 id={`${userId}-h`}>{registering ? 'Załóż konto' : 'Zaloguj się'}</h3>
      <p className="muted fine">
        Konto nie jest potrzebne do analizy. Pozwala zapisać działki, sprawdzić wszystkie naraz i
        wracać do starszych raportów. Podajesz tylko nazwę i hasło: bez e-maila i danych osobowych.
      </p>
      <form className="account-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor={userId}>Nazwa użytkownika</label>
          <input
            id={userId}
            value={username}
            autoComplete="username"
            autoCapitalize="none"
            minLength={3}
            maxLength={32}
            pattern="[A-Za-z0-9._\-]+"
            title="Litery bez polskich znaków, cyfry, kropka, podkreślnik lub myślnik"
            required
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={passId}>Hasło {registering && <span className="muted">(min. 8 znaków)</span>}</label>
          <input
            id={passId}
            type="password"
            value={password}
            autoComplete={registering ? 'new-password' : 'current-password'}
            minLength={8}
            maxLength={128}
            required
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {registering && (
          <p className="notice fine">
            Zapamiętaj hasło. Nie zbieramy e-maila, więc nie da się go odzyskać ani zresetować.
          </p>
        )}
        <div aria-live="polite">{error && <p className="error">{error}</p>}</div>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Chwileczkę…' : registering ? 'Załóż konto' : 'Zaloguj się'}
        </button>
      </form>
      <button
        type="button"
        className="quiet account-switch"
        onClick={() => {
          setMode(registering ? 'login' : 'register')
          setError(null)
        }}
      >
        {registering ? 'Mam już konto: zaloguj się' : 'Nie masz konta? Załóż je'}
      </button>
    </section>
  )
}
