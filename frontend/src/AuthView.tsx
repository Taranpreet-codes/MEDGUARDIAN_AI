import React, { useState } from 'react';
import { HeartPulse, Lock, User, Mail, LogIn, UserPlus, AlertCircle, Sun, Moon } from 'lucide-react';
import { login, register } from './api';

interface AuthViewProps {
  onAuthSuccess: (token: string) => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export const AuthView: React.FC<AuthViewProps> = ({ onAuthSuccess, theme, onToggleTheme }) => {
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
    <div className={`min-h-screen flex items-center justify-center p-4 selection:bg-teal-500 selection:text-white transition-colors duration-300 ${theme === 'dark' ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      <div className="w-full max-w-md panel-surface p-8 rounded-3xl shadow-2xl relative overflow-hidden">
        
        {/* Theme Switcher in top right */}
        <div className="absolute top-5 right-5 z-10">
          <button
            onClick={onToggleTheme}
            className={`p-2 rounded-xl border transition-all ${
              theme === 'dark'
                ? 'bg-slate-900 border-slate-800 text-amber-400 hover:bg-slate-800'
                : 'bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200'
            }`}
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>

        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="p-3.5 rounded-2xl bg-gradient-to-tr from-teal-600 to-cyan-400 text-slate-950 shadow-lg shadow-teal-500/20 mb-3">
            <HeartPulse className="w-8 h-8 stroke-[2.5]" />
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight">
            MedGuardian<span className="text-teal-500 ml-0.5">AI</span>
          </h1>
          <p className={`text-xs mt-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
            Clinical Decision Support & Medication Digital Twin
          </p>
        </div>

        {/* Form Mode Selector */}
        <div className={`flex p-1 rounded-xl border mb-6 ${theme === 'dark' ? 'bg-slate-900/80 border-slate-800' : 'bg-slate-100 border-slate-200'}`}>
          <button
            type="button"
            onClick={() => { setIsLogin(true); setError(''); }}
            className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
              isLogin
                ? 'bg-teal-500/10 text-teal-500 border border-teal-500/30 shadow-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setIsLogin(false); setError(''); }}
            className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
              !isLogin
                ? 'bg-teal-500/10 text-teal-500 border border-teal-500/30 shadow-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Register Patient
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={`block text-xs font-semibold mb-1.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>Username</label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                className={`w-full border rounded-xl pl-9 pr-3.5 py-2 text-xs focus:outline-none focus:border-teal-500 transition-all ${
                  theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-100 placeholder-slate-500' : 'bg-white border-slate-200 text-slate-900 placeholder-slate-400'
                }`}
              />
            </div>
          </div>

          {!isLogin && (
            <div>
              <label className={`block text-xs font-semibold mb-1.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>Email Address (Optional)</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="patient@example.com"
                  className={`w-full border rounded-xl pl-9 pr-3.5 py-2 text-xs focus:outline-none focus:border-teal-500 transition-all ${
                    theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-100 placeholder-slate-500' : 'bg-white border-slate-200 text-slate-900 placeholder-slate-400'
                  }`}
                />
              </div>
            </div>
          )}

          <div>
            <label className={`block text-xs font-semibold mb-1.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password (min 8 chars)"
                className={`w-full border rounded-xl pl-9 pr-3.5 py-2 text-xs focus:outline-none focus:border-teal-500 transition-all ${
                  theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-100 placeholder-slate-500' : 'bg-white border-slate-200 text-slate-900 placeholder-slate-400'
                }`}
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
        <div className={`mt-6 pt-4 border-t flex flex-col items-center ${theme === 'dark' ? 'border-slate-800/80' : 'border-slate-200'}`}>
          <span className={`text-[11px] mb-2 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>Quick Demo Account:</span>
          <button
            type="button"
            onClick={fillQuickDemoUser}
            className={`px-3 py-1.5 border rounded-lg text-xs font-mono transition-all flex items-center gap-1.5 ${
              theme === 'dark'
                ? 'bg-slate-900 hover:bg-slate-800 text-teal-400 border-slate-800'
                : 'bg-teal-50 hover:bg-teal-100 text-teal-700 border-teal-200'
            }`}
          >
            <span>Fill Demo Credentials (testuser_qa)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
