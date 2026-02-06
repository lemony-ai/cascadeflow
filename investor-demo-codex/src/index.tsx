import React, { useEffect, useMemo, useRef, useState } from 'react'

type ProviderMode = 'openai' | 'anthropic' | 'mixed'
type Stage = 'welcome' | 'select' | 'running' | 'summary'

type SimEvent =
  | {
      t: number
      kind: 'log'
      message: string
    }
  | {
      t: number
      kind: 'cost'
      deltaBaselineUsd: number
      deltaCascadeUsd: number
    }
  | {
      t: number
      kind: 'stat'
      accepted: boolean
      provider: 'openai' | 'anthropic'
      tokens: number
      latencyMs: number
    }
  | {
      t: number
      kind: 'done'
    }

const ASCII_LOGO = String.raw`
   ____               __          __
  / __/__ ____ ____ _/ /__ ____  / /__
 _\ \/ _ \/ __/ _ \/ / _ \/ __/ / / _ \
/___/\___/_/  \___/_/\___/_/   /_/\___/

           cascadeflow investor demo
`

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n))
}

function usd(n: number): string {
  return n.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 4,
  })
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`
}

function nowMs(): number {
  return performance.now()
}

function useInterval(callback: () => void, delayMs: number | null): void {
  const saved = useRef(callback)
  useEffect(() => {
    saved.current = callback
  }, [callback])
  useEffect(() => {
    if (delayMs === null) return
    const id = window.setInterval(() => saved.current(), delayMs)
    return () => window.clearInterval(id)
  }, [delayMs])
}

function Spinner({ label }: { label: string }) {
  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
  const [i, setI] = useState(0)
  useInterval(() => setI((x) => (x + 1) % frames.length), 90)
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
      <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>{frames[i]}</span>
      <span>{label}</span>
    </div>
  )
}

function buildSimulation(mode: ProviderMode): SimEvent[] {
  // A deterministic(ish) script: time offsets in ms.
  // Baseline is “single strong model”; cascade is “draft + verify + fallback”.
  // The numbers are illustrative and not tied to any real provider pricing.
  const providerForStep = (step: number): 'openai' | 'anthropic' => {
    if (mode === 'openai') return 'openai'
    if (mode === 'anthropic') return 'anthropic'
    return step % 2 === 0 ? 'openai' : 'anthropic'
  }

  const events: SimEvent[] = []
  let t = 0
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const push = (e: any, dt: number) => {
    t += dt
    events.push({ ...e, t } as SimEvent)
  }

  push({ kind: 'log', message: 'Initializing cascade…' }, 200)
  push({ kind: 'log', message: 'Loading routing table (domains, tools)…' }, 450)
  push({ kind: 'log', message: 'Warming providers…' }, 400)

  // Simulate 10 queries.
  for (let i = 1; i <= 10; i++) {
    const provider = providerForStep(i)
    const accepted = i % 4 !== 0 // every 4th query rejects draft
    const tokens = 550 + i * 35
    const latencyMs = 420 + i * 55 + (accepted ? 0 : 260)

    push({ kind: 'log', message: `Query ${i}/10 → draft (${provider})` }, 260)

    // Costs: baseline is always higher; cascade is lower when accepted.
    const baseline = 0.0062 + i * 0.00035
    const cascade = accepted ? baseline * (0.42 + (i % 3) * 0.03) : baseline * 0.95

    push({ kind: 'cost', deltaBaselineUsd: baseline, deltaCascadeUsd: cascade }, 220)
    push({ kind: 'stat', accepted, provider, tokens, latencyMs }, 200)

    if (!accepted) {
      push({ kind: 'log', message: `Query ${i}/10 → fallback verify (strong model)` }, 220)
      push({ kind: 'log', message: 'Alignment low; rerouting to stronger tier…' }, 260)
    }
  }

  push({ kind: 'log', message: 'Computing summary…' }, 400)
  push({ kind: 'done' }, 250)
  return events
}

export function App() {
  const [stage, setStage] = useState<Stage>('welcome')
  const [providerMode, setProviderMode] = useState<ProviderMode>('mixed')

  const [logLines, setLogLines] = useState<string[]>([])
  const [baselineUsd, setBaselineUsd] = useState(0)
  const [cascadeUsd, setCascadeUsd] = useState(0)
  const [acceptedCount, setAcceptedCount] = useState(0)
  const [rejectedCount, setRejectedCount] = useState(0)
  const [openaiCount, setOpenaiCount] = useState(0)
  const [anthropicCount, setAnthropicCount] = useState(0)
  const [totalTokens, setTotalTokens] = useState(0)
  const [latencyMsTotal, setLatencyMsTotal] = useState(0)
  const [eventsApplied, setEventsApplied] = useState(0)

  const script = useMemo(() => buildSimulation(providerMode), [providerMode])
  const runStartRef = useRef<number | null>(null)
  const rafRef = useRef<number | null>(null)

  const savingsUsd = baselineUsd - cascadeUsd
  const savingsRate = baselineUsd > 0 ? clamp(savingsUsd / baselineUsd, 0, 1) : 0

  const reset = () => {
    setLogLines([])
    setBaselineUsd(0)
    setCascadeUsd(0)
    setAcceptedCount(0)
    setRejectedCount(0)
    setOpenaiCount(0)
    setAnthropicCount(0)
    setTotalTokens(0)
    setLatencyMsTotal(0)
    setEventsApplied(0)
    runStartRef.current = null
  }

  const startRun = () => {
    reset()
    setStage('running')
    runStartRef.current = nowMs()
  }

  useEffect(() => {
    if (stage !== 'running') return
    const start = runStartRef.current ?? nowMs()

    const tick = () => {
      const elapsed = nowMs() - start

      // Apply all events whose time has passed.
      let idx = eventsApplied
      while (idx < script.length && script[idx].t <= elapsed) {
        const ev = script[idx]
        if (ev.kind === 'log') {
          setLogLines((prev) => {
            const next = [...prev, ev.message]
            return next.slice(-14)
          })
        } else if (ev.kind === 'cost') {
          setBaselineUsd((v) => v + ev.deltaBaselineUsd)
          setCascadeUsd((v) => v + ev.deltaCascadeUsd)
        } else if (ev.kind === 'stat') {
          setTotalTokens((v) => v + ev.tokens)
          setLatencyMsTotal((v) => v + ev.latencyMs)
          if (ev.provider === 'openai') setOpenaiCount((v) => v + 1)
          else setAnthropicCount((v) => v + 1)
          if (ev.accepted) setAcceptedCount((v) => v + 1)
          else setRejectedCount((v) => v + 1)
        } else if (ev.kind === 'done') {
          setStage('summary')
        }
        idx++
      }
      if (idx !== eventsApplied) setEventsApplied(idx)

      if (stage === 'running') {
        rafRef.current = window.requestAnimationFrame(tick)
      }
    }

    rafRef.current = window.requestAnimationFrame(tick)
    return () => {
      if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, script, eventsApplied])

  const container: React.CSSProperties = {
    minHeight: '100vh',
    background: 'radial-gradient(1200px 600px at 20% 10%, #0b1b2b 0%, #06080c 55%, #050608 100%)',
    color: '#e6edf3',
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  }

  const card: React.CSSProperties = {
    width: 'min(980px, 100%)',
    background: 'rgba(10, 12, 16, 0.7)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: 16,
    boxShadow: '0 20px 80px rgba(0,0,0,0.45)',
    overflow: 'hidden',
  }

  const header: React.CSSProperties = {
    padding: '18px 20px',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
    display: 'flex',
    gap: 12,
    alignItems: 'center',
    justifyContent: 'space-between',
  }

  const badge: React.CSSProperties = {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    fontSize: 12,
    padding: '4px 10px',
    borderRadius: 999,
    border: '1px solid rgba(255,255,255,0.14)',
    color: '#c9d1d9',
    background: 'rgba(255,255,255,0.04)',
    whiteSpace: 'nowrap',
  }

  const body: React.CSSProperties = {
    padding: 20,
    display: 'grid',
    gridTemplateColumns: '1.1fr 0.9fr',
    gap: 18,
  }

  const panel: React.CSSProperties = {
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 14,
    padding: 16,
    background: 'rgba(255,255,255,0.03)',
  }

  const mono: React.CSSProperties = {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  }

  const button: React.CSSProperties = {
    border: '1px solid rgba(255,255,255,0.16)',
    background: 'rgba(255,255,255,0.06)',
    color: '#e6edf3',
    padding: '10px 14px',
    borderRadius: 12,
    cursor: 'pointer',
    fontWeight: 600,
  }

  const primaryButton: React.CSSProperties = {
    ...button,
    background: 'linear-gradient(180deg, rgba(88,166,255,0.22), rgba(88,166,255,0.10))',
    border: '1px solid rgba(88,166,255,0.35)',
  }

  const smallMuted: React.CSSProperties = {
    fontSize: 12,
    color: 'rgba(230,237,243,0.72)',
    lineHeight: 1.4,
  }

  const selectRow: React.CSSProperties = {
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap',
  }

  const modeButton = (mode: ProviderMode, title: string, subtitle: string) => {
    const active = providerMode === mode
    const style: React.CSSProperties = {
      ...button,
      textAlign: 'left',
      minWidth: 200,
      background: active
        ? 'linear-gradient(180deg, rgba(46,160,67,0.24), rgba(46,160,67,0.10))'
        : button.background,
      border: active ? '1px solid rgba(46,160,67,0.45)' : button.border,
    }
    return (
      <button key={mode} style={style} onClick={() => setProviderMode(mode)}>
        <div style={{ fontWeight: 700 }}>{title}</div>
        <div style={smallMuted}>{subtitle}</div>
      </button>
    )
  }

  const costBarWidth = `${(savingsRate * 100).toFixed(1)}%`

  return (
    <div style={container}>
      <div style={card}>
        <div style={header}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <div style={{ ...mono, fontWeight: 800, letterSpacing: 0.2 }}>cascadeflow</div>
            <div style={badge}>@cascadeflow/demo-codex</div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {stage !== 'welcome' && (
              <button
                style={button}
                onClick={() => {
                  reset()
                  setStage('select')
                }}
              >
                Reset
              </button>
            )}
            {stage === 'summary' && (
              <button style={primaryButton} onClick={startRun}>
                Run again
              </button>
            )}
          </div>
        </div>

        <div style={body}>
          <div style={panel}>
            {stage === 'welcome' && (
              <div>
                <pre
                  style={{
                    ...mono,
                    margin: 0,
                    padding: 16,
                    borderRadius: 12,
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: 'rgba(0,0,0,0.25)',
                    overflowX: 'auto',
                    whiteSpace: 'pre',
                  }}
                >
                  {ASCII_LOGO}
                </pre>
                <div style={{ marginTop: 14, ...smallMuted }}>
                  A lightweight, terminal-inspired UI that mocks a cascade run: draft → verify → fallback.
                  Select a provider mode and watch cost savings update in real time.
                </div>
                <div style={{ marginTop: 16, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button style={primaryButton} onClick={() => setStage('select')}>
                    Start
                  </button>
                  <button
                    style={button}
                    onClick={() => {
                      setProviderMode('mixed')
                      setStage('select')
                    }}
                  >
                    Quick run (Mixed)
                  </button>
                </div>
              </div>
            )}

            {stage === 'select' && (
              <div>
                <div style={{ fontWeight: 800, fontSize: 16 }}>Provider selection</div>
                <div style={{ marginTop: 6, ...smallMuted }}>
                  This demo simulates routing decisions and acceptance/rejection rates.
                </div>

                <div style={{ marginTop: 14, ...selectRow }}>
                  {modeButton('openai', 'OpenAI', 'Single-provider cascade')}
                  {modeButton('anthropic', 'Anthropic', 'Single-provider cascade')}
                  {modeButton('mixed', 'Mixed', 'Route per-step across providers')}
                </div>

                <div style={{ marginTop: 16, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button style={primaryButton} onClick={startRun}>
                    Run mock cascade
                  </button>
                  <button style={button} onClick={() => setStage('welcome')}>
                    Back
                  </button>
                </div>
              </div>
            )}

            {stage === 'running' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: 16 }}>Mock cascade simulation</div>
                    <div style={{ marginTop: 6, ...smallMuted }}>
                      Mode: <span style={mono}>{providerMode}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <Spinner label="Routing" />
                    <Spinner label="Scoring" />
                    <Spinner label="Budget" />
                  </div>
                </div>

                <div
                  style={{
                    marginTop: 14,
                    padding: 14,
                    borderRadius: 12,
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: 'rgba(0,0,0,0.25)',
                    ...mono,
                    minHeight: 220,
                  }}
                >
                  {logLines.length === 0 ? (
                    <div style={{ opacity: 0.85 }}>…</div>
                  ) : (
                    logLines.map((l, i) => (
                      <div key={i}>
                        <span style={{ opacity: 0.65 }}>$</span> {l}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {stage === 'summary' && (
              <div>
                <div style={{ fontWeight: 800, fontSize: 16 }}>Summary</div>
                <div style={{ marginTop: 6, ...smallMuted }}>
                  Mocked run complete — these metrics are illustrative.
                </div>

                <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div style={{ ...panel, margin: 0 }}>
                    <div style={{ fontWeight: 700 }}>Savings</div>
                    <div style={{ marginTop: 8, fontSize: 22, fontWeight: 900 }}>{usd(savingsUsd)}</div>
                    <div style={{ ...smallMuted, marginTop: 4 }}>Cost reduction: {pct(savingsRate)}</div>
                  </div>
                  <div style={{ ...panel, margin: 0 }}>
                    <div style={{ fontWeight: 700 }}>Acceptance</div>
                    <div style={{ marginTop: 8, fontSize: 22, fontWeight: 900 }}>
                      {acceptedCount}/{acceptedCount + rejectedCount}
                    </div>
                    <div style={{ ...smallMuted, marginTop: 4 }}>
                      Rejections (fallback): {rejectedCount}
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 12, ...panel }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>Providers</div>
                      <div style={{ ...smallMuted, marginTop: 4 }}>
                        OpenAI steps: <span style={mono}>{openaiCount}</span> · Anthropic steps:{' '}
                        <span style={mono}>{anthropicCount}</span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 700 }}>Avg latency</div>
                      <div style={{ ...smallMuted, marginTop: 4 }}>
                        {(latencyMsTotal / Math.max(1, acceptedCount + rejectedCount)).toFixed(0)} ms / query
                      </div>
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button style={primaryButton} onClick={startRun}>
                    Run again
                  </button>
                  <button style={button} onClick={() => setStage('select')}>
                    Change providers
                  </button>
                </div>
              </div>
            )}
          </div>

          <div style={panel}>
            <div style={{ fontWeight: 800, fontSize: 16 }}>Real-time costs</div>
            <div style={{ marginTop: 6, ...smallMuted }}>
              Baseline = single strong model. Cascade = draft + verify + fallback.
            </div>

            <div style={{ marginTop: 14, display: 'grid', gap: 10 }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 700 }}>Baseline</div>
                  <div style={{ ...mono }}>{usd(baselineUsd)}</div>
                </div>
                <div style={{ ...smallMuted, marginTop: 2 }}>Strong model only</div>
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 700 }}>Cascade</div>
                  <div style={{ ...mono }}>{usd(cascadeUsd)}</div>
                </div>
                <div style={{ ...smallMuted, marginTop: 2 }}>Draft acceptance drives savings</div>
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 700 }}>Savings</div>
                  <div style={{ ...mono }}>{usd(savingsUsd)}</div>
                </div>
                <div style={{ ...smallMuted, marginTop: 2 }}>{pct(savingsRate)} reduction</div>
              </div>
            </div>

            <div style={{ marginTop: 14 }}>
              <div style={{ ...smallMuted, marginBottom: 8 }}>Savings meter</div>
              <div
                style={{
                  height: 12,
                  borderRadius: 999,
                  border: '1px solid rgba(255,255,255,0.10)',
                  background: 'rgba(255,255,255,0.05)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: costBarWidth,
                    height: '100%',
                    background: 'linear-gradient(90deg, rgba(46,160,67,0.65), rgba(88,166,255,0.65))',
                    transition: 'width 220ms ease',
                  }}
                />
              </div>
            </div>

            <div style={{ marginTop: 16, ...panel, background: 'rgba(0,0,0,0.18)' }}>
              <div style={{ fontWeight: 800 }}>Run stats</div>
              <div style={{ marginTop: 8, display: 'grid', gap: 6, ...mono }}>
                <div>events applied: {eventsApplied}/{script.length}</div>
                <div>draft accepted: {acceptedCount}</div>
                <div>fallbacks: {rejectedCount}</div>
                <div>tokens (mock): {totalTokens.toLocaleString()}</div>
              </div>
            </div>

            {stage !== 'running' && (
              <div style={{ marginTop: 14, ...smallMuted }}>
                Tip: click “Run mock cascade” to see spinners + live updates.
              </div>
            )}
          </div>
        </div>

        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid rgba(255,255,255,0.08)',
            display: 'flex',
            justifyContent: 'space-between',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <div style={smallMuted}>
            Demo UI only — no API keys, no network calls.
          </div>
          {stage === 'welcome' && (
            <button style={button} onClick={() => setStage('select')}>
              Continue
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

