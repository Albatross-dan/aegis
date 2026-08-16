import { useEffect, useState } from 'react'

interface HealthStatus {
  status: string
  database: string
}

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch(() => setError('Could not reach AEGIS backend'))
  }, [])

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center gap-4">
      <h1 className="text-4xl font-bold tracking-wide">AEGIS</h1>
      <p className="text-slate-400 italic">
        Observe. Understand. Reason. Protect. Execute. Learn. Improve.
      </p>

      <div className="mt-8 p-6 rounded-lg bg-slate-800 border border-slate-700 w-80">
        <h2 className="text-lg font-semibold mb-2">System Status</h2>
        {error && <p className="text-red-400">{error}</p>}
        {health && (
          <div className="space-y-1 text-sm">
            <p>
              API: <span className="text-green-400">{health.status}</span>
            </p>
            <p>
              Database: <span className="text-green-400">{health.database}</span>
            </p>
          </div>
        )}
        {!health && !error && <p className="text-slate-400">Connecting...</p>}
      </div>
    </div>
  )
}

export default App
