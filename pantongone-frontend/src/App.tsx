import { lazy, Suspense, useEffect, useState } from 'react'
import {
  getMeta,
  setSignedOutHandler,
  signOut,
  storedSession,
  type Meta,
  type Session,
} from '@/lib/api'
import { Login } from '@/panels/Login'
import './App.css'

/* Everything past the sign-in screen is fetched when it is first needed
 * (tech-stack.md 2). The gate stays eager because it IS the first paint;
 * making it wait on a second round trip would trade a smaller download for a
 * slower start, which is the wrong way round. */
const Desk = lazy(() => import('@/panels/Desk').then((m) => ({ default: m.Desk })))

/* Screens are chosen with useState, not a router. This is one screen whose
 * contents change - the desktop program is a window with four tabs, not a set
 * of pages anybody bookmarks (tech-stack.md 2).
 *
 * The app draws NOTHING until the held session has been looked at. A flash of
 * the sign-in form for somebody who is already signed in is the thing that
 * avoids, and it is the same reason the desktop gate runs before the main
 * window is built rather than over the top of it. */
export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [metaError, setMetaError] = useState('')

  useEffect(() => {
    setSession(storedSession())
    setReady(true)
    /* One handler for the whole app: when the server says a token is finished,
     * the sign-in screen comes back wherever somebody happened to be. The
     * alternative is every screen remembering to check, and the one that
     * forgets leaves a person clicking a dead page. */
    setSignedOutHandler(() => setSession(null))
  }, [])

  /* The labels are fetched BEFORE the sign-in, because the sign-in screen is
   * drawn out of them: /api/meta is open for exactly that reason. It gives away
   * a version string and the words on a form - not a single figure from the
   * price book. */
  useEffect(() => {
    getMeta()
      .then(setMeta)
      .catch((e: Error) => setMetaError(e.message))
  }, [])

  if (!ready) return null

  if (!session) {
    return <Login meta={meta} metaError={metaError} onSignedIn={setSession} />
  }

  return (
    <Suspense fallback={<p className="app-wait">กำลังเปิด / opening...</p>}>
      <Desk meta={meta} session={session} onSignOut={signOut} />
    </Suspense>
  )
}
