import { useCallback, useEffect, useState } from 'react'
import * as api from './accountApi'
import type { SavedParcel } from './accountApi'

/** `checking` until the server says whether a session cookie is valid. */
export type AccountState = { status: 'checking' } | { status: 'anonymous' } | {
  status: 'user'
  username: string
}

export function useAccount() {
  const [state, setState] = useState<AccountState>({ status: 'checking' })
  const [saved, setSaved] = useState<SavedParcel[]>([])

  const apply = useCallback((me: api.Me) => {
    setState(me.username ? { status: 'user', username: me.username } : { status: 'anonymous' })
    if (!me.username) setSaved([])
  }, [])

  const refreshSaved = useCallback(async () => {
    setSaved(await api.fetchSaved())
  }, [])

  useEffect(() => {
    // Accounts are optional: if the check fails the app simply works anonymously.
    api.fetchMe().then(
      (me) => {
        apply(me)
        if (me.username) void refreshSaved()
      },
      () => setState({ status: 'anonymous' }),
    )
  }, [apply, refreshSaved])

  const signIn = useCallback(
    async (mode: 'login' | 'register', username: string, password: string) => {
      const me = await (mode === 'login' ? api.login : api.register)(username, password)
      apply(me)
      await refreshSaved()
    },
    [apply, refreshSaved],
  )

  const signOut = useCallback(async () => {
    apply(await api.logout())
  }, [apply])

  return { state, saved, refreshSaved, signIn, signOut }
}

export type Account = ReturnType<typeof useAccount>
