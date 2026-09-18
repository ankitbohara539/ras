import { useEffect, useState } from 'react'
import { getHealth, type HealthResponse } from './lib/api'

type ApiState =
  | { kind: 'loading' }
  | { kind: 'ready'; health: HealthResponse }
  | { kind: 'error' }

const technologies = ['React', 'Tailwind CSS', 'FastAPI', 'Supabase']

function App() {
  const [api, setApi] = useState<ApiState>({ kind: 'loading' })

  useEffect(() => {
    getHealth()
      .then((health) => setApi({ kind: 'ready', health }))
      .catch(() => setApi({ kind: 'error' }))
  }, [])

  const isOnline = api.kind === 'ready'
  const statusLabel =
    api.kind === 'loading'
      ? 'Connecting to API'
      : isOnline
        ? 'All systems operational'
        : 'Backend is offline'

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-6 py-16 text-white">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-0 h-[420px] w-[700px] -translate-x-1/2 rounded-full bg-cyan-500/10 blur-[120px]" />
        <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-indigo-500/10 blur-[100px]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
      </div>

      <section className="relative mx-auto flex w-full max-w-4xl flex-col items-center text-center">
        {/* <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 shadow-lg shadow-black/10 backdrop-blur-sm">
          <span
            className={`h-2 w-2 rounded-full ${
              api.kind === 'loading'
                ? 'animate-pulse bg-amber-400'
                : isOnline
                  ? 'bg-emerald-400'
                  : 'bg-rose-400'
            }`}
          />
          {statusLabel}
        </div> */}

        <p className="mb-5 text-sm font-semibold uppercase tracking-[0.32em] text-cyan-300">
          Team RAS
        </p>

        <h1 className="max-w-4xl text-balance text-5xl font-bold leading-[1.08] tracking-[-0.04em] sm:text-7xl lg:text-8xl">
          Let&apos;s build something{' '}
          <span className="bg-gradient-to-r from-cyan-300 via-sky-400 to-indigo-400 bg-clip-text text-transparent">
            remarkable.
          </span>
        </h1>

       

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          {technologies.map((technology) => (
            <span
              key={technology}
              className="rounded-full border border-slate-800 bg-slate-900/70 px-4 py-2 text-sm font-medium text-slate-300 backdrop-blur"
            >
              {technology}
            </span>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center gap-4 sm:flex-row">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="group inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3.5 text-sm font-semibold text-slate-950 shadow-xl shadow-white/5 transition hover:-translate-y-0.5 hover:bg-cyan-50"
          >
            Explore the API
            <svg
              viewBox="0 0 20 20"
              fill="none"
              aria-hidden="true"
              className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
            >
              <path
                d="M4.167 10h11.666m-4.166-4.167L15.833 10l-4.166 4.167"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>

          <a
            href="https://supabase.com/dashboard"
            target="_blank"
            rel="noreferrer"
            className="rounded-xl border border-white/10 bg-white/[0.04] px-6 py-3.5 text-sm font-semibold text-slate-200 transition hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.08]"
          >
            Open Supabase
          </a>
        </div>

       
      </section>
    </main>
  )
}

export default App
