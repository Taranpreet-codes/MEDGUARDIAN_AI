import React, { useState } from 'react';
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
  User, 
  BookOpen, 
  CheckCircle2, 
  HeartPulse, 
  Search, 
  Sparkles, 
  Info, 
  RefreshCw, 
  Sliders 
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
import { 
  mockPatient, 
  mockMedications, 
  mockSafetyCheck, 
  mockHistory, 
  mockAlertsStream,
  evaluateNewMedication, 
  askClinicalAssistant 
} from './api';
import type { Medication, SafetyCheckResult, ChatMessage, SafetyAlert } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'cabinet' | 'chat' | 'history' | 'reports'>('dashboard');
  const [patient] = useState(mockPatient);
  const [medications, setMedications] = useState<Medication[]>(mockMedications);
  const [safetyCheck, setSafetyCheck] = useState<SafetyCheckResult>(mockSafetyCheck);
  const [alertsStream, setAlertsStream] = useState<SafetyAlert[]>(mockAlertsStream);
  
  // Simulator state
  const [simulatedDrug, setSimulatedDrug] = useState('');
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<SafetyCheckResult | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      sender: 'assistant',
      content: `Hello! I am MedGuardian AI, your clinical decision support & medication safety digital twin. I have loaded Eleanor Vance's active profile (4 active medications, eGFR 45 mL/min/1.73m², Penicillin allergy).\n\nHow can I assist you with clinical guidelines, drug safety, or dosage adjustments today?`,
      timestamp: '10:00 AM',
      evidence_sources: [
        { title: 'MedGuardian Clinical Knowledge Graph & RAG Core v2.0' }
      ]
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isAiThinking, setIsAiThinking] = useState(false);

  // Fast suggestion prompts
  const samplePrompts = [
    'Can the patient take Ibuprofen for knee pain?',
    'Evaluate Metformin dosage for eGFR of 45',
    'What are the bleeding risks of Warfarin with antibiotics?',
    'Is alcohol safe with this medication regimen?'
  ];

  const handleSimulate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!simulatedDrug.trim()) return;

    setIsSimulating(true);
    setTimeout(() => {
      const result = evaluateNewMedication(simulatedDrug, medications, patient);
      setSimulationResult(result);
      setIsSimulating(false);
    }, 400);
  };

  const handleCommitMedication = (drugName: string) => {
    const newMed: Medication = {
      id: Date.now(),
      name: drugName,
      generic_name: drugName,
      dosage: 'Standard Clinical Dose',
      frequency: 'As prescribed',
      route: 'Oral',
      start_date: new Date().toISOString().split('T')[0],
      prescribing_doctor: 'Attending Clinician',
      indication: 'Simulated Order Entry',
      status: 'active'
    };

    const updatedMeds = [newMed, ...medications];
    setMedications(updatedMeds);
    if (simulationResult) {
      setSafetyCheck(simulationResult);
    } else {
      setSafetyCheck(evaluateNewMedication(drugName, updatedMeds, patient));
    }
    setSimulatedDrug('');
    setSimulationResult(null);
    setActiveTab('dashboard');
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

    const contextDrugs = medications.map(m => m.name);
    const assistantMsg = await askClinicalAssistant(text, contextDrugs);

    setMessages(prev => [...prev, assistantMsg]);
    setIsAiThinking(false);
  };

  const dismissAlert = (id: string) => {
    setAlertsStream(prev => prev.filter(a => a.id !== id));
  };

  const getRiskColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'critical': return 'text-rose-400 bg-rose-950/50 border-rose-800/80';
      case 'high': return 'text-amber-400 bg-amber-950/50 border-amber-800/80';
      case 'moderate': return 'text-yellow-300 bg-yellow-950/40 border-yellow-700/60';
      default: return 'text-teal-300 bg-teal-950/40 border-teal-700/60';
    }
  };

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
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-teal-950 text-teal-300 border border-teal-800 rounded-full">v2.0 Beta</span>
            </div>
            <p className="text-xs text-slate-400">Clinical Decision Support & Medication Digital Twin</p>
          </div>
        </div>

        {/* Patient Quick Glance Badge */}
        <div className="flex items-center gap-3 bg-slate-900/90 border border-slate-800 px-4 py-2 rounded-xl">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-teal-400 font-bold text-xs">
            EV
          </div>
          <div className="text-xs">
            <div className="font-semibold text-slate-200 flex items-center gap-2">
              {patient.name} <span className="text-slate-400 font-normal">({patient.age}y {patient.gender})</span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center gap-2">
              <span>eGFR: <strong className="text-amber-300">{patient.egfr} mL/min</strong></span>
              <span>•</span>
              <span>Allergies: <strong className="text-rose-400">Penicillin</strong></span>
            </div>
          </div>
        </div>

        {/* Global Risk Badge */}
        <div className="flex items-center gap-3">
          <div className={`px-3 py-1.5 rounded-xl border flex items-center gap-2 ${getRiskColor(safetyCheck.overall_risk_level)}`}>
            {safetyCheck.overall_risk_level === 'Critical' || safetyCheck.overall_risk_level === 'High' ? (
              <ShieldAlert className="w-4 h-4" />
            ) : (
              <ShieldCheck className="w-4 h-4" />
            )}
            <span className="text-xs font-bold uppercase tracking-wider">
              {safetyCheck.overall_risk_level} Risk ({safetyCheck.overall_risk_score}/100)
            </span>
          </div>
        </div>
      </header>

      {/* Proactive Alerts Stream Banner */}
      {alertsStream.length > 0 && (
        <div className="bg-gradient-to-r from-rose-950/80 via-slate-900/90 to-rose-950/80 border-b border-rose-900/50 px-4 lg:px-8 py-2 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2 text-rose-300">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 animate-pulse" />
            <span className="font-semibold text-rose-200">Proactive Alert:</span>
            <span className="line-clamp-1">{alertsStream[0].title}</span>
          </div>
          <button 
            onClick={() => dismissAlert(alertsStream[0].id)}
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
          {/* TAB 1: DIGITAL TWIN SAFETY DASHBOARD */}
          {activeTab === 'dashboard' && (
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
                  <span className="text-[11px] text-slate-500 mt-2 block">eGFR: 45 (Moderate Risk)</span>
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
                  <span className="text-[11px] text-slate-500 mt-2 block">ALT/AST within normal</span>
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
                  <span className="text-[11px] text-slate-500 mt-2 block">AFib + Hypertension</span>
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
                  <span className="text-xs text-slate-400">Multi-factor Evidence Evaluation</span>
                </div>

                <div className="space-y-4">
                  {safetyCheck.alerts.map((alert: SafetyAlert) => (
                    <div 
                      key={alert.id} 
                      className={`p-4 rounded-xl border transition-all ${
                        alert.severity === 'critical' 
                          ? 'bg-rose-950/30 border-rose-800/80 text-rose-100'
                          : alert.severity === 'high'
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
                        {alert.evidence_score && (
                          <span className="text-[11px] text-slate-400 font-mono bg-slate-800/90 px-2 py-0.5 rounded">
                            Evidence: {alert.evidence_score}%
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed mb-2.5">{alert.description}</p>

                      {alert.mechanism && (
                        <div className="text-[11px] text-slate-400 bg-slate-950/60 p-2 rounded-lg mb-2.5 border border-slate-800">
                          <strong className="text-slate-300">Biochemical Mechanism:</strong> {alert.mechanism}
                        </div>
                      )}

                      <div className="text-xs text-teal-300 bg-teal-950/40 p-2.5 rounded-lg border border-teal-900/60 flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-teal-400 flex-shrink-0 mt-0.5" />
                        <div>
                          <strong>Clinical Recommendation:</strong> {alert.recommendation}
                        </div>
                      </div>

                      {alert.evidence_source && (
                        <div className="mt-2 text-[10px] text-slate-500 flex items-center gap-1">
                          <BookOpen className="w-3 h-3" />
                          <span>Source: {alert.evidence_source}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
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
                  Test the safety impact of prescribing or dispensing a candidate medication against Eleanor's complete digital twin before committing.
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
                    onClick={() => { setSimulatedDrug('Ibuprofen'); }}
                    className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-rose-300 border border-rose-900/60"
                  >
                    + Ibuprofen (NSAID Risk)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => { setSimulatedDrug('Amoxicillin'); }}
                    className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-amber-300 border border-amber-900/60"
                  >
                    + Amoxicillin (Allergy Risk)
                  </button>
                  <button 
                    type="button" 
                    onClick={() => { setSimulatedDrug('Ciprofloxacin'); }}
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
                        <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${getRiskColor(simulationResult.overall_risk_level)}`}>
                          Projected: {simulationResult.overall_risk_level} ({simulationResult.overall_risk_score}/100)
                        </span>
                        <h4 className="font-semibold text-xs text-white">{simulationResult.summary}</h4>
                      </div>
                      <button
                        onClick={() => handleCommitMedication(simulatedDrug)}
                        className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-teal-300 text-xs font-semibold rounded-lg border border-teal-800/80 transition-all"
                      >
                        Add to Cabinet
                      </button>
                    </div>

                    <div className="text-xs text-slate-300 space-y-1.5 mt-2">
                      {simulationResult.alerts.slice(0, 1).map((alert: SafetyAlert) => (
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
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {medications.map((med) => (
                    <div key={med.id} className="glass-card p-4 rounded-xl border border-slate-800 flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <h4 className="font-bold text-sm text-white">{med.name}</h4>
                          <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-teal-950 text-teal-300 border border-teal-800">
                            {med.dosage}
                          </span>
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
                    <p className="text-[10px] text-slate-400">Grounded in WHO Essential Medicines, FDA Prescribing Labels & KDIGO Guidelines</p>
                  </div>
                </div>
                <span className="text-[11px] text-teal-400 font-mono bg-teal-950/60 px-2 py-0.5 rounded border border-teal-800">
                  RAG Active
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
                      {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
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
                          {msg.evidence_sources.map((src: { title: string; confidence?: number; quote?: string }, idx: number) => (
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
                  placeholder="Ask a clinical question about Eleanor's medications, dosages, or side-effects..."
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
                    <p className="text-xs text-slate-400">Tracking cumulative risk index through past regimen adjustments</p>
                  </div>
                </div>

                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={mockHistory} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.4}/>
                          <stop offset="95%" stopColor="#14b8a6" stopOpacity={0.0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
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
                  {mockHistory.map((pt, i) => (
                    <div key={i} className="flex items-start gap-3 relative">
                      {i < mockHistory.length - 1 && (
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
          {activeTab === 'reports' && (
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <h3 className="font-bold text-lg text-white">Comprehensive Clinical Decision Summary</h3>
                  <p className="text-xs text-slate-400">Generated for Patient & Provider Review</p>
                </div>
                <button 
                  onClick={() => window.print()}
                  className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-teal-300 text-xs font-semibold rounded-xl border border-slate-700 flex items-center gap-1.5 transition-all"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Print / Export Summary
                </button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-400 block text-[11px]">Patient Name</span>
                  <strong className="text-white">{patient.name}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Demographics</span>
                  <strong className="text-white">{patient.age}y {patient.gender} ({patient.weight_kg}kg)</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">eGFR / Renal Function</span>
                  <strong className="text-amber-300">{patient.egfr} mL/min (Stage 3a CKD)</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Documented Allergies</span>
                  <strong className="text-rose-400">{patient.allergies.join(', ')}</strong>
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
    </div>
  );
}
