import React, { useState, useEffect, useCallback } from 'react';
import { 
  ShieldAlert, 
  ShieldCheck, 
  Activity, 
  Pill, 
  History, 
  FileText, 
  AlertTriangle, 
  Send, 
  Bot, 
  User as UserIcon, 
  BookOpen, 
  CheckCircle2, 
  HeartPulse, 
  Search, 
  Sparkles, 
  Info, 
  RefreshCw, 
  Sliders,
  LogOut,
  Edit3,
  Plus,
  Trash2,
  Download,
  X,
  Sun,
  Moon
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  Tooltip, 
  CartesianGrid, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis 
} from 'recharts';

import { AuthView } from './AuthView';
import { 
  getToken, 
  removeToken, 
  getPatientProfile, 
  updatePatientProfile,
  getMedications, 
  addMedication, 
  deleteMedication,
  getSafetyCheck, 
  getSafetyHistory, 
  getUnreadAlerts, 
  acknowledgeAlert, 
  askClinicalAssistant,
  downloadPatientReport,
  downloadClinicianReport
} from './api';
import type { 
  PatientProfile, 
  Medication, 
  SafetyCheckResult, 
  ChatMessage, 
  SafetyHistoryPoint, 
  ProactiveAlert,
  SafetyAlert 
} from './types';

