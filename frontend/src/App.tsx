import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppDispatch, useAppSelector } from './app/hooks'
import { store } from './app/store'
import { ask, abortAsk } from './features/askStream'
import { setToken, TOKEN_KEY } from './features/authSlice'
import { authApi, useMeQuery } from './features/authApi'
import { historyApi, useGetConversationsQuery, useLazyGetConversationQuery } from './features/historyApi'
import { goHome, reset } from './features/streamSlice'
import AuthModal from './components/AuthModal'
import DeepToggle from './components/DeepToggle'
import FeedBlock from './components/FeedBlock'
import type { FeedItem } from './components/FeedBlock'
import HistorySidebar from './components/HistorySidebar'
import LandingView from './components/LandingView'
import ProfileModal from './components/ProfileModal'
import ThemeToggle from './components/ThemeToggle'

let blockSeq = 0
function nextBlockId() {
  blockSeq += 1
  return `block-${Date.now()}-${blockSeq}`
}

function streamErrorMessage(error: string) {
  if (error === 'auth_required') return 'Sign in to ask questions.'
  if (error === 'rate_limited') return 'The research service is temporarily rate-limited. Try again in a few minutes.'
  if (error === 'question_invalid') return 'That question was too long or empty.'
  if (error === 'backend_status_404') return 'That chat no longer exists. Start a new chat.'
  if (error === 'stream_ended') return 'The connection dropped before the answer finished. Ask again.'
  if (error === 'stream_stalled') return 'The connection stalled. Ask again.'
  if (error === 'save_failed') return 'The answer finished but could not be saved to your history.'
  return `I could not reach the local AskKara backend. (${error})`
}

