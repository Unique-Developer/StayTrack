import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Lock,
  Mail,
  Eye,
  EyeOff,
  AlertTriangle,
  Building2,
  ArrowRight,
  CheckCircle2,
  Loader2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  
  // Form fields
  const [email, setEmail] = useState<string>(() => {
    try {
      return localStorage.getItem('staytrack_remembered_email') || '';
    } catch {
      return '';
    }
  });
  const [password, setPassword] = useState<string>('');
  const [rememberMe, setRememberMe] = useState<boolean>(() => {
    try {
      return !!localStorage.getItem('staytrack_remembered_email');
    } catch {
      return false;
    }
  });

  // UI state
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [capsLockActive, setCapsLockActive] = useState<boolean>(false);
  const [failedAttempts, setFailedAttempts] = useState<number>(0);
  const [cooldownSeconds, setCooldownSeconds] = useState<number>(0);

  // Cooldown timer if rate limited
  useEffect(() => {
    if (cooldownSeconds <= 0) return;
    const interval = setInterval(() => {
      setCooldownSeconds((prev) => Math.max(prev - 1, 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldownSeconds]);

  // Clear error message when user starts typing
  const handleEmailChange = (val: string) => {
    setEmail(val);
    if (errorMessage) setErrorMessage(null);
  };

  const handlePasswordChange = (val: string) => {
    setPassword(val);
    if (errorMessage) setErrorMessage(null);
  };

  const checkCapsLock = (e: React.KeyboardEvent) => {
    if (e.getModifierState) {
      setCapsLockActive(e.getModifierState('CapsLock'));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (cooldownSeconds > 0) {
      setErrorMessage(`Security lockout in effect. Please wait ${cooldownSeconds} second(s) before attempting again.`);
      return;
    }

    const trimmedEmail = email.trim();

    // Client-side validation
    if (!trimmedEmail) {
      setErrorMessage('Please enter your email address.');
      return;
    }

    if (!trimmedEmail.includes('@') || !trimmedEmail.includes('.')) {
      setErrorMessage('Please enter a valid email address format (e.g. name@staytrack.local).');
      return;
    }

    if (!password) {
      setErrorMessage('Please enter your account password.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await login(trimmedEmail, password);

      // Handle remember me on success
      try {
        if (rememberMe) {
          localStorage.setItem('staytrack_remembered_email', trimmedEmail);
        } else {
          localStorage.removeItem('staytrack_remembered_email');
        }
      } catch (e) {
        console.warn('Unable to persist remembered email', e);
      }
    } catch (err: any) {
      console.error('Login authentication error:', err);
      const newAttempts = failedAttempts + 1;
      setFailedAttempts(newAttempts);

      let msg = err.message || 'Incorrect email or password. Please check your credentials and try again.';

      // Check if server returned rate limit (429)
      if (msg.toLowerCase().includes('too many failed') || msg.toLowerCase().includes('wait')) {
        setCooldownSeconds(30);
      } else if (newAttempts >= 5) {
        setCooldownSeconds(30);
        msg = 'Multiple failed attempts detected. Access temporarily paused for 30 seconds for security.';
      }

      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden text-slate-100 font-sans selection:bg-amber-500 selection:text-slate-950">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-amber-500/10 blur-[130px] pointer-events-none rounded-full" />
      <div className="absolute bottom-10 right-10 w-[400px] h-[300px] bg-blue-600/10 blur-[140px] pointer-events-none rounded-full" />

      <div className="w-full max-w-md relative z-10 space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center text-slate-950 font-black text-2xl shadow-xl shadow-amber-500/25 ring-2 ring-amber-400/30">
              S6
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-black tracking-tight text-white">StayTrack</span>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                  PRO
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Daily Reports. Continuous Insights.</p>
            </div>
          </div>

          {/* Motel Property Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/90 border border-slate-800 text-slate-300 text-xs shadow-inner">
            <Building2 className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="font-semibold text-slate-200">STUDIO 6 - STAFFORD, VA</span>
            <span className="text-slate-500 font-mono">#3756</span>
          </div>
        </div>

        {/* Login Card */}
        <div className="bg-slate-900/95 border border-slate-800/90 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl relative">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800/80 mb-6">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Staff Authentication</span>
            </div>
            <span className="text-[11px] text-slate-500 font-medium">Role: Manager / Admin</span>
          </div>

          {/* Prominent Error Banner */}
          {errorMessage && (
            <div
              id="login-error-alert"
              role="alert"
              aria-live="assertive"
              className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/40 text-rose-200 text-sm flex items-start gap-3 shadow-lg shadow-rose-950/20 animate-fadeIn"
            >
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1">
                <div className="font-semibold text-rose-300 text-xs uppercase tracking-wide">
                  Authentication Failed
                </div>
                <div className="text-xs leading-relaxed text-rose-100/90">{errorMessage}</div>
                {failedAttempts >= 3 && cooldownSeconds === 0 && (
                  <div className="text-[11px] text-amber-300/80 pt-1">
                    Note: Passwords are case-sensitive. Check if Caps Lock is enabled.
                  </div>
                )}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            {/* Email Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="login-email"
                className="block text-xs font-semibold text-slate-300 uppercase tracking-wider"
              >
                Email Address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="login-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => handleEmailChange(e.target.value)}
                  placeholder="Enter your email address"
                  autoComplete="username"
                  aria-invalid={!!errorMessage}
                  aria-describedby={errorMessage ? 'login-error-alert' : undefined}
                  className={`w-full pl-10 pr-4 py-2.5 rounded-xl text-sm text-slate-100 placeholder-slate-600 focus:outline-none transition-all ${
                    errorMessage
                      ? 'bg-rose-500/5 border border-rose-500/60 focus:border-rose-400 focus:ring-1 focus:ring-rose-400'
                      : 'bg-slate-950/70 border border-slate-800 focus:border-amber-500 focus:ring-1 focus:ring-amber-500'
                  }`}
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="login-password"
                  className="block text-xs font-semibold text-slate-300 uppercase tracking-wider"
                >
                  Password
                </label>
                {capsLockActive && (
                  <span className="text-[10px] text-amber-400 font-semibold flex items-center gap-1 animate-pulse">
                    Caps Lock is ON
                  </span>
                )}
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  onKeyDown={checkCapsLock}
                  onKeyUp={checkCapsLock}
                  onBlur={() => setCapsLockActive(false)}
                  placeholder="••••••••••••"
                  autoComplete="current-password"
                  aria-invalid={!!errorMessage}
                  aria-describedby={errorMessage ? 'login-error-alert' : undefined}
                  className={`w-full pl-10 pr-11 py-2.5 rounded-xl text-sm text-slate-100 placeholder-slate-600 focus:outline-none transition-all ${
                    errorMessage
                      ? 'bg-rose-500/5 border border-rose-500/60 focus:border-rose-400 focus:ring-1 focus:ring-rose-400'
                      : 'bg-slate-950/70 border border-slate-800 focus:border-amber-500 focus:ring-1 focus:ring-amber-500'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember Me Option */}
            <div className="flex items-center justify-between pt-1 text-xs">
              <label className="flex items-center gap-2 cursor-pointer text-slate-400 hover:text-slate-300 select-none">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-700 bg-slate-950 text-amber-500 focus:ring-amber-500 focus:ring-offset-slate-900 cursor-pointer"
                />
                <span>Remember email on this device</span>
              </label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting || cooldownSeconds > 0}
              className="w-full mt-3 py-3 px-4 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold text-sm shadow-lg shadow-amber-500/25 transition-all flex items-center justify-center gap-2 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Verifying Credentials...</span>
                </>
              ) : cooldownSeconds > 0 ? (
                <span>Security Pause ({cooldownSeconds}s)</span>
              ) : (
                <>
                  <span>Sign In to StayTrack</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Security & Audit Notice */}
        <div className="text-center text-[11px] text-slate-500 space-y-1">
          <p className="flex items-center justify-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            <span>Tamper-evident audit logging is active for all PDF imports and actions.</span>
          </p>
          <p>Protected by TLS 1.3 & Argon2/PBKDF2 SHA-256 Authentication</p>
        </div>
      </div>
    </div>
  );
};
