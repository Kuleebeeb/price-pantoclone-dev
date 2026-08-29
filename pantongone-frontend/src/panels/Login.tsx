import { useEffect, useRef, useState } from 'react'
import { ApiError, signIn, type Meta, type Session } from '@/lib/api'
import mark from '@/assets/pantong.png'
import './Login.css'

/* THE DOOR, KEPT.
 *
 * Bee, 27-08-2026: "vẫn giữ màn đăng nhập". The desktop program asks before it
 * draws anything - that was the point of building the gate in the first place,
 * and a web version that opened straight onto the price book would undo it.
 * Same layout as Z:\1\gate.py: the mark, the name, what version and WHICH HOST
 * the password is about to be sent to, then the two boxes.
 *
 * SAYING THE HOST OUT LOUD IS NOT A LEAK. It is in the .exe, in every packet,
 * and in the address bar above this form. A password box that will not say who
 * is receiving it is the shape of every phishing page ever made.
 *
 * SAYING WHOSE PASSWORD, LIKEWISE. Since 28-08-2026 the server may hand what
 * is typed here to PacOs (meta.sign_in_with === 'pacos'). A person with two
 * passwords and no line telling them which one this box wants will try the
 * wrong one, be refused, and read the refusal as the door being broken.
 *
 * ONE BUTTON, NOT TWO. The desktop has "ออก / Exit" beside "เข้าสู่ระบบ" because
 * a window that refuses to open has to leave a way out of itself. A browser tab
 * already has one, drawn by the browser, and a button that pretends to close a
 * tab is a button that mostly cannot.
 */

type Props = {
  meta: Meta | null
  metaError: string
  onSignedIn: (session: Session) => void
}

export function Login({ meta, metaError, onSignedIn }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [working, setWorking] = useState(false)
  const [message, setMessage] = useState('')
  const [tone, setTone] = useState<'error' | 'working'>('error')
  const emailBox = useRef<HTMLInputElement>(null)

  useEffect(() => {
    emailBox.current?.focus()
  }, [])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (working) return
    if (!email.trim() || !password) {
      setTone('error')
      setMessage('กรุณากรอกอีเมลและรหัสผ่าน / enter your email and password')
      return
    }
    setWorking(true)
    setTone('working')
    setMessage('กำลังเข้าสู่ระบบ / signing in...')
    try {
      const session = await signIn(email.trim(), password)
      onSignedIn(session)
    } catch (e) {
      setTone('error')
      /* The server's own sentence, in both languages, including the one that
       * matters most: after eight wrong guesses in fifteen minutes it answers
       * 429 and says how long to wait. Replacing that with "sign-in failed"
       * would leave somebody retrying a door that has already stopped
       * listening. */
      setMessage(
        e instanceof ApiError
          ? e.message
          : 'ต่อเซิร์ฟเวอร์ไม่ได้ / the server could not be reached',
      )
      setPassword('')
      setWorking(false)
    }
  }

  const title = meta?.labels.app_title ?? 'PantongOne'
  const subtitle = meta?.labels.app_subtitle ?? 'โปรแกรมคำนวณราคาพลาสติก / Plastic pricing'
  /* version_label, not version. The latter is a build string - it names a
   * source tree and a checksum - and thirty characters of that above a password
   * box is noise where the desktop printed one short line: "v1.7.1". */
  const version = meta?.version_label ?? ''
  const viaPacos = meta?.sign_in_with === 'pacos'

  return (
    <div className="gate">
      <form className="gate-card" onSubmit={submit}>
        <div className="gate-head">
          <img src={mark} alt="" width={64} height={64} />
          <div>
            {/* gate.py:125-152 - the name, what it does, then the version and
                WHICH HOST the password is about to go to, with the desktop's
                own two spaces around the bullet (gate.py:150). */}
            <h1>{title}</h1>
            <p className="gate-muted">{subtitle}</p>
            <p className="gate-muted gate-version">
              {version ? `${version}  •  ` : ''}
              {window.location.host}
            </p>
            {viaPacos && (
              <p className="gate-muted gate-with">
                ใช้อีเมลและรหัสผ่านของ PacOs / Sign in with your PacOs email and password
              </p>
            )}
          </div>
        </div>

        <label className="gate-row">
          <span>อีเมล / Email</span>
          <input
            ref={emailBox}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            spellCheck={false}
            disabled={working}
          />
        </label>

        <label className="gate-row">
          <span>รหัสผ่าน / Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={working}
          />
        </label>

        {/* Always in the layout, never a line that appears and shoves the
            buttons down the screen under somebody's finger (LAW P9). */}
        <p className={message ? `gate-message is-${tone}` : 'gate-message'}>{message || '\u00a0'}</p>

        {metaError && (
          <p className="gate-message is-error">
            {`ต่อเซิร์ฟเวอร์ไม่ได้ / cannot reach the server: ${metaError}`}
          </p>
        )}

        <div className="gate-foot">
          <span className="gate-muted">
            {viaPacos
              ? 'ยังไม่มีบัญชี PacOs ติดต่อผู้ดูแล PacOs / No PacOs account? ask the PacOs administrator'
              : 'ยังไม่มีบัญชี ติดต่อผู้ดูแล / No account? ask your administrator'}
          </span>
          <button type="submit" disabled={working}>
            {working ? 'กำลังเข้าสู่ระบบ / Signing in...' : 'เข้าสู่ระบบ / Sign in'}
          </button>
        </div>
      </form>
    </div>
  )
}