export default function App() {
  const dispatch = useAppDispatch()
  const stream = useAppSelector((state) => state.stream)
  const token = useAppSelector((state) => state.auth.token)

  const [archive, setArchive] = useState<FeedItem[]>([])
  const [liveItem, setLiveItem] = useState<FeedItem | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [online, setOnline] = useState(true)
  const archiveGen = useRef(0)
  const feedRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = feedRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'instant' })
  }, [archive, liveItem])

  useEffect(() => {
    if (stream.status !== 'running') return
    const el = feedRef.current
    if (!el) return
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 160) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'instant' })
    }
  }, [stream.answer, stream.status])

  useEffect(() => {
    let alive = true
    async function check() {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 5000)
      try {
        const res = await fetch('/api/health', { signal: ctrl.signal })
        if (alive) setOnline(res.ok)
      } catch {
        if (alive) setOnline(false)
      } finally {
        clearTimeout(timer)
      }
    }
    check()
    const id = setInterval(check, 30000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  const { data: me, error: meError } = useMeQuery(undefined, { skip: !token })
  const { data: conversations } = useGetConversationsQuery(undefined, { skip: !token })
  const [fetchConversation] = useLazyGetConversationQuery()

  const running = stream.status === 'running'

  const applyAuth = useCallback(
    (value: string) => {
      abortAsk()
      dispatch(setToken(value))
      if (value) {
        localStorage.setItem(TOKEN_KEY, value)
      } else {
        localStorage.removeItem(TOKEN_KEY)
      }
      dispatch(authApi.util.resetApiState())
      dispatch(historyApi.util.resetApiState())
      dispatch(reset())
      archiveGen.current += 1
      setArchive([])
      setConversationId(null)
    },
    [dispatch],
  )

  const meStatus = meError && typeof meError === 'object' && 'status' in meError ? meError.status : undefined
  useEffect(() => {
    if (!token || meStatus !== 401) return
    abortAsk()
    dispatch(setToken(''))
    localStorage.removeItem(TOKEN_KEY)
    dispatch(authApi.util.resetApiState())
    dispatch(historyApi.util.resetApiState())
    dispatch(reset())
  }, [token, meStatus, dispatch])

  const startAsk = useCallback(
    (question: string) => {
      if (stream.status === 'running') return false
      const id = nextBlockId()
      const gen = archiveGen.current
      setLiveItem({ id, question })
      dispatch(ask(question, conversationId)).then(() => {
        const final = store.getState().stream
        if (gen !== archiveGen.current) {
          setLiveItem(null)
          dispatch(reset())
          return
        }
        if (final.status === 'done' || final.status === 'error') {
          setArchive((items) => [
            ...items,
            {
              id,
              question: final.question,
              answer: final.status === 'done' ? final.answer : '',
              sources: final.sources,
              instant: final.streamed,
              error: final.status === 'error' ? streamErrorMessage(final.error) : undefined,
            },
          ])
          if (store.getState().auth.token) dispatch(historyApi.util.invalidateTags(['History']))
        }
        if (final.status === 'done' && final.conversationId) setConversationId(final.conversationId)
        if (final.error === 'auth_required') setAuthOpen(true)
        setLiveItem(null)
        dispatch(reset())
      })
      return true
    },
    [dispatch, stream.status, conversationId],
  )

  const sidebarItems = (conversations?.items ?? []).map((item) => ({ id: `conv-${item.id}`, title: item.title }))

  function startNewChat() {
    setSidebarOpen(false)
    abortAsk()
    archiveGen.current += 1
    setConversationId(null)
    setArchive([])
    setLiveItem(null)
    dispatch(goHome())
  }

  function openConversation(id: string) {
    setSidebarOpen(false)
    const numericId = Number(id.replace('conv-', ''))
    if (!Number.isFinite(numericId)) return
    abortAsk()
    archiveGen.current += 1
    const gen = archiveGen.current
    setLiveItem(null)
    dispatch(reset())
    fetchConversation(numericId)
      .unwrap()
      .then((data) => {
        if (gen !== archiveGen.current) return
        setArchive(
          data.items.map((turn) => ({
            id: `turn-${turn.id}`,
            question: turn.question,
            answer: turn.answer,
            sources: turn.sources,
            instant: true,
          })),
        )
        setConversationId(numericId)
        setLiveItem(null)
      })
      .catch(() => {})
  }

  const showLanding = archive.length === 0 && liveItem === null

  return (
    <>
      <div className="noise" />
      <div className="ambient-glow" />

      <header className="header">
        <div
          className="brand"
          onClick={() => {
            abortAsk()
            archiveGen.current += 1
            setArchive([])
            setLiveItem(null)
            setConversationId(null)
            dispatch(goHome())
          }}
        >
          kara<span className={`brand-dot${online ? '' : ' offline'}`}>.</span>
        </div>
        <div className="header-right">
          {token ? (
            <>
              <button className="menu-btn" onClick={() => setSidebarOpen(true)}>
                HISTORY
              </button>
              <button
                className="avatar-btn"
                onClick={() => setProfileOpen(true)}
                aria-label="Account"
              >
                {(me?.email ?? '?').charAt(0).toUpperCase()}
              </button>
            </>
          ) : (
            <button className="menu-btn" onClick={() => setAuthOpen(true)}>
              SIGN IN
            </button>
          )}
        </div>
      </header>

      <HistorySidebar
        open={sidebarOpen}
        items={sidebarItems}
        onClose={() => setSidebarOpen(false)}
        onOpen={openConversation}
        onNew={startNewChat}
      />

      <main className="container">
        {showLanding ? (
          <LandingView onAsk={startAsk} />
        ) : (
          <section className="section-results active" ref={feedRef}>
            <div className="feed-container">
              {(liveItem ? [...archive, liveItem] : archive).map((item) => {
                const isLive = item.id === liveItem?.id
                return (
                  <FeedBlock
                    key={item.id}
                    item={item}
                    stage={isLive ? stream.stage : undefined}
                    liveText={isLive ? stream.answer : undefined}
                    steps={isLive ? stream.steps : undefined}
                  />
                )
              })}
            </div>
            <div className="followup-wrapper">
              <div className="followup-line">
                <FollowupInput busy={running} onSubmit={startAsk} />
                <DeepToggle />
              </div>
            </div>
          </section>
        )}
      </main>

      <ThemeToggle />
      {authOpen ? (
        <AuthModal
          onClose={() => setAuthOpen(false)}
          onAuth={(value) => {
            applyAuth(value)
            setAuthOpen(false)
          }}
        />
      ) : null}
      {profileOpen ? (
        <ProfileModal
          email={me?.email ?? ''}
          onClose={() => setProfileOpen(false)}
          onSignOut={() => {
            applyAuth('')
            setProfileOpen(false)
          }}
        />
      ) : null}
    </>
  )
}

function FollowupInput({
  busy,
  onSubmit,
}: {
  busy: boolean
  onSubmit: (question: string) => boolean
}) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (window.matchMedia('(pointer: fine)').matches) inputRef.current?.focus()
  }, [])

  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    const trimmed = value.trim()
    if (!trimmed) return
    if (!onSubmit(trimmed)) return
    setValue('')
  }

  return (
    <form onSubmit={submit}>
      <input
        ref={inputRef}
        type="text"
        className="input-followup"
        placeholder={busy ? 'Researching...' : 'Dig deeper...'}
        autoComplete="off"
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
    </form>
  )
}
