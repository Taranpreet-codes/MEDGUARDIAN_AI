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
  X
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
  const [profileForm, setProfileForm] = useState<{
    age: number;
    gender: string;
    pregnancy_status: boolean;
    egfr: string;
    creatinine: string;
    chronic_diseases: string;
    allergies: string;
  }>({
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

      // Initial Chat Welcome message
      setMessages([
        {
          id: 'init-1',
          sender: 'assistant',
          content: `Hello! I am MedGuardian AI, your clinical decision support & medication safety digital twin.\n\n` +
            `Active Profile Loaded: ${prof.name} (${prof.age}y ${prof.gender}, ` +
            `${meds.length} active medications in cabinet, eGFR: ${prof.egfr || 'N/A'}).\n\n` +
            `How can I assist you with clinical guidelines, drug interactions, or safety assessments today?`,
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
          // Refresh safety check and history when new alert arrives
          getSafetyCheck().then(setSafetyCheck).catch(() => {});
          getSafetyHistory().then(setSafetyHistory).catch(() => {});
        }
      } catch (_e) {
        // Heartbeat or pulse parse
      }
    };

    eventSource.onerror = (_err) => {
      // Automatic browser reconnects; close if unauthenticated
      if (!getToken()) eventSource.close();
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

      // Re-trigger safety check and history
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

      // Refresh data
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
    if (!confirm('Are you sure you want to remove this medication from your cabinet?')) return;
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
      // Temporarily add med to cabinet, evaluate, then delete or test
      const tempMed = await addMedication({
        name: simulatedDrug,
        dosage: 'Standard Dosage',
        frequency: 'As needed'
      });

      const check = await getSafetyCheck();
      setSimulationResult(check);

      // Remove temp med unless committed
      await deleteMedication(tempMed.id);
      await getMedications().then(setMedications);
    } catch (_err) {
      // Fallback local preview simulation
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

  const getRiskColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'critical':
      case 'severe': return 'text-rose-400 bg-rose-950/50 border-rose-800/80';
      case 'high': return 'text-amber-400 bg-amber-950/50 border-amber-800/80';
      case 'moderate': return 'text-yellow-300 bg-yellow-950/40 border-yellow-700/60';
      default: return 'text-teal-300 bg-teal-950/40 border-teal-700/60';
    }
  };

  // Unauthenticated -> Show Auth Page
  if (!token) {
    return <AuthView onAuthSuccess={handleAuthSuccess} />;
  }

  // Loading state
  if (loading && !patient) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
        <RefreshCw className="w-8 h-8 text-teal-400 animate-spin mb-3" />
        <p className="text-xs text-slate-400">Syncing with MedGuardian AI backend & Digital Twin engine...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-teal-500 selection:text-white">
      {/* Top Header */}
      <header className="sticky top-0 z-40 glass-panel border-b border-slate-800/80 px-4 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-gradient-to-tr from-teal-600 to-cyan-400 text-slate-950 shadow-lg shadow-teal-500/20">
            <HeartPulse className="w-6 h-6 stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-white tracking-tight">MedGuardian<span className="text-teal-400 font-extrabold ml-0.5">AI</span></span>
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-teal-950 text-teal-300 border border-teal-800 rounded-full">v2.0 Connected</span>
            </div>
            <p className="text-xs text-slate-400">Clinical Decision Support & Medication Digital Twin</p>
          </div>
        </div>

        {/* Patient Quick Glance Badge & Profile Edit */}
        {patient && (
          <div className="flex items-center gap-3 bg-slate-900/90 border border-slate-800 px-4 py-2 rounded-xl">
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-teal-400 font-bold text-xs">
              {patient.name.substring(0, 2).toUpperCase()}
            </div>
            <div className="text-xs">
              <div className="font-semibold text-slate-200 flex items-center gap-2">
                {patient.name} <span className="text-slate-400 font-normal">({patient.age}y {patient.gender})</span>
              </div>
              <div className="text-[11px] text-slate-400 flex items-center gap-2">
                <span>eGFR: <strong className="text-amber-300">{patient.egfr ?? 'N/A'} mL/min</strong></span>
                <span>•</span>
                <span>Allergies: <strong className="text-rose-400">{patient.allergies.length > 0 ? patient.allergies.join(', ') : 'None'}</strong></span>
              </div>
            </div>
            <button
              onClick={() => setShowProfileModal(true)}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all ml-1"
              title="Edit Patient Profile"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Global Risk Badge & Logout */}
        <div className="flex items-center gap-3">
          {safetyCheck && (
            <div className={`px-3 py-1.5 rounded-xl border flex items-center gap-2 ${getRiskColor(String(safetyCheck.overall_risk_level))}`}>
              {String(safetyCheck.overall_risk_level).toLowerCase() === 'severe' || String(safetyCheck.overall_risk_level).toLowerCase() === 'high' ? (
                <ShieldAlert className="w-4 h-4" />
              ) : (
                <ShieldCheck className="w-4 h-4" />
              )}
              <span className="text-xs font-bold uppercase tracking-wider">
                {safetyCheck.overall_risk_level} Risk ({safetyCheck.overall_risk_score}/100)
              </span>
            </div>
          )}

          <button
            onClick={handleLogout}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition-all flex items-center gap-1.5 text-xs"
            title="Sign Out"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Proactive Alerts Stream Banner */}
      {proactiveAlerts.length > 0 && (
        <div className="bg-gradient-to-r from-rose-950/80 via-slate-900/90 to-rose-950/80 border-b border-rose-900/50 px-4 lg:px-8 py-2 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2 text-rose-300">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 animate-pulse" />
            <span className="font-semibold text-rose-200">Proactive Alert ({proactiveAlerts[0].severity}):</span>
            <span className="line-clamp-1">{proactiveAlerts[0].message}</span>
          </div>
          <button 
            onClick={() => handleDismissAlert(proactiveAlerts[0].id)}
            className="text-slate-400 hover:text-slate-200 text-[11px] underline ml-4 whitespace-nowrap"
          >
            Acknowledge
          </button>
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex flex-col md:flex-row max-w-7xl w-full mx-auto p-4 lg:p-6 gap-6">
        
        {/* Navigation Sidebar / Tabs */}
        <aside className="w-full md:w-64 flex-shrink-0 flex md:flex-col gap-1.5 glass-panel p-2.5 rounded-2xl border border-slate-800 self-start">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'dashboard'
                ? 'bg-teal-500/10 text-teal-300 border border-teal-500/30 glow-teal'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Activity className="w-4 h-4 text-teal-400" />
            <span>Digital Twin Safety</span>
          </button>

          <button
            onClick={() => setActiveTab('cabinet')}
            className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'cabinet'
                ? 'bg-teal-500/10 text-teal-300 border border-teal-500/30 glow-teal'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Pill className="w-4 h-4 text-cyan-400" />
            <div className="flex-1 flex justify-between items-center">
              <span>Medication Cabinet</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">{medications.length}</span>
            </div>
          </button>

          <button
            onClick={() => setActiveTab('chat')}
            className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'chat'
                ? 'bg-teal-500/10 text-teal-300 border border-teal-500/30 glow-teal'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Bot className="w-4 h-4 text-emerald-400" />
            <span>Clinical AI (RAG)</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'history'
                ? 'bg-teal-500/10 text-teal-300 border border-teal-500/30 glow-teal'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <History className="w-4 h-4 text-amber-400" />
            <span>Safety History</span>
          </button>

          <button
            onClick={() => setActiveTab('reports')}
            className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'reports'
                ? 'bg-teal-500/10 text-teal-300 border border-teal-500/30 glow-teal'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <FileText className="w-4 h-4 text-indigo-400" />
            <span>Clinical Summary</span>
          </button>
        </aside>

        {/* Content Area */}
        <main className="flex-1 min-w-0 flex flex-col">
          {/* Error Banner if any */}
          {errorMsg && (
            <div className="mb-4 p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-200 text-xs flex items-center justify-between">
              <span>{errorMsg}</span>
              <button onClick={() => setErrorMsg('')} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* TAB 1: DIGITAL TWIN SAFETY DASHBOARD */}
          {activeTab === 'dashboard' && safetyCheck && (
            <div className="space-y-6">
              {/* Digital Twin Organ Burden Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="glass-card p-4 rounded-2xl border border-slate-800">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-slate-400 font-medium">Renal Clearance Load</span>
                    <span className="text-xs font-bold text-amber-300">{safetyCheck.digital_twin_status.renal_load}%</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-amber-400 h-full rounded-full transition-all duration-500" 
                      style={{ width: `${safetyCheck.digital_twin_status.renal_load}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-slate-500 mt-2 block">eGFR: {patient?.egfr ?? 'N/A'} mL/min</span>
                </div>

                <div className="glass-card p-4 rounded-2xl border border-slate-800">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-slate-400 font-medium">Hepatic Metabolic Load</span>
                    <span className="text-xs font-bold text-teal-300">{safetyCheck.digital_twin_status.hepatic_load}%</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-teal-400 h-full rounded-full transition-all duration-500" 
                      style={{ width: `${safetyCheck.digital_twin_status.hepatic_load}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-slate-500 mt-2 block">Normal Liver Enzyme Profile</span>
                </div>

                <div className="glass-card p-4 rounded-2xl border border-slate-800">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-slate-400 font-medium">Cardiovascular Risk</span>
                    <span className="text-xs font-bold text-cyan-300">{safetyCheck.digital_twin_status.cardiac_risk}%</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-cyan-400 h-full rounded-full transition-all duration-500" 
                      style={{ width: `${safetyCheck.digital_twin_status.cardiac_risk}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-slate-500 mt-2 block">Cardiovascular Monitor</span>
                </div>

                <div className="glass-card p-4 rounded-2xl border border-slate-800">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-slate-400 font-medium">CNS Burden</span>
                    <span className="text-xs font-bold text-emerald-300">{safetyCheck.digital_twin_status.cns_depression_risk}%</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div 
                      className="bg-emerald-400 h-full rounded-full transition-all duration-500" 
                      style={{ width: `${safetyCheck.digital_twin_status.cns_depression_risk}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-slate-500 mt-2 block">Low sedation profile</span>
                </div>
              </div>

              {/* Active Clinical Safety Warnings & Alerts */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-base text-white flex items-center gap-2">
                    <ShieldAlert className="w-5 h-5 text-amber-400" />
                    Active Safety Alerts ({safetyCheck.alerts.length})
                  </h3>
                  <span className="text-xs text-slate-400">Live Backend Evaluation</span>
                </div>

                {safetyCheck.alerts.length === 0 ? (
                  <div className="p-6 text-center text-xs text-teal-300 bg-teal-950/20 border border-teal-900/50 rounded-xl">
                    <CheckCircle2 className="w-8 h-8 text-teal-400 mx-auto mb-2" />
                    No critical interactions or drug contraindications detected for active regimen.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {safetyCheck.alerts.map((alert: SafetyAlert) => (
                      <div 
                        key={alert.id} 
                        className={`p-4 rounded-xl border transition-all ${
                          String(alert.severity).toLowerCase() === 'severe' || String(alert.severity).toLowerCase() === 'critical'
                            ? 'bg-rose-950/30 border-rose-800/80 text-rose-100'
                            : String(alert.severity).toLowerCase() === 'high' || String(alert.severity).toLowerCase() === 'moderate'
                            ? 'bg-amber-950/30 border-amber-800/80 text-amber-100'
                            : 'bg-slate-900/80 border-slate-800 text-slate-200'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${getRiskColor(alert.severity)}`}>
                              {alert.severity}
                            </span>
                            <h4 className="font-semibold text-sm text-slate-100">{alert.title}</h4>
                          </div>
                        </div>

                        <p className="text-xs text-slate-300 leading-relaxed mb-2.5">{alert.description}</p>

                        <div className="text-xs text-teal-300 bg-teal-950/40 p-2.5 rounded-lg border border-teal-900/60 flex items-start gap-2">
                          <CheckCircle2 className="w-4 h-4 text-teal-400 flex-shrink-0 mt-0.5" />
                          <div>
                            <strong>Clinical Recommendation:</strong> {alert.recommendation}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Actionable Clinical Directives */}
              <div className="glass-panel p-5 rounded-2xl border border-slate-800">
                <h3 className="font-semibold text-sm text-white mb-3 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-teal-400" />
                  Key Clinical Monitoring Directives
                </h3>
                <ul className="space-y-2 text-xs text-slate-300">
                  {safetyCheck.recommendations.map((rec: string, i: number) => (
                    <li key={i} className="flex items-start gap-2 bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/80">
                      <span className="w-5 h-5 rounded-full bg-teal-950 text-teal-400 border border-teal-800 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
                        {i + 1}
                      </span>
                      <span className="leading-relaxed">{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* TAB 2: MEDICATION CABINET & SIMULATOR */}
          {activeTab === 'cabinet' && (
            <div className="space-y-6">
              {/* Interactive Drug Simulator */}
              <div className="glass-panel p-5 rounded-2xl border border-teal-800/50 bg-gradient-to-b from-teal-950/20 to-slate-900/80">
                <div className="flex items-center gap-2 mb-2">
                  <Sliders className="w-4 h-4 text-teal-400" />
                  <h3 className="font-bold text-sm text-white">Digital Twin Pre-Prescription Simulator</h3>
                </div>
                <p className="text-xs text-slate-400 mb-4">
                  Test the safety impact of prescribing or dispensing a candidate medication against {patient?.name}'s digital twin before committing to cabinet.
                </p>

                <form onSubmit={handleSimulate} className="flex gap-2 mb-3">
                  <input
                    type="text"
                    placeholder="Enter drug name (e.g. Ibuprofen, Amoxicillin, Ciprofloxacin, Acetaminophen)..."
                    value={simulatedDrug}
                    onChange={(e) => setSimulatedDrug(e.target.value)}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
                  />
                  <button
                    type="submit"
                    disabled={isSimulating || !simulatedDrug.trim()}
                    className="px-4 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all"
                  >
                    {isSimulating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                    Simulate Impact
                  </button>
                </form>

                {/* Quick Simulation Chips */}
                <div className="flex flex-wrap gap-2 text-[11px] text-slate-400 items-center">
                  <span>Quick Test:</span>
                  <button 
                    type="button" 
                    onClick={() => setSimulatedDrug('Ibuprofen')}
                    className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-rose-300 border border-rose-900/60"
                  >
                    + Ibuprofen (NSAID Risk)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setSimulatedDrug('Amoxicillin')}
                    className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-amber-300 border border-amber-900/60"
                  >
                    + Amoxicillin (Allergy Risk)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setSimulatedDrug('Ciprofloxacin')}
                    className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-900/60"
                  >
                    + Ciprofloxacin (CYP Interaction)
                  </button>
                </div>

                {/* Simulation Result Box */}
                {simulationResult && (
                  <div className="mt-4 p-4 rounded-xl border bg-slate-950/80 border-slate-800 animate-fadeIn">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${getRiskColor(String(simulationResult.overall_risk_level))}`}>
                          Projected: {simulationResult.overall_risk_level} ({simulationResult.overall_risk_score}/100)
                        </span>
                        <h4 className="font-semibold text-xs text-white">{simulationResult.summary}</h4>
                      </div>
                      <button
                        onClick={handleCommitSimulatedDrug}
                        className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-teal-300 text-xs font-semibold rounded-lg border border-teal-800/80 transition-all"
                      >
                        Add to Cabinet
                      </button>
                    </div>

                    <div className="text-xs text-slate-300 space-y-1.5 mt-2">
                      {simulationResult.alerts.slice(0, 2).map((alert: SafetyAlert) => (
                        <div key={alert.id} className="p-2.5 rounded bg-slate-900 border border-slate-800">
                          <p className="text-xs font-medium text-amber-300 mb-1">{alert.description}</p>
                          <p className="text-[11px] text-teal-300"><strong>Recommendation:</strong> {alert.recommendation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Current Active Medications List */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-base text-white flex items-center gap-2">
                    <Pill className="w-5 h-5 text-cyan-400" />
                    Active Prescriptions & Regimen ({medications.length})
                  </h3>
                  <button
                    onClick={() => setShowAddMedModal(true)}
                    className="px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md shadow-teal-500/20"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Medication
                  </button>
                </div>

                {medications.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-400 bg-slate-900/50 rounded-xl border border-slate-800">
                    No medications in cabinet. Click "Add Medication" to add your first prescription.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {medications.map((med) => (
                      <div key={med.id} className="glass-card p-4 rounded-xl border border-slate-800 flex flex-col justify-between">
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <h4 className="font-bold text-sm text-white">{med.name}</h4>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-teal-950 text-teal-300 border border-teal-800">
                                {med.dosage}
                              </span>
                              <button
                                onClick={() => handleDeleteMedication(med.id)}
                                className="text-slate-500 hover:text-rose-400 transition-colors p-1"
                                title="Remove medication"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                          <p className="text-xs text-slate-400 mb-2">{med.generic_name}</p>
                          
                          <div className="space-y-1 text-xs text-slate-300 mb-3">
                            <div><span className="text-slate-500">Frequency:</span> {med.frequency}</div>
                            <div><span className="text-slate-500">Indication:</span> {med.indication}</div>
                            <div><span className="text-slate-500">Prescriber:</span> {med.prescribing_doctor}</div>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-slate-800 flex justify-between items-center text-[11px] text-slate-400">
                          <span>Started: {med.start_date}</span>
                          <span className="text-emerald-400 font-medium">● Active</span>
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
            <div className="glass-panel rounded-2xl border border-slate-800 flex flex-col h-[650px] overflow-hidden">
              {/* Chat Header */}
              <div className="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-teal-600 flex items-center justify-center text-slate-950 font-bold">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-white">Clinical AI Evidence Chat</h3>
                    <p className="text-[10px] text-slate-400">Grounded in WHO Essential Medicines, FDA Prescribing Labels & Vector RAG Store</p>
                  </div>
                </div>
                <span className="text-[11px] text-teal-400 font-mono bg-teal-950/60 px-2 py-0.5 rounded border border-teal-800">
                  Backend API Live
                </span>
              </div>

              {/* Message Feed */}
              <div className="flex-1 p-4 overflow-y-auto space-y-4">
                {messages.map((msg) => (
                  <div 
                    key={msg.id} 
                    className={`flex gap-3 max-w-2xl ${msg.sender === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
                  >
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                      msg.sender === 'user' 
                        ? 'bg-slate-700 text-slate-200' 
                        : 'bg-teal-600 text-slate-950'
                    }`}>
                      {msg.sender === 'user' ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>

                    <div className={`p-3.5 rounded-2xl text-xs leading-relaxed ${
                      msg.sender === 'user'
                        ? 'bg-teal-700 text-white rounded-tr-none'
                        : 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-none'
                    }`}>
                      <div className="whitespace-pre-wrap">{msg.content}</div>

                      {/* Evidence Citations */}
                      {msg.evidence_sources && msg.evidence_sources.length > 0 && (
                        <div className="mt-3 pt-2.5 border-t border-slate-800 text-[10px] text-slate-400 space-y-1">
                          <span className="font-semibold text-slate-300 block">Grounding Evidence & Citations:</span>
                          {msg.evidence_sources.map((src, idx) => (
                            <div key={idx} className="flex items-center gap-1.5 text-teal-400">
                              <BookOpen className="w-3 h-3 flex-shrink-0" />
                              <span>{src.title}</span>
                              {src.confidence && (
                                <span className="text-slate-500 font-mono">({Math.round(src.confidence * 100)}% match)</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      
                      <span className="block mt-1 text-[9px] text-slate-500 text-right">{msg.timestamp}</span>
                    </div>
                  </div>
                ))}

                {isAiThinking && (
                  <div className="flex gap-3 items-center text-xs text-teal-400 bg-slate-900/60 p-3 rounded-xl border border-slate-800 w-fit">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Searching clinical vector index & synthesizing evidence...</span>
                  </div>
                )}
              </div>

              {/* Suggested Questions */}
              <div className="px-4 py-2 border-t border-slate-800/80 bg-slate-950/40 flex flex-wrap gap-1.5">
                {samplePrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(prompt)}
                    className="text-[11px] px-2.5 py-1 rounded-full bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 transition-all text-left"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              {/* Chat Input Bar */}
              <div className="p-3 border-t border-slate-800 bg-slate-900/80 flex gap-2">
                <input
                  type="text"
                  placeholder={`Ask a clinical question about ${patient?.name || 'patient'}'s medications, dosages, or side-effects...`}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
                />
                <button
                  onClick={() => handleSendMessage()}
                  disabled={!inputMessage.trim() || isAiThinking}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: SAFETY HISTORY & RISK ANALYTICS */}
          {activeTab === 'history' && (
            <div className="space-y-6">
              {/* Longitudinal Risk Trend Chart */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-base text-white flex items-center gap-2">
                      <History className="w-5 h-5 text-amber-400" />
                      Longitudinal Medication Risk Progression
                    </h3>
                    <p className="text-xs text-slate-400">Live timeline generated from backend Celery evaluation audits</p>
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
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} />
                      <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
                      />
                      <Area type="monotone" dataKey="score" stroke="#14b8a6" strokeWidth={2.5} fillOpacity={1} fill="url(#riskGradient)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Event Timeline */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800">
                <h3 className="font-bold text-sm text-white mb-4">Medication Modification Audit Trail</h3>
                <div className="space-y-4">
                  {safetyHistory.map((pt, i) => (
                    <div key={i} className="flex items-start gap-3 relative">
                      {i < safetyHistory.length - 1 && (
                        <div className="absolute left-2.5 top-6 bottom-0 w-0.5 bg-slate-800" />
                      )}
                      <div className="w-5 h-5 rounded-full bg-slate-800 border-2 border-teal-500 z-10 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 glass-card p-3 rounded-xl border border-slate-800/80">
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-semibold text-xs text-white">{pt.event}</span>
                          <span className="text-[10px] text-slate-400 font-mono">{pt.date}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${getRiskColor(pt.risk_level)}`}>
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

          {/* TAB 5: CLINICAL SUMMARY & AUDIT REPORT */}
          {activeTab === 'reports' && patient && (
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
              <div className="flex flex-wrap items-center justify-between border-b border-slate-800 pb-4 gap-3">
                <div>
                  <h3 className="font-bold text-lg text-white">Comprehensive Clinical Decision Summary</h3>
                  <p className="text-xs text-slate-400">Generated directly from Django Backend PDF Engine</p>
                </div>
                
                <div className="flex gap-2">
                  <button 
                    onClick={() => downloadPatientReport()}
                    className="px-3.5 py-2 bg-teal-600 hover:bg-teal-500 text-slate-950 text-xs font-bold rounded-xl flex items-center gap-1.5 transition-all shadow-md shadow-teal-500/20"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Patient Report (PDF)
                  </button>

                  <button 
                    onClick={() => downloadClinicianReport()}
                    className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-teal-300 text-xs font-bold rounded-xl border border-slate-700 flex items-center gap-1.5 transition-all"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    Clinician Dossier (PDF)
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-400 block text-[11px]">Patient Name</span>
                  <strong className="text-white">{patient.name}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Demographics</span>
                  <strong className="text-white">{patient.age}y {patient.gender}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">eGFR / Renal Function</span>
                  <strong className="text-amber-300">{patient.egfr ?? 'N/A'} mL/min</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Documented Allergies</span>
                  <strong className="text-rose-400">{patient.allergies.length > 0 ? patient.allergies.join(', ') : 'None'}</strong>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-bold text-sm text-slate-200">Current Drug Regimen</h4>
                <div className="border border-slate-800 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="p-2.5">Medication</th>
                        <th className="p-2.5">Dosage & Frequency</th>
                        <th className="p-2.5">Indication</th>
                        <th className="p-2.5">Prescriber</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {medications.map((m) => (
                        <tr key={m.id} className="hover:bg-slate-900/40">
                          <td className="p-2.5 font-medium text-white">{m.name}</td>
                          <td className="p-2.5 text-slate-300">{m.dosage} ({m.frequency})</td>
                          <td className="p-2.5 text-slate-400">{m.indication}</td>
                          <td className="p-2.5 text-slate-400">{m.prescribing_doctor}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-teal-950/20 border border-teal-900/40 text-xs space-y-2">
                <h4 className="font-semibold text-teal-300 flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-teal-400" />
                  Clinical Decision Support Notice & Disclaimer
                </h4>
                <p className="text-slate-400 leading-relaxed">
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
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-lg w-full shadow-2xl relative">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-teal-400" /> Edit Patient Clinical Profile
              </h3>
              <button onClick={() => setShowProfileModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateProfile} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Age</label>
                  <input
                    type="number"
                    value={profileForm.age}
                    onChange={e => setProfileForm({ ...profileForm, age: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Gender</label>
                  <select
                    value={profileForm.gender}
                    onChange={e => setProfileForm({ ...profileForm, gender: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                  >
                    <option value="Female">Female</option>
                    <option value="Male">Male</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">eGFR (mL/min)</label>
                  <input
                    type="number"
                    value={profileForm.egfr}
                    onChange={e => setProfileForm({ ...profileForm, egfr: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Creatinine (mg/dL)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={profileForm.creatinine}
                    onChange={e => setProfileForm({ ...profileForm, creatinine: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2 text-slate-300 my-1">
                  <input
                    type="checkbox"
                    checked={profileForm.pregnancy_status}
                    onChange={e => setProfileForm({ ...profileForm, pregnancy_status: e.target.checked })}
                    className="rounded bg-slate-950 border-slate-800 text-teal-500"
                  />
                  <span>Is Pregnant (Female profile only)</span>
                </label>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Chronic Diseases (comma separated)</label>
                <input
                  type="text"
                  value={profileForm.chronic_diseases}
                  onChange={e => setProfileForm({ ...profileForm, chronic_diseases: e.target.value })}
                  placeholder="Stage 3 CKD, Hypertension, Type 2 Diabetes"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Documented Allergies (comma separated)</label>
                <input
                  type="text"
                  value={profileForm.allergies}
                  onChange={e => setProfileForm({ ...profileForm, allergies: e.target.value })}
                  placeholder="Penicillin, Sulfa Drugs"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowProfileModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-slate-950 font-bold rounded-xl"
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
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl relative">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-teal-400" /> Add Prescription to Cabinet
              </h3>
              <button onClick={() => setShowAddMedModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddMedication} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Medication Name</label>
                <input
                  type="text"
                  required
                  value={newMedForm.name}
                  onChange={e => setNewMedForm({ ...newMedForm, name: e.target.value })}
                  placeholder="e.g. Lisinopril, Amoxicillin, Warfarin, Metformin"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Dosage</label>
                  <input
                    type="text"
                    value={newMedForm.dosage}
                    onChange={e => setNewMedForm({ ...newMedForm, dosage: e.target.value })}
                    placeholder="10mg"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Frequency</label>
                  <input
                    type="text"
                    value={newMedForm.frequency}
                    onChange={e => setNewMedForm({ ...newMedForm, frequency: e.target.value })}
                    placeholder="Once daily"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-white"
                  />
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddMedModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-slate-950 font-bold rounded-xl"
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
