import { useState } from 'react'
import { Brain, Lock, Mail, User, Eye, EyeOff } from 'lucide-react'
import { clsx } from 'clsx'

interface LoginPageProps {
  onLogin: (token: string, user: { id: string; email: string; name: string }) => void
  onSkip?: () => void
}

export default function LoginPage({ onLogin, onSkip }: LoginPageProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const body = mode === 'login'
        ? { email, password }
        : { email, password, name }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || 'Authentication failed')
        return
      }

      if (mode === 'register') {
        // After register, auto-login
        const loginRes = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        const loginData = await loginRes.json()
        if (loginRes.ok) {
          localStorage.setItem('cotrader_token', loginData.access_token)
          localStorage.setItem('cotrader_refresh', loginData.refresh_token)
          onLogin(loginData.access_token, loginData.user)
        } else {
          setError('Registered but login failed. Try logging in.')
        }
      } else {
        localStorage.setItem('cotrader_token', data.access_token)
        localStorage.setItem('cotrader_refresh', data.refresh_token)
        onLogin(data.access_token, data.user)
      }
    } catch (err) {
      setError('Connection failed. Is the server running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-purple-900/40 border border-purple-700 flex items-center justify-center mx-auto mb-4">
            <Brain size={32} className="text-purple-400" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary">CoTrader</h1>
          <p className="text-sm text-text-muted mt-1">Systematic Options Trading</p>
        </div>

        {/* Form */}
        <div className="border border-border-primary rounded-xl bg-bg-secondary/50 p-6">
          {/* Tabs */}
          <div className="flex gap-1 mb-6 bg-bg-tertiary rounded-lg p-1">
            <button
              onClick={() => { setMode('login'); setError('') }}
              className={clsx('flex-1 py-2 rounded text-xs font-semibold transition-all',
                mode === 'login' ? 'bg-accent-blue text-white' : 'text-text-muted hover:text-text-primary'
              )}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode('register'); setError('') }}
              className={clsx('flex-1 py-2 rounded text-xs font-semibold transition-all',
                mode === 'register' ? 'bg-accent-blue text-white' : 'text-text-muted hover:text-text-primary'
              )}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Name</label>
                <div className="relative">
                  <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                  <input
                    type="text"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="Your name"
                    className="w-full pl-9 pr-3 py-2.5 bg-bg-tertiary border border-border-secondary rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Email</label>
              <div className="relative">
                <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full pl-9 pr-3 py-2.5 bg-bg-tertiary border border-border-secondary rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Password</label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="w-full pl-9 pr-10 py-2.5 bg-bg-tertiary border border-border-secondary rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-red-400 text-xs bg-red-950/20 border border-red-900/30 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className={clsx(
                'w-full py-2.5 rounded-lg text-sm font-semibold transition-all',
                loading ? 'bg-accent-blue/50 text-white/50' : 'bg-accent-blue text-white hover:bg-accent-blue/90',
              )}
            >
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>

        {/* Skip */}
        {onSkip && (
          <button
            onClick={onSkip}
            className="w-full mt-3 py-2 text-xs text-text-muted hover:text-text-primary transition-colors"
          >
            Continue without login →
          </button>
        )}

        {/* Footer */}
        <p className="text-center text-[10px] text-text-muted mt-4">
          Capital preservation first. Every trade has a reason.
        </p>
      </div>
    </div>
  )
}
