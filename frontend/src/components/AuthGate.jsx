import { useEffect, useState } from 'react'
import { clearSession, developmentIdentity, initializeAuth, signIn, signInConfigured, signOut } from '../services/auth'

export default function AuthGate({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!developmentIdentity && signInConfigured)
  const [error, setError] = useState('')

  useEffect(() => {
    if (developmentIdentity || !signInConfigured) return
    let cancelled = false
    initializeAuth().then((result) => {
      if (!cancelled) setUser(result)
    }).catch(() => {
      if (!cancelled) setError('Unable to complete sign-in. Please try again.')
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    const expire = () => {
      void clearSession()
      setUser(null)
      setError('Your session has expired. Please sign in again.')
    }
    window.addEventListener('documind:session-expired', expire)
    return () => {
      cancelled = true
      window.removeEventListener('documind:session-expired', expire)
    }
  }, [])

  if (developmentIdentity || user) {
    return <>
      <div className="fixed bottom-4 right-4 z-50 flex items-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-2 text-xs shadow-sm">
        <span>{developmentIdentity ? 'Local development workspace' : user.profile.name || 'Private workspace'}</span>
        {!developmentIdentity && <button onClick={() => signOut().catch(() => setError('Unable to sign out. Please try again.'))} className="font-semibold underline">Sign out</button>}
        {error && <span role="alert">{error}</span>}
      </div>
      {children}
    </>
  }

  return <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-6 text-zinc-900">
    <section className="w-full max-w-md rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">DocuMind AI</p>
      <h1 className="mt-3 text-2xl font-semibold">Your private document workspace</h1>
      <p className="mt-3 text-sm leading-6 text-zinc-600">Understand documents, review evidence, and turn findings into useful actions.</p>
      {loading ? <p className="mt-6 text-sm" role="status">Checking your session…</p> : signInConfigured ?
        <button className="mt-6 w-full rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white" onClick={() => signIn().catch(() => setError('Unable to open sign-in. Please try again.'))}>Sign in to continue</button> :
        <p className="mt-6 rounded-xl bg-zinc-50 p-4 text-sm text-zinc-600">Sign-in is being set up. Contact your workspace administrator for access.</p>}
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    </section>
  </main>
}
