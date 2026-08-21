import { useEffect, useState } from 'react'

interface HealthStatus {
  status: string
  database: string
}

interface PriceRow {
  symbol: string
  bid: number
  ask: number
  timestamp: string
}

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [prices, setPrices] = useState<PriceRow[]>([])
  const [pricesError, setPricesError] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch(() => setError('Could not reach AEGIS backend'))
  }, [])

  useEffect(() => {
    const fetchPrices = () => {
      fetch('http://localhost:8000/api/v1/prices/latest')
        .then((res) => res.json())
        .then((data) => {
          setPrices(data.prices)
          setPricesError(null)
        })
        .catch(() => setPricesError('Could not reach price feed'))
    }

    fetchPrices()
    const interval = setInterval(fetchPrices, 3000)
    return () => clearInterval(interval)
  }, [])

  const decimalsFor = (symbol: string) => (symbol.includes('JPY') ? 3 : 5)

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center gap-4 py-12">
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

      <div className="mt-4 p-6 rounded-lg bg-slate-800 border border-slate-700 w-[480px]">
        <h2 className="text-lg font-semibold mb-4">Live Prices</h2>
        {pricesError && <p className="text-red-400">{pricesError}</p>}
        {!pricesError && prices.length === 0 && (
          <p className="text-slate-400">Loading prices...</p>
        )}
        {prices.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700">
                <th className="text-left pb-2">Symbol</th>
                <th className="text-right pb-2">Bid</th>
                <th className="text-right pb-2">Ask</th>
                <th className="text-right pb-2">Spread</th>
              </tr>
            </thead>
            <tbody>
              {[...prices]
                .sort((a, b) => a.symbol.localeCompare(b.symbol))
                .map((row) => {
                  const decimals = decimalsFor(row.symbol)
                  const spread = (row.ask - row.bid).toFixed(decimals)
                  return (
                    <tr key={row.symbol} className="border-b border-slate-800">
                      <td className="py-1 font-medium">{row.symbol}</td>
                      <td className="py-1 text-right text-green-400">
                        {row.bid.toFixed(decimals)}
                      </td>
                      <td className="py-1 text-right text-red-400">
                        {row.ask.toFixed(decimals)}
                      </td>
                      <td className="py-1 text-right text-slate-400">{spread}</td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default App
