import React, { useState } from 'react';
import { HeartPulse, Lock, User, Mail, LogIn, UserPlus, AlertCircle } from 'lucide-react';
import { login, register } from './api';

interface AuthViewProps {
  onAuthSuccess: (token: string) => void;
}

export const AuthView: React.FC<AuthViewProps> = ({ onAuthSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        const token = await login(username, password);
        onAuthSuccess(token);
      } else {
        const token = await register(username, password, email);
        onAuthSuccess(token);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const fillQuickDemoUser = () => {
    setUsername('testuser_qa');
    setPassword('testpass123');
    setIsLogin(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4 selection:bg-teal-500 selection:text-white">
      <div className="w-full max-w-md glass-panel p-8 rounded-3xl border border-slate-800 shadow-2xl relative overflow-hidden">
        {/* Decorative background glow */}
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="p-3.5 rounded-2xl bg-gradient-to-tr from-teal-600 to-cyan-400 text-slate-950 shadow-lg shadow-teal-500/20 mb-3">
            <HeartPulse className="w-8 h-8 stroke-[2.5]" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            MedGuardian<span className="text-teal-400 ml-0.5">AI</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Clinical Decision Support & Medication Digital Twin
          </p>
        </div>

        {/* Form Mode Selector */}
        <div className="flex bg-slate-900/80 p-1 rounded-xl border border-slate-800 mb-6">
          <button
            type="button"
            onClick={() => { setIsLogin(true); setError(''); }}
            className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${
              isLogin
                ? 'bg-teal-500/10 text-teal-300 border border-teal-500/30 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setIsLogin(false); setError(''); }}
            className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${
              !isLogin
                ? 'bg-teal-500/10 text-teal-300 border border-teal-500/30 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Register Patient
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Username</label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-all"
              />
            </div>
          </div>

          {!isLogin && (
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Email Address (Optional)</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="patient@example.com"
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-all"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password (min 8 chars)"
                className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-all"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-teal-500/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50 mt-2"
          >
            {loading ? (
              <span className="animate-pulse">Authenticating...</span>
            ) : isLogin ? (
              <>
                <LogIn className="w-4 h-4" /> Sign In
              </>
            ) : (
              <>
                <UserPlus className="w-4 h-4" /> Create Account
              </>
            )}
          </button>
        </form>

        {/* Demo Quick Fill Helper */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 flex flex-col items-center">
          <span className="text-[11px] text-slate-500 mb-2">Quick Demo Account:</span>
          <button
            type="button"
            onClick={fillQuickDemoUser}
            className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-teal-300 border border-slate-800 rounded-lg text-xs font-mono transition-all flex items-center gap-1.5"
          >
            <span>Fill Demo Credentials (testuser_qa)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