export default function App() {
  const [token, setTokenState] = useState<string | null>(getToken());
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('medguardian_theme') as 'dark' | 'light') || 'dark';
  });

  const [activeTab, setActiveTab] = useState<'dashboard' | 'cabinet' | 'chat' | 'history' | 'reports'>('dashboard');
  
  // Data States
  const [patient, setPatient] = useState<PatientProfile | null>(null);
  const [medications, setMedications] = useState<Medication[]>([]);
  const [safetyCheck, setSafetyCheck] = useState<SafetyCheckResult | null>(null);
  const [safetyHistory, setSafetyHistory] = useState<SafetyHistoryPoint[]>([]);
  const [proactiveAlerts, setProactiveAlerts] = useState<ProactiveAlert[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string>('');

  // Modals state
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showAddMedModal, setShowAddMedModal] = useState(false);
  
  // Profile Form state
  const [profileForm, setProfileForm] = useState({
    age: 30,
    gender: 'Female',
    pregnancy_status: false,
    egfr: '45',
    creatinine: '1.2',
    chronic_diseases: 'Hypertension, Stage 3 CKD',
    allergies: 'Penicillin'
  });

  // New Medication Form state
  const [newMedForm, setNewMedForm] = useState({
    name: '',
    dosage: '10mg',
    frequency: 'Once daily'
  });

  // Simulator state
  const [simulatedDrug, setSimulatedDrug] = useState('');
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<SafetyCheckResult | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isAiThinking, setIsAiThinking] = useState(false);

  // Fast suggestion prompts
  const samplePrompts = [
    'Can the patient take Ibuprofen for knee pain?',
    'Evaluate Metformin dosage for eGFR of 45',
    'What are the bleeding risks of Warfarin with antibiotics?',
    'Is alcohol safe with this medication regimen?'
  ];

  // Sync body theme class
  useEffect(() => {
    document.body.className = theme;
    localStorage.setItem('medguardian_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  // Load patient data from backend
  const loadAllData = useCallback(async () => {
    if (!getToken()) return;
    setLoading(true);
    setErrorMsg('');

    try {
      const [prof, meds, check, hist, alerts] = await Promise.all([
        getPatientProfile(),
        getMedications(),
        getSafetyCheck(),
        getSafetyHistory(),
        getUnreadAlerts()
      ]);

      setPatient(prof);
      setMedications(meds);
      setSafetyCheck(check);
      setSafetyHistory(hist);
      setProactiveAlerts(alerts);

      setProfileForm({
        age: prof.age,
        gender: prof.gender,
        pregnancy_status: prof.is_pregnant,
        egfr: prof.egfr ? String(prof.egfr) : '',
        creatinine: prof.creatinine ? String(prof.creatinine) : '',
        chronic_diseases: prof.chronic_conditions ? prof.chronic_conditions.join(', ') : '',
        allergies: prof.allergies ? prof.allergies.join(', ') : ''
      });

      setMessages([
        {
          id: 'init-1',
          sender: 'assistant',
          content: `Hello! I am MedGuardian AI, your clinical decision support & medication safety digital twin.\n\n` +
            `Active Patient Context Loaded: ${prof.name} (${prof.age}y ${prof.gender}, ` +
            `${meds.length} active medications, eGFR: ${prof.egfr || 'N/A'} mL/min).\n\n` +
            `How can I assist you with clinical guidelines, drug interaction analysis, or dosing safety today?`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          evidence_sources: [
            { title: 'MedGuardian Clinical Knowledge Graph & RAG Core v2.0' }
          ]
        }
      ]);
    } catch (err: any) {
      console.error('Failed to load patient data:', err);
      setErrorMsg(err.message || 'Failed to sync with backend API.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) {
      loadAllData();
    }
  }, [token, loadAllData]);

  // Setup SSE stream for real-time alerts
  useEffect(() => {
    const currentToken = getToken();
    if (!currentToken) return;

    const sseUrl = `/api/alerts/stream/?token=${encodeURIComponent(currentToken)}`;
    const eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.alerts && payload.alerts.length > 0) {
          setProactiveAlerts(prev => {
            const existingIds = new Set(prev.map(a => String(a.id)));
            const newAlerts = payload.alerts.filter((a: any) => !existingIds.has(String(a.id)));
            return [...newAlerts, ...prev];
          });
          getSafetyCheck().then(setSafetyCheck).catch(() => {});
          getSafetyHistory().then(setSafetyHistory).catch(() => {});
        }
      } catch (_e) {
        // SSE pulse parsing
      }
    };

    return () => {
      eventSource.close();
    };
  }, [token]);

  const handleAuthSuccess = (newToken: string) => {
    setTokenState(newToken);
  };

  const handleLogout = () => {
    removeToken();
    setTokenState(null);
    setPatient(null);
    setMedications([]);
    setSafetyCheck(null);
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const updated = await updatePatientProfile({
        age: Number(profileForm.age),
        gender: profileForm.gender,
        is_pregnant: profileForm.pregnancy_status,
        egfr: profileForm.egfr ? Number(profileForm.egfr) : undefined,
        creatinine: profileForm.creatinine ? Number(profileForm.creatinine) : undefined,
        chronic_conditions: profileForm.chronic_diseases.split(',').map(s => s.trim()).filter(Boolean),
        allergies: profileForm.allergies.split(',').map(s => s.trim()).filter(Boolean)
      });
      setPatient(updated);
      setShowProfileModal(false);

      const [check, hist, alerts] = await Promise.all([
        getSafetyCheck(),
        getSafetyHistory(),
        getUnreadAlerts()
      ]);
      setSafetyCheck(check);
      setSafetyHistory(hist);
      setProactiveAlerts(alerts);
    } catch (err: any) {
      alert(`Failed to update profile: ${err.message}`);
    }
  };

  const handleAddMedication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMedForm.name.trim()) return;

    try {
      await addMedication({
        name: newMedForm.name,
        dosage: newMedForm.dosage,
        frequency: newMedForm.frequency
      });

      setNewMedForm({ name: '', dosage: '10mg', frequency: 'Once daily' });
      setShowAddMedModal(false);

      const [meds, check, hist, alerts] = await Promise.all([
        getMedications(),
        getSafetyCheck(),
        getSafetyHistory(),
        getUnreadAlerts()
      ]);
      setMedications(meds);
      setSafetyCheck(check);
      setSafetyHistory(hist);
      setProactiveAlerts(alerts);
    } catch (err: any) {
      alert(`Failed to add medication: ${err.message}`);
    }
  };

  const handleDeleteMedication = async (id: number) => {
    if (!confirm('Are you sure you want to remove this medication from the active regimen?')) return;
    try {
      await deleteMedication(id);
      const [meds, check, hist, alerts] = await Promise.all([
        getMedications(),
        getSafetyCheck(),
        getSafetyHistory(),
        getUnreadAlerts()
      ]);
      setMedications(meds);
      setSafetyCheck(check);
      setSafetyHistory(hist);
      setProactiveAlerts(alerts);
    } catch (err: any) {
      alert(`Failed to delete medication: ${err.message}`);
    }
  };

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!simulatedDrug.trim()) return;

    setIsSimulating(true);
    try {
      const tempMed = await addMedication({
        name: simulatedDrug,
        dosage: 'Standard Dosage',
        frequency: 'As needed'
      });

      const check = await getSafetyCheck();
      setSimulationResult(check);

      await deleteMedication(tempMed.id);
      await getMedications().then(setMedications);
    } catch (_err) {
      // Fallback preview
    } finally {
      setIsSimulating(false);
    }
  };

  const handleCommitSimulatedDrug = async () => {
    if (!simulatedDrug.trim()) return;
    try {
      await addMedication({
        name: simulatedDrug,
        dosage: 'Standard Dose',
        frequency: 'As prescribed'
      });
      setSimulatedDrug('');
      setSimulationResult(null);

      const [meds, check, hist, alerts] = await Promise.all([
        getMedications(),
        getSafetyCheck(),
        getSafetyHistory(),
        getUnreadAlerts()
      ]);
      setMedications(meds);
      setSafetyCheck(check);
      setSafetyHistory(hist);
      setProactiveAlerts(alerts);

      setActiveTab('dashboard');
    } catch (err: any) {
      alert(`Failed to commit medication: ${err.message}`);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputMessage;
    if (!text.trim() || isAiThinking) return;

    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setIsAiThinking(true);

    try {
      const contextDrugs = medications.map(m => m.name);
      const assistantMsg = await askClinicalAssistant(text, contextDrugs);
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          content: `⚠️ Error fetching response: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsAiThinking(false);
    }
  };

  const handleDismissAlert = async (id: number | string) => {
    try {
      await acknowledgeAlert(id);
      setProactiveAlerts(prev => prev.filter(a => String(a.id) !== String(id)));
    } catch (_err) {
      setProactiveAlerts(prev => prev.filter(a => String(a.id) !== String(id)));
    }
  };

  const getRiskColorClasses = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'critical':
      case 'severe':
        return theme === 'dark'
          ? 'text-rose-400 bg-rose-950/60 border-rose-800/80 glow-rose-sm'
          : 'text-rose-700 bg-rose-50 border-rose-300';
      case 'high':
        return theme === 'dark'
          ? 'text-amber-400 bg-amber-950/60 border-amber-800/80'
          : 'text-amber-700 bg-amber-50 border-amber-300';
      case 'moderate':
        return theme === 'dark'
          ? 'text-yellow-300 bg-yellow-950/50 border-yellow-700/60'
          : 'text-yellow-800 bg-yellow-50 border-yellow-300';
      default:
        return theme === 'dark'
          ? 'text-teal-300 bg-teal-950/50 border-teal-700/60'
          : 'text-teal-800 bg-teal-50 border-teal-300';
    }
  };

  // Render SVG Semi-Gauge Dial for Risk Score
  const renderRiskGauge = (scoreNum: number, levelStr: string) => {
    const strokeDashoffset = 251.2 - (251.2 * Math.min(100, Math.max(0, scoreNum))) / 100;
    const isHighOrSevere = levelStr.toLowerCase() === 'severe' || levelStr.toLowerCase() === 'high';
    const dialColor = isHighOrSevere ? '#f43f5e' : levelStr.toLowerCase() === 'moderate' ? '#f59e0b' : '#14b8a6';

    return (
      <div className="relative flex flex-col items-center justify-center">
        <svg className="w-28 h-16" viewBox="0 0 100 55">
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={theme === 'dark' ? '#1e293b' : '#e2e8f0'}
            strokeWidth="8"
            strokeLinecap="round"
          />
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={dialColor}
            strokeWidth="8"
            strokeDasharray="251.2"
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute top-6 flex flex-col items-center">
          <span className="text-xl font-extrabold tracking-tight font-mono">{scoreNum}</span>
          <span className="text-[9px] uppercase font-bold tracking-wider opacity-75">{levelStr}</span>
        </div>
      </div>
    );
  };

  // Unauthenticated -> Render Auth View
  if (!token) {
    return <AuthView onAuthSuccess={handleAuthSuccess} theme={theme} onToggleTheme={toggleTheme} />;
  }

  // Loading state
  if (loading && !patient) {
    return (
      <div className={`min-h-screen flex flex-col items-center justify-center p-4 transition-colors ${theme === 'dark' ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
        <RefreshCw className="w-8 h-8 text-teal-500 animate-spin mb-3" />
        <p className="text-xs font-semibold text-slate-400">Syncing with MedGuardian AI backend & Digital Twin engine...</p>
      </div>
    );
  }

  return (
    <div className={`min-h-screen flex flex-col transition-colors duration-200 selection:bg-teal-500 selection:text-white ${theme === 'dark' ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      
      {/* Executive Header */}
      <header className={`sticky top-0 z-40 border-b px-4 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-4 transition-colors ${theme === 'dark' ? 'bg-slate-900/90 border-slate-800/80 backdrop-blur-md' : 'bg-white/90 border-slate-200 backdrop-blur-md shadow-sm'}`}>
        
        {/* Brand & Subtitle */}
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-2xl bg-gradient-to-tr from-teal-600 to-emerald-400 text-slate-950 shadow-lg shadow-teal-500/20">
            <HeartPulse className="w-6 h-6 stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-xl tracking-tight">MedGuardian<span className="text-teal-500 font-extrabold ml-0.5">AI</span></span>
              <span className="px-2 py-0.5 text-[10px] font-bold bg-teal-500/10 text-teal-500 border border-teal-500/30 rounded-full uppercase tracking-wider">Clinical Enterprise v2.0</span>
            </div>
            <p className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Clinical Decision Support & Medication Digital Twin System</p>
          </div>
        </div>

        {/* Live Patient Glance Badge */}
        {patient && (
          <div className={`hidden md:flex items-center gap-3 border px-4 py-2 rounded-2xl transition-all ${theme === 'dark' ? 'bg-slate-900/90 border-slate-800' : 'bg-slate-50 border-slate-200'}`}>
            <div className="w-9 h-9 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-500 font-extrabold text-xs">
              {patient.name.substring(0, 2).toUpperCase()}
            </div>
            <div className="text-xs">
              <div className="font-bold flex items-center gap-2">
                {patient.name} <span className={`font-normal text-[11px] ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>({patient.age}y {patient.gender})</span>
              </div>
              <div className={`text-[11px] flex items-center gap-2 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
                <span>eGFR: <strong className="text-amber-500">{patient.egfr ?? 'N/A'} mL/min</strong></span>
                <span>•</span>
                <span>Allergies: <strong className="text-rose-500">{patient.allergies.length > 0 ? patient.allergies.join(', ') : 'None'}</strong></span>
              </div>
            </div>
            <button
              onClick={() => setShowProfileModal(true)}
              className={`p-1.5 rounded-lg border transition-all ml-1 ${theme === 'dark' ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-100'}`}
              title="Edit Patient Clinical Profile"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Header Controls (Theme Toggle, Risk Dial, User Avatar/Logout) */}
        <div className="flex items-center gap-3">
          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className={`p-2.5 rounded-xl border transition-all ${
              theme === 'dark'
                ? 'bg-slate-900 border-slate-800 text-amber-400 hover:bg-slate-800'
                : 'bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200'
            }`}
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Theme`}
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          {/* Global Risk Badge */}
          {safetyCheck && (
            <div className={`px-3.5 py-1.5 rounded-xl border flex items-center gap-2 ${getRiskColorClasses(String(safetyCheck.overall_risk_level))}`}>
              {String(safetyCheck.overall_risk_level).toLowerCase() === 'severe' || String(safetyCheck.overall_risk_level).toLowerCase() === 'high' ? (
                <ShieldAlert className="w-4 h-4 animate-pulse" />
              ) : (
                <ShieldCheck className="w-4 h-4" />
              )}
              <span className="text-xs font-extrabold uppercase tracking-wider">
                {safetyCheck.overall_risk_level} Risk ({safetyCheck.overall_risk_score}/100)
              </span>
            </div>
          )}

          {/* User Signout Button */}
          <button
            onClick={handleLogout}
            className={`p-2.5 rounded-xl border transition-all flex items-center gap-1.5 text-xs font-semibold ${
              theme === 'dark'
                ? 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                : 'bg-white border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
            title="Sign Out"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Proactive Alerts Stream Banner */}
      {proactiveAlerts.length > 0 && (
        <div className={`border-b px-4 lg:px-8 py-2.5 text-xs flex items-center justify-between transition-colors ${
          theme === 'dark'
            ? 'bg-gradient-to-r from-rose-950/80 via-slate-900 to-rose-950/80 border-rose-900/50'
            : 'bg-rose-50 border-rose-200 text-rose-900'
        }`}>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-500 flex-shrink-0 animate-pulse" />
            <span className="font-bold uppercase tracking-wider text-rose-500">Proactive Alert ({proactiveAlerts[0].severity}):</span>
            <span className="font-medium line-clamp-1">{proactiveAlerts[0].message}</span>
          </div>
          <button 
            onClick={() => handleDismissAlert(proactiveAlerts[0].id)}
            className="text-xs font-bold underline ml-4 whitespace-nowrap hover:opacity-80 transition-opacity"
          >
            Acknowledge
          </button>
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex flex-col md:flex-row max-w-7xl w-full mx-auto p-4 lg:p-6 gap-6">
        
        {/* Navigation Sidebar Tabs */}
        <aside className={`w-full md:w-64 flex-shrink-0 flex md:flex-col gap-1.5 p-2 rounded-2xl border self-start panel-surface`}>
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'dashboard'
                ? 'bg-teal-500/10 text-teal-500 border border-teal-500/30 glow-teal-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Activity className="w-4 h-4 text-teal-500" />
            <span>Digital Twin Safety</span>
          </button>

          <button
            onClick={() => setActiveTab('cabinet')}
            className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'cabinet'
                ? 'bg-teal-500/10 text-teal-500 border border-teal-500/30 glow-teal-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Pill className="w-4 h-4 text-cyan-500" />
            <div className="flex-1 flex justify-between items-center">
              <span>Medication Cabinet</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${theme === 'dark' ? 'bg-slate-800 text-slate-300' : 'bg-slate-200 text-slate-700'}`}>{medications.length}</span>
            </div>
          </button>

          <button
            onClick={() => setActiveTab('chat')}
            className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'chat'
                ? 'bg-teal-500/10 text-teal-500 border border-teal-500/30 glow-teal-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Bot className="w-4 h-4 text-emerald-500" />
            <span>Clinical AI (RAG)</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'history'
                ? 'bg-teal-500/10 text-teal-500 border border-teal-500/30 glow-teal-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <History className="w-4 h-4 text-amber-500" />
            <span>Safety History</span>
          </button>

          <button
            onClick={() => setActiveTab('reports')}
            className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'reports'
                ? 'bg-teal-500/10 text-teal-500 border border-teal-500/30 glow-teal-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <FileText className="w-4 h-4 text-indigo-500" />
            <span>Clinical Summary</span>
          </button>
        </aside>

        {/* Content Area */}
        <main className="flex-1 min-w-0 flex flex-col">
          {/* Error Banner */}
          {errorMsg && (
            <div className="mb-4 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center justify-between">
              <span>{errorMsg}</span>
              <button onClick={() => setErrorMsg('')} className="hover:opacity-80">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* TAB 1: EXECUTIVE DIGITAL TWIN SAFETY DASHBOARD */}
          {activeTab === 'dashboard' && safetyCheck && (
            <div className="space-y-6">
              
              {/* Executive Overview Stats Grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                
                {/* Risk Score Dial Card */}
                <div className="panel-surface p-4 rounded-2xl flex flex-col items-center justify-between">
                  <span className={`text-xs font-semibold ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Cumulative Safety Risk</span>
                  {renderRiskGauge(Number(safetyCheck.overall_risk_score), String(safetyCheck.overall_risk_level))}
                </div>

                {/* Active Regimen Count */}
                <div className="panel-surface p-4 rounded-2xl flex flex-col justify-between">
                  <div className="flex justify-between items-center">
                    <span className={`text-xs font-semibold ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Active Regimen</span>
                    <Pill className="w-4 h-4 text-cyan-500" />
                  </div>
                  <div className="my-2">
                    <span className="text-3xl font-extrabold tracking-tight font-mono">{medications.length}</span>
                    <span className={`text-xs ml-2 font-medium ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Active Meds</span>
                  </div>
                  <span className="text-[11px] text-teal-500 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Regimen Synchronized
                  </span>
                </div>

                {/* Active Clinical Warnings Count */}
                <div className="panel-surface p-4 rounded-2xl flex flex-col justify-between">
                  <div className="flex justify-between items-center">
                    <span className={`text-xs font-semibold ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Active Warnings</span>
                    <ShieldAlert className="w-4 h-4 text-amber-500" />
                  </div>
                  <div className="my-2">
                    <span className="text-3xl font-extrabold tracking-tight font-mono">{safetyCheck.alerts.length}</span>
                    <span className={`text-xs ml-2 font-medium ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Flagged Alerts</span>
                  </div>
                  <span className="text-[11px] text-amber-500 font-semibold">
                    {safetyCheck.alerts.length > 0 ? 'Requires Clinical Review' : 'No Critical Concerns'}
                  </span>
                </div>

                {/* Live Backend Audit Status */}
                <div className="panel-surface p-4 rounded-2xl flex flex-col justify-between">
                  <div className="flex justify-between items-center">
                    <span className={`text-xs font-semibold ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Celery Task Engine</span>
                    <Activity className="w-4 h-4 text-emerald-500" />
                  </div>
                  <div className="my-2">
                    <span className="text-lg font-bold text-emerald-500 flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" /> Live Audit Engine
                    </span>
                  </div>
                  <span className={`text-[11px] ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
                    Last sync: {new Date(safetyCheck.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>

              {/* Digital Twin Organ System Burden Panel */}
              <div className="panel-surface p-5 rounded-2xl">
                <h3 className="font-bold text-sm mb-3 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-teal-500" />
                  Digital Twin Organ System Clearance & Burden
                </h3>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="card-surface p-3.5 rounded-xl">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className={`text-xs font-medium ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>Renal Clearance</span>
                      <span className="text-xs font-mono font-bold text-amber-500">{safetyCheck.digital_twin_status.renal_load}%</span>
                    </div>
                    <div className={`w-full h-2 rounded-full overflow-hidden ${theme === 'dark' ? 'bg-slate-800' : 'bg-slate-200'}`}>
                      <div className="bg-amber-500 h-full rounded-full transition-all duration-500" style={{ width: `${safetyCheck.digital_twin_status.renal_load}%` }} />
                    </div>
                    <span className={`text-[10px] mt-1.5 block ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>eGFR: {patient?.egfr ?? 'N/A'} mL/min</span>
                  </div>

                  <div className="card-surface p-3.5 rounded-xl">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className={`text-xs font-medium ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>Hepatic Metabolism</span>
                      <span className="text-xs font-mono font-bold text-teal-500">{safetyCheck.digital_twin_status.hepatic_load}%</span>
                    </div>
                    <div className={`w-full h-2 rounded-full overflow-hidden ${theme === 'dark' ? 'bg-slate-800' : 'bg-slate-200'}`}>
                      <div className="bg-teal-500 h-full rounded-full transition-all duration-500" style={{ width: `${safetyCheck.digital_twin_status.hepatic_load}%` }} />
                    </div>
                    <span className={`text-[10px] mt-1.5 block ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>Normal Enzyme Profile</span>
                  </div>

                  <div className="card-surface p-3.5 rounded-xl">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className={`text-xs font-medium ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>Cardiovascular Monitor</span>
                      <span className="text-xs font-mono font-bold text-cyan-500">{safetyCheck.digital_twin_status.cardiac_risk}%</span>
                    </div>
                    <div className={`w-full h-2 rounded-full overflow-hidden ${theme === 'dark' ? 'bg-slate-800' : 'bg-slate-200'}`}>
                      <div className="bg-cyan-500 h-full rounded-full transition-all duration-500" style={{ width: `${safetyCheck.digital_twin_status.cardiac_risk}%` }} />
                    </div>
                    <span className={`text-[10px] mt-1.5 block ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>Cardiovascular Risk Profile</span>
                  </div>

                  <div className="card-surface p-3.5 rounded-xl">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className={`text-xs font-medium ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>CNS Burden</span>
                      <span className="text-xs font-mono font-bold text-emerald-500">{safetyCheck.digital_twin_status.cns_depression_risk}%</span>
                    </div>
                    <div className={`w-full h-2 rounded-full overflow-hidden ${theme === 'dark' ? 'bg-slate-800' : 'bg-slate-200'}`}>
                      <div className="bg-emerald-500 h-full rounded-full transition-all duration-500" style={{ width: `${safetyCheck.digital_twin_status.cns_depression_risk}%` }} />
                    </div>
                    <span className={`text-[10px] mt-1.5 block ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>Low Sedation Burden</span>
                  </div>
                </div>
              </div>

              {/* Active Clinical Safety Warnings & Alerts */}
              <div className="panel-surface p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-base flex items-center gap-2">
                    <ShieldAlert className="w-5 h-5 text-amber-500" />
                    Active Clinical Safety Alerts ({safetyCheck.alerts.length})
                  </h3>
                  <span className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Evaluated via Backend Clinical Engine</span>
                </div>

                {safetyCheck.alerts.length === 0 ? (
                  <div className="p-6 text-center text-xs text-teal-500 bg-teal-500/10 border border-teal-500/30 rounded-xl font-medium">
                    <CheckCircle2 className="w-8 h-8 text-teal-500 mx-auto mb-2" />
                    No critical drug interactions or contraindications flagged for active regimen.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {safetyCheck.alerts.map((alert: SafetyAlert) => (
                      <div 
                        key={alert.id} 
                        className={`p-4 rounded-xl border transition-all card-surface ${
                          String(alert.severity).toLowerCase() === 'severe' || String(alert.severity).toLowerCase() === 'critical'
                            ? theme === 'dark' ? 'bg-rose-950/30 border-rose-800/80' : 'bg-rose-50 border-rose-200'
                            : theme === 'dark' ? 'bg-amber-950/30 border-amber-800/80' : 'bg-amber-50 border-amber-200'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${getRiskColorClasses(alert.severity)}`}>
                              {alert.severity}
                            </span>
                            <h4 className="font-bold text-xs">{alert.title}</h4>
                          </div>
                        </div>

                        <p className={`text-xs leading-relaxed mb-2.5 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}`}>{alert.description}</p>

                        <div className={`text-xs p-2.5 rounded-lg border flex items-start gap-2 ${
                          theme === 'dark' ? 'bg-teal-950/40 border-teal-900/60 text-teal-300' : 'bg-teal-50 border-teal-200 text-teal-800'
                        }`}>
                          <CheckCircle2 className="w-4 h-4 text-teal-500 flex-shrink-0 mt-0.5" />
                          <div>
                            <strong>Clinical Directive:</strong> {alert.recommendation}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Actionable Clinical Directives */}
              <div className="panel-surface p-5 rounded-2xl">
                <h3 className="font-bold text-sm mb-3 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-teal-500" />
                  Actionable Clinical Directives
                </h3>
                <ul className="space-y-2 text-xs">
                  {safetyCheck.recommendations.map((rec: string, i: number) => (
                    <li key={i} className={`flex items-start gap-2.5 p-3 rounded-xl border card-surface`}>
                      <span className="w-5 h-5 rounded-full bg-teal-500/10 text-teal-500 border border-teal-500/30 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
                        {i + 1}
                      </span>
                      <span className="leading-relaxed font-medium">{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* TAB 2: MEDICATION CABINET & PRE-PRESCRIPTION SIMULATOR */}
          {activeTab === 'cabinet' && (
            <div className="space-y-6">
              
              {/* Stepped Pre-Prescription Simulator Workflow */}
              <div className="panel-surface p-5 rounded-2xl border-teal-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <Sliders className="w-4 h-4 text-teal-500" />
                  <h3 className="font-bold text-sm">Digital Twin Pre-Prescription Simulator</h3>
                </div>
                <p className={`text-xs mb-4 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
                  Simulate prescribing a candidate medication against {patient?.name}'s digital twin before committing to cabinet.
                </p>

                {/* Workflow Steps Indicator */}
                <div className="grid grid-cols-4 gap-2 mb-4 text-[11px] font-bold">
                  <div className={`p-2 rounded-lg border text-center ${simulatedDrug ? 'bg-teal-500/10 text-teal-500 border-teal-500/30' : theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-500' : 'bg-slate-100 border-slate-200 text-slate-400'}`}>
                    1. Select Candidate
                  </div>
                  <div className={`p-2 rounded-lg border text-center ${isSimulating ? 'bg-amber-500/10 text-amber-500 border-amber-500/30 animate-pulse' : simulationResult ? 'bg-teal-500/10 text-teal-500 border-teal-500/30' : theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-500' : 'bg-slate-100 border-slate-200 text-slate-400'}`}>
                    2. Digital Twin Test
                  </div>
                  <div className={`p-2 rounded-lg border text-center ${simulationResult ? 'bg-teal-500/10 text-teal-500 border-teal-500/30' : theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-500' : 'bg-slate-100 border-slate-200 text-slate-400'}`}>
                    3. Risk Shift Report
                  </div>
                  <div className={`p-2 rounded-lg border text-center ${simulationResult ? 'bg-teal-500/10 text-teal-500 border-teal-500/30' : theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-500' : 'bg-slate-100 border-slate-200 text-slate-400'}`}>
                    4. Commit Decision
                  </div>
                </div>

                <form onSubmit={handleSimulate} className="flex gap-2 mb-3">
                  <input
                    type="text"
                    placeholder="Enter drug name (e.g. Ibuprofen, Amoxicillin, Ciprofloxacin, Acetaminophen)..."
                    value={simulatedDrug}
                    onChange={(e) => setSimulatedDrug(e.target.value)}
                    className={`flex-1 border rounded-xl px-3.5 py-2 text-xs focus:outline-none focus:border-teal-500 transition-all ${
                      theme === 'dark' ? 'bg-slate-900 border-slate-800 text-slate-100 placeholder-slate-500' : 'bg-white border-slate-200 text-slate-900 placeholder-slate-400'
                    }`}
                  />
                  <button
                    type="submit"
                    disabled={isSimulating || !simulatedDrug.trim()}
                    className="px-4 py-2 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md shadow-teal-500/20 disabled:opacity-50"
                  >
                    {isSimulating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                    Simulate Impact
                  </button>
                </form>

                {/* Quick Simulation Chips */}
                <div className={`flex flex-wrap gap-2 text-[11px] items-center ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
                  <span>Quick Test:</span>
                  <button 
                    type="button" 
                    onClick={() => setSimulatedDrug('Ibuprofen')}
                    className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 border border-rose-500/30 transition-all font-semibold"
                  >
                    + Ibuprofen (NSAID Risk)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setSimulatedDrug('Amoxicillin')}
                    className="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 border border-amber-500/30 transition-all font-semibold"
                  >
                    + Amoxicillin (Allergy Risk)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setSimulatedDrug('Ciprofloxacin')}
                    className="px-2.5 py-1 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-500 border border-cyan-500/30 transition-all font-semibold"
                  >
                    + Ciprofloxacin (CYP Risk)
                  </button>
                </div>

                {/* Simulation Result Box */}
                {simulationResult && (
                  <div className={`mt-4 p-4 rounded-xl border animate-fadeIn ${theme === 'dark' ? 'bg-slate-900/90 border-slate-800' : 'bg-slate-50 border-slate-200'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${getRiskColorClasses(String(simulationResult.overall_risk_level))}`}>
                          Projected: {simulationResult.overall_risk_level} ({simulationResult.overall_risk_score}/100)
                        </span>
                        <h4 className="font-bold text-xs">{simulationResult.summary}</h4>
                      </div>
                      <button
                        onClick={handleCommitSimulatedDrug}
                        className="px-3.5 py-1.5 bg-teal-500/10 hover:bg-teal-500/20 text-teal-500 text-xs font-bold rounded-lg border border-teal-500/30 transition-all"
                      >
                        Commit to Cabinet
                      </button>
                    </div>

                    <div className="text-xs space-y-2 mt-2">
                      {simulationResult.alerts.slice(0, 2).map((alert: SafetyAlert) => (
                        <div key={alert.id} className="p-3 rounded-lg border card-surface">
                          <p className="text-xs font-bold text-amber-500 mb-1">{alert.description}</p>
                          <p className="text-[11px] text-teal-500"><strong>Recommendation:</strong> {alert.recommendation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Active Prescriptions Table & Cards */}
              <div className="panel-surface p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-base flex items-center gap-2">
                    <Pill className="w-5 h-5 text-cyan-500" />
                    Active Prescription Regimen ({medications.length})
                  </h3>
                  <button
                    onClick={() => setShowAddMedModal(true)}
                    className="px-3.5 py-2 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md shadow-teal-500/20"
                  >
                    <Plus className="w-4 h-4" />
                    Add Prescription
                  </button>
                </div>

                {medications.length === 0 ? (
                  <div className={`p-6 text-center text-xs rounded-xl border ${theme === 'dark' ? 'bg-slate-900/50 border-slate-800 text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-500'}`}>
                    No active medications in cabinet. Click "Add Prescription" to add your first medication.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {medications.map((med) => (
                      <div key={med.id} className="card-surface p-4 rounded-xl border flex flex-col justify-between card-surface-hover transition-all">
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <h4 className="font-bold text-sm">{med.name}</h4>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-teal-500/10 text-teal-500 border border-teal-500/30">
                                {med.dosage}
                              </span>
                              <button
                                onClick={() => handleDeleteMedication(med.id)}
                                className="text-slate-400 hover:text-rose-500 transition-colors p-1"
                                title="Remove medication"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                          <p className={`text-xs mb-2 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>{med.generic_name}</p>
                          
                          <div className={`space-y-1 text-xs mb-3 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}`}>
                            <div><span className={theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}>Frequency:</span> {med.frequency}</div>
                            <div><span className={theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}>Indication:</span> {med.indication}</div>
                            <div><span className={theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}>Prescriber:</span> {med.prescribing_doctor}</div>
                          </div>
                        </div>

                        <div className={`pt-2 border-t flex justify-between items-center text-[11px] ${theme === 'dark' ? 'border-slate-800 text-slate-400' : 'border-slate-200 text-slate-500'}`}>
                          <span>Started: {med.start_date}</span>
                          <span className="text-emerald-500 font-bold">● Active</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: CLINICAL AI RAG ASSISTANT */}
          {activeTab === 'chat' && (
            <div className="panel-surface rounded-2xl flex flex-col h-[650px] overflow-hidden">
              {/* Chat Header */}
              <div className={`p-4 border-b flex items-center justify-between ${theme === 'dark' ? 'bg-slate-900/60 border-slate-800' : 'bg-slate-100/80 border-slate-200'}`}>
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-teal-600 flex items-center justify-center text-slate-950 font-bold">
                    <Bot className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm">Clinical AI Evidence Chat</h3>
                    <p className={`text-[10px] ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Grounded in WHO Essential Medicines, FDA Prescribing Labels & Vector Guidelines Store</p>
                  </div>
                </div>
                <span className="text-[11px] text-teal-500 font-mono font-bold bg-teal-500/10 px-2.5 py-1 rounded-full border border-teal-500/30">
                  RAG Core Active
                </span>
              </div>

              {/* Message Feed */}
              <div className="flex-1 p-4 overflow-y-auto space-y-4">
                {messages.map((msg) => (
                  <div 
                    key={msg.id} 
                    className={`flex gap-3 max-w-2xl ${msg.sender === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
                  >
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                      msg.sender === 'user' 
                        ? theme === 'dark' ? 'bg-slate-800 text-slate-200' : 'bg-slate-200 text-slate-800'
                        : 'bg-teal-600 text-slate-950'
                    }`}>
                      {msg.sender === 'user' ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>

                    <div className={`p-4 rounded-2xl text-xs leading-relaxed ${
                      msg.sender === 'user'
                        ? 'bg-teal-600 text-white rounded-tr-none'
                        : theme === 'dark' ? 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none' : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none shadow-sm'
                    }`}>
                      <div className="whitespace-pre-wrap">{msg.content}</div>

                      {/* Evidence Citations */}
                      {msg.evidence_sources && msg.evidence_sources.length > 0 && (
                        <div className={`mt-3 pt-2.5 border-t text-[10px] space-y-1 ${theme === 'dark' ? 'border-slate-800 text-slate-400' : 'border-slate-200 text-slate-500'}`}>
                          <span className="font-bold block text-teal-500">Grounding Evidence & Citations:</span>
                          {msg.evidence_sources.map((src, idx) => (
                            <div key={idx} className="flex items-center gap-1.5 text-teal-500 font-semibold">
                              <BookOpen className="w-3 h-3 flex-shrink-0" />
                              <span>{src.title}</span>
                              {src.confidence && (
                                <span className="opacity-75 font-mono">({Math.round(src.confidence * 100)}% match)</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      
                      <span className={`block mt-1.5 text-[9px] text-right ${msg.sender === 'user' ? 'text-teal-100' : theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>{msg.timestamp}</span>
                    </div>
                  </div>
                ))}

                {isAiThinking && (
                  <div className={`flex gap-3 items-center text-xs text-teal-500 p-3.5 rounded-xl border w-fit ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Searching clinical vector index & synthesizing evidence...</span>
                  </div>
                )}
              </div>

              {/* Fast Prompt Suggestions */}
              <div className={`px-4 py-2.5 border-t flex flex-wrap gap-1.5 ${theme === 'dark' ? 'border-slate-800 bg-slate-950/40' : 'border-slate-200 bg-slate-100/50'}`}>
                {samplePrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(prompt)}
                    className={`text-[11px] px-3 py-1 rounded-full border transition-all text-left font-medium ${
                      theme === 'dark' 
                        ? 'bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800' 
                        : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-300'
                    }`}
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              {/* Chat Input Bar */}
              <div className={`p-3 border-t flex gap-2 ${theme === 'dark' ? 'border-slate-800 bg-slate-900/90' : 'border-slate-200 bg-white'}`}>
                <input
                  type="text"
                  placeholder={`Ask a clinical question about ${patient?.name || 'patient'}'s active medications, dosages, or side-effects...`}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  className={`flex-1 border rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-teal-500 transition-all ${
                    theme === 'dark' ? 'bg-slate-950 border-slate-800 text-slate-100 placeholder-slate-500' : 'bg-slate-50 border-slate-300 text-slate-900 placeholder-slate-400'
                  }`}
                />
                <button
                  onClick={() => handleSendMessage()}
                  disabled={!inputMessage.trim() || isAiThinking}
                  className="px-4 py-2.5 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md shadow-teal-500/20 disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: SAFETY HISTORY & RISK ANALYTICS */}
          {activeTab === 'history' && (
            <div className="space-y-6">
              
              {/* Longitudinal Risk Trend Chart */}
              <div className="panel-surface p-6 rounded-2xl">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-base flex items-center gap-2">
                      <History className="w-5 h-5 text-amber-500" />
                      Longitudinal Medication Risk Progression
                    </h3>
                    <p className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Live timeline generated from backend Celery evaluation audits</p>
                  </div>
                </div>

                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={safetyHistory} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.4}/>
                          <stop offset="95%" stopColor="#14b8a6" stopOpacity={0.0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#334155' : '#cbd5e1'} />
                      <XAxis dataKey="date" stroke={theme === 'dark' ? '#94a3b8' : '#64748b'} fontSize={10} />
                      <YAxis stroke={theme === 'dark' ? '#94a3b8' : '#64748b'} fontSize={11} domain={[0, 100]} />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: theme === 'dark' ? '#0f172a' : '#ffffff', 
                          borderColor: theme === 'dark' ? '#334155' : '#cbd5e1', 
                          borderRadius: '8px', 
                          fontSize: '12px',
                          color: theme === 'dark' ? '#f8fafc' : '#0f172a'
                        }}
                      />
                      <Area type="monotone" dataKey="score" stroke="#14b8a6" strokeWidth={2.5} fillOpacity={1} fill="url(#riskGradient)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Event Audit Trail */}
              <div className="panel-surface p-6 rounded-2xl">
                <h3 className="font-bold text-sm mb-4">Medication Modification Audit Trail</h3>
                <div className="space-y-3">
                  {safetyHistory.map((pt, i) => (
                    <div key={i} className="flex items-start gap-3 relative">
                      {i < safetyHistory.length - 1 && (
                        <div className={`absolute left-2.5 top-6 bottom-0 w-0.5 ${theme === 'dark' ? 'bg-slate-800' : 'bg-slate-200'}`} />
                      )}
                      <div className="w-5 h-5 rounded-full bg-teal-500/20 border-2 border-teal-500 z-10 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 card-surface p-3.5 rounded-xl">
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-bold text-xs">{pt.event}</span>
                          <span className={`text-[10px] font-mono ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>{pt.date}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${getRiskColorClasses(pt.risk_level)}`}>
                            {pt.risk_level} ({pt.score}/100)
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: CLINICAL SUMMARY & REPORT GENERATION */}
          {activeTab === 'reports' && patient && (
            <div className="panel-surface p-6 rounded-2xl space-y-6">
              <div className={`flex flex-wrap items-center justify-between border-b pb-4 gap-3 ${theme === 'dark' ? 'border-slate-800' : 'border-slate-200'}`}>
                <div>
                  <h3 className="font-bold text-lg">Comprehensive Clinical Decision Summary</h3>
                  <p className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Generated directly from Django Backend ReportLab PDF Engine</p>
                </div>
                
                <div className="flex gap-2">
                  <button 
                    onClick={() => downloadPatientReport()}
                    className="px-4 py-2.5 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-slate-950 text-xs font-bold rounded-xl flex items-center gap-1.5 transition-all shadow-md shadow-teal-500/20"
                  >
                    <Download className="w-4 h-4" />
                    Patient Report (PDF)
                  </button>

                  <button 
                    onClick={() => downloadClinicianReport()}
                    className={`px-4 py-2.5 text-xs font-bold rounded-xl border flex items-center gap-1.5 transition-all ${
                      theme === 'dark'
                        ? 'bg-slate-900 hover:bg-slate-800 text-teal-400 border-slate-800'
                        : 'bg-white hover:bg-slate-100 text-teal-700 border-slate-300'
                    }`}
                  >
                    <FileText className="w-4 h-4" />
                    Clinician Dossier (PDF)
                  </button>
                </div>
              </div>

              <div className={`grid grid-cols-2 md:grid-cols-4 gap-4 p-4 rounded-xl border text-xs card-surface`}>
                <div>
                  <span className={`block text-[11px] ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Patient Name</span>
                  <strong className="font-bold">{patient.name}</strong>
                </div>
                <div>
                  <span className={`block text-[11px] ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Demographics</span>
                  <strong className="font-bold">{patient.age}y {patient.gender}</strong>
                </div>
                <div>
                  <span className={`block text-[11px] ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>eGFR / Renal Function</span>
                  <strong className="text-amber-500 font-bold">{patient.egfr ?? 'N/A'} mL/min</strong>
                </div>
                <div>
                  <span className={`block text-[11px] ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Documented Allergies</span>
                  <strong className="text-rose-500 font-bold">{patient.allergies.length > 0 ? patient.allergies.join(', ') : 'None'}</strong>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-bold text-sm">Active Prescription Regimen</h4>
                <div className={`border rounded-xl overflow-hidden ${theme === 'dark' ? 'border-slate-800' : 'border-slate-200'}`}>
                  <table className="w-full text-left text-xs">
                    <thead className={`font-semibold border-b ${theme === 'dark' ? 'bg-slate-900 text-slate-400 border-slate-800' : 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                      <tr>
                        <th className="p-3">Medication</th>
                        <th className="p-3">Dosage & Frequency</th>
                        <th className="p-3">Indication</th>
                        <th className="p-3">Prescriber</th>
                      </tr>
                    </thead>
                    <tbody className={`divide-y ${theme === 'dark' ? 'divide-slate-800' : 'divide-slate-200'}`}>
                      {medications.map((m) => (
                        <tr key={m.id} className={theme === 'dark' ? 'hover:bg-slate-900/50' : 'hover:bg-slate-50'}>
                          <td className="p-3 font-bold">{m.name}</td>
                          <td className="p-3">{m.dosage} ({m.frequency})</td>
                          <td className="p-3 opacity-80">{m.indication}</td>
                          <td className="p-3 opacity-80">{m.prescribing_doctor}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className={`p-4 rounded-xl border text-xs space-y-2 ${
                theme === 'dark' ? 'bg-teal-950/20 border-teal-900/40 text-slate-300' : 'bg-teal-50 border-teal-200 text-teal-900'
              }`}>
                <h4 className="font-bold text-teal-500 flex items-center gap-1.5">
                  <Info className="w-4 h-4" />
                  Clinical Decision Support Notice & Disclaimer
                </h4>
                <p className="leading-relaxed opacity-90">
                  MedGuardian AI is an assistive decision support platform. Pharmacological recommendations are derived from integrated clinical knowledge graphs, FDA labeling, and WHO formulations. Final prescription decisions remain the sole responsibility of the licensed attending physician.
                </p>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Profile Edit Modal */}
      {showProfileModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className={`panel-surface rounded-3xl p-6 max-w-lg w-full shadow-2xl relative`}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-base font-bold flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-teal-500" /> Edit Patient Clinical Profile
              </h3>
              <button onClick={() => setShowProfileModal(false)} className="hover:opacity-70">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateProfile} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium mb-1">Age</label>
                  <input
                    type="number"
                    value={profileForm.age}
                    onChange={e => setProfileForm({ ...profileForm, age: Number(e.target.value) })}
                    className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1">Gender</label>
                  <select
                    value={profileForm.gender}
                    onChange={e => setProfileForm({ ...profileForm, gender: e.target.value })}
                    className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                  >
                    <option value="Female">Female</option>
                    <option value="Male">Male</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium mb-1">eGFR (mL/min)</label>
                  <input
                    type="number"
                    value={profileForm.egfr}
                    onChange={e => setProfileForm({ ...profileForm, egfr: e.target.value })}
                    className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1">Creatinine (mg/dL)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={profileForm.creatinine}
                    onChange={e => setProfileForm({ ...profileForm, creatinine: e.target.value })}
                    className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                  />
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2 font-medium my-2">
                  <input
                    type="checkbox"
                    checked={profileForm.pregnancy_status}
                    onChange={e => setProfileForm({ ...profileForm, pregnancy_status: e.target.checked })}
                    className="rounded text-teal-500"
                  />
                  <span>Is Pregnant (Female profile only)</span>
                </label>
              </div>

              <div>
                <label className="block font-medium mb-1">Chronic Diseases (comma separated)</label>
                <input
                  type="text"
                  value={profileForm.chronic_diseases}
                  onChange={e => setProfileForm({ ...profileForm, chronic_diseases: e.target.value })}
                  placeholder="Stage 3 CKD, Hypertension, Type 2 Diabetes"
                  className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                />
              </div>

              <div>
                <label className="block font-medium mb-1">Documented Allergies (comma separated)</label>
                <input
                  type="text"
                  value={profileForm.allergies}
                  onChange={e => setProfileForm({ ...profileForm, allergies: e.target.value })}
                  placeholder="Penicillin, Sulfa Drugs"
                  className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowProfileModal(false)}
                  className={`px-4 py-2 rounded-xl font-bold ${theme === 'dark' ? 'bg-slate-800 text-slate-300' : 'bg-slate-200 text-slate-700'}`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-slate-950 font-bold rounded-xl shadow-md shadow-teal-500/20"
                >
                  Save Profile Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Medication Modal */}
      {showAddMedModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className={`panel-surface rounded-3xl p-6 max-w-md w-full shadow-2xl relative`}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-base font-bold flex items-center gap-2">
                <Plus className="w-4 h-4 text-teal-500" /> Add Prescription to Cabinet
              </h3>
              <button onClick={() => setShowAddMedModal(false)} className="hover:opacity-70">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddMedication} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium mb-1">Medication Name</label>
                <input
                  type="text"
                  required
                  value={newMedForm.name}
                  onChange={e => setNewMedForm({ ...newMedForm, name: e.target.value })}
                  placeholder="e.g. Lisinopril, Amoxicillin, Warfarin, Metformin"
                  className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium mb-1">Dosage</label>
                  <input
                    type="text"
                    value={newMedForm.dosage}
                    onChange={e => setNewMedForm({ ...newMedForm, dosage: e.target.value })}
                    placeholder="10mg"
                    className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                  />
                </div>

                <div>
                  <label className="block font-medium mb-1">Frequency</label>
                  <input
                    type="text"
                    value={newMedForm.frequency}
                    onChange={e => setNewMedForm({ ...newMedForm, frequency: e.target.value })}
                    placeholder="Once daily"
                    className={`w-full border rounded-xl p-2.5 ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}
                  />
                </div>
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddMedModal(false)}
                  className={`px-4 py-2 rounded-xl font-bold ${theme === 'dark' ? 'bg-slate-800 text-slate-300' : 'bg-slate-200 text-slate-700'}`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-slate-950 font-bold rounded-xl shadow-md shadow-teal-500/20"
                >
                  Save Medication
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
