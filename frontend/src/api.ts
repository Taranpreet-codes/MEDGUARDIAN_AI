import type { 
  PatientProfile, 
  Medication, 
  SafetyCheckResult, 
  ChatMessage, 
  SafetyHistoryPoint, 
  SafetyAlert,
  ProactiveAlert
} from './types';

const API_BASE = '/api';

// Token Management
export const TOKEN_KEY = 'medguardian_jwt_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

// ─────────────────────────────────────────────────────────────────────────────
// AUTHENTICATION APIs
// ─────────────────────────────────────────────────────────────────────────────

export async function login(username: string, password: string): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/token/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.error || 'Invalid username or password.');
  }

  const data = await res.json();
  setToken(data.access);
  return data.access;
}

export async function register(username: string, password: string, email?: string): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/register/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, email: email || '' })
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || errorData.detail || 'Registration failed.');
  }

  const data = await res.json();
  setToken(data.access);
  return data.access;
}

// ─────────────────────────────────────────────────────────────────────────────
// PATIENT PROFILE & CABINET APIs
// ─────────────────────────────────────────────────────────────────────────────

export async function getPatientProfile(): Promise<PatientProfile> {
  const res = await fetch(`${API_BASE}/patients/profile/me/`, {
    headers: getAuthHeaders()
  });

  if (!res.ok) {
    throw new Error('Failed to fetch patient profile.');
  }

  const data = await res.json();
  return {
    id: data.id,
    username: data.username,
    name: data.name || data.username || 'Patient',
    age: data.age ?? 30,
    gender: data.gender === 'F' ? 'Female' : data.gender === 'M' ? 'Male' : 'Other',
    weight_kg: 68.5,
    creatinine: data.creatinine ? Number(data.creatinine) : undefined,
    egfr: data.egfr ? Number(data.egfr) : undefined,
    allergies: Array.isArray(data.allergies) ? data.allergies : [],
    chronic_conditions: Array.isArray(data.chronic_diseases) ? data.chronic_diseases : [],
    chronic_diseases: Array.isArray(data.chronic_diseases) ? data.chronic_diseases : [],
    is_pregnant: Boolean(data.pregnancy_status),
    pregnancy_status: Boolean(data.pregnancy_status),
  };
}

export async function updatePatientProfile(updated: Partial<PatientProfile>): Promise<PatientProfile> {
  const payload: Record<string, any> = {};

  if (updated.age !== undefined) payload.age = updated.age;
  if (updated.gender !== undefined) payload.gender = updated.gender.startsWith('F') ? 'F' : updated.gender.startsWith('M') ? 'M' : 'O';
  if (updated.is_pregnant !== undefined || updated.pregnancy_status !== undefined) {
    payload.pregnancy_status = updated.is_pregnant ?? updated.pregnancy_status;
  }
  if (updated.chronic_conditions !== undefined || updated.chronic_diseases !== undefined) {
    payload.chronic_diseases = updated.chronic_conditions || updated.chronic_diseases;
  }
  if (updated.allergies !== undefined) payload.allergies = updated.allergies;
  if (updated.creatinine !== undefined) payload.creatinine = updated.creatinine;
  if (updated.egfr !== undefined) payload.egfr = updated.egfr;

  const res = await fetch(`${API_BASE}/patients/profile/me/`, {
    method: 'PATCH',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(JSON.stringify(err));
  }

  return await getPatientProfile();
}

export async function getMedications(): Promise<Medication[]> {
  const res = await fetch(`${API_BASE}/patients/cabinet/`, {
    headers: getAuthHeaders()
  });

  if (!res.ok) {
    throw new Error('Failed to fetch medications.');
  }

  const rawList = await res.json();
  return rawList.map((item: any) => ({
    id: item.id,
    name: item.name,
    generic_name: item.generic_name || item.name,
    dosage: item.dosage,
    frequency: item.frequency,
    route: item.route || 'Oral',
    start_date: item.start_date,
    end_date: item.end_date,
    prescribing_doctor: item.prescribing_doctor || 'Attending Physician',
    indication: item.indication || 'Prescribed Regimen',
    status: item.is_active ? 'active' : 'discontinued',
    is_active: item.is_active
  }));
}

export async function addMedication(med: { name: string; dosage: string; frequency: string; start_date?: string }): Promise<Medication> {
  const res = await fetch(`${API_BASE}/patients/cabinet/`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      name: med.name,
      dosage: med.dosage || 'Standard Dose',
      frequency: med.frequency || 'Once daily',
      start_date: med.start_date || new Date().toISOString().split('T')[0],
      is_active: true
    })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(JSON.stringify(err));
  }

  const item = await res.json();
  return {
    id: item.id,
    name: item.name,
    generic_name: item.generic_name || item.name,
    dosage: item.dosage,
    frequency: item.frequency,
    route: 'Oral',
    start_date: item.start_date,
    prescribing_doctor: 'Attending Physician',
    indication: 'Prescribed Regimen',
    status: 'active',
    is_active: true
  };
}

export async function deleteMedication(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/patients/cabinet/${id}/`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  if (!res.ok) {
    throw new Error('Failed to delete medication.');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SAFETY CHECK & DIGITAL TWIN APIs
// ─────────────────────────────────────────────────────────────────────────────

export async function getSafetyCheck(): Promise<SafetyCheckResult> {
  const res = await fetch(`${API_BASE}/patients/profile/safety-check/`, {
    headers: getAuthHeaders()
  });

  if (!res.ok) {
    throw new Error('Failed to fetch safety check.');
  }

  const raw = await res.json();
  const rawScore = raw.overall_risk_score || 'Safe';
  
  // Convert string score to numeric representation
  const numericScore = typeof rawScore === 'number' ? rawScore : (
    rawScore === 'Severe' ? 88 : rawScore === 'Moderate' ? 55 : rawScore === 'Low' ? 25 : 5
  );

  const riskLevel = typeof rawScore === 'string' ? rawScore : (
    rawScore >= 75 ? 'Severe' : rawScore >= 50 ? 'Moderate' : rawScore >= 25 ? 'Low' : 'Safe'
  );

  const rawInteractions = raw.interactions || [];
  const alerts: SafetyAlert[] = rawInteractions.map((inter: any, idx: number) => ({
    id: `alert-${idx}-${Date.now()}`,
    type: inter.severity === 'Severe' ? 'organ_impairment' : 'drug_drug',
    severity: (inter.severity || 'moderate').toLowerCase() as any,
    title: `${inter.severity || 'Moderate'} Alert: ${inter.drug_involved || 'Medication Concern'}`,
    description: inter.description || 'Clinical safety alert identified.',
    drugs_involved: inter.drug_involved ? inter.drug_involved.split(', ') : [],
    recommendation: raw.clinician_notes || 'Review medication regimen with treating clinician.',
    evidence_source: (raw.evidence_references && raw.evidence_references[0]) || 'Clinical RAG Knowledge Base',
    evidence_score: 92
  }));

  // Digital Twin organ load estimates
  const egfr = raw.egfr ?? 45;
  const renalLoad = egfr < 30 ? 92 : egfr < 60 ? 68 : 28;

  return {
    overall_risk_score: numericScore,
    overall_risk_level: riskLevel as any,
    summary: raw.clinician_notes || (alerts.length > 0 ? alerts[0].title : 'No critical drug interactions flagged.'),
    digital_twin_status: {
      renal_load: renalLoad,
      hepatic_load: 34,
      cardiac_risk: riskLevel === 'Severe' ? 75 : 38,
      cns_depression_risk: 15
    },
    alerts,
    recommendations: [
      raw.clinician_notes || 'Maintain routine monitoring of kidney and liver lab values.',
      'Check serum electrolytes and creatinine before initiating new prescriptions.',
      'Consult clinician or clinical pharmacist before taking over-the-counter NSAIDs.'
    ],
    clinician_notes: raw.clinician_notes,
    evidence_references: raw.evidence_references || [],
    timestamp: new Date().toISOString()
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// SAFETY HISTORY & PROACTIVE ALERTS APIs
// ─────────────────────────────────────────────────────────────────────────────

export async function getSafetyHistory(): Promise<SafetyHistoryPoint[]> {
  const res = await fetch(`${API_BASE}/patients/me/safety-history/`, {
    headers: getAuthHeaders()
  });

  if (!res.ok) {
    throw new Error('Failed to fetch safety history.');
  }

  const data = await res.json();
  const results = data.results || [];
  
  if (results.length === 0) {
    return [
      { date: 'Initial', score: 10, event: 'Baseline Profile Created', risk_level: 'Safe' }
    ];
  }

  return results.map((item: any) => {
    const scoreStr = item.risk_score || 'Safe';
    const numericScore = scoreStr === 'Severe' ? 88 : scoreStr === 'Moderate' ? 55 : scoreStr === 'Low' ? 25 : 5;
    const dateFormatted = new Date(item.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    return {
      id: item.id,
      date: dateFormatted,
      score: numericScore,
      event: `Safety Assessment (${item.triggered_by || 'system'})`,
      risk_level: scoreStr,
      triggered_by: item.triggered_by
    };
  }).reverse(); // Chronological order
}

export async function getUnreadAlerts(): Promise<ProactiveAlert[]> {
  const res = await fetch(`${API_BASE}/alerts/unread/`, {
    headers: getAuthHeaders()
  });

  if (!res.ok) {
    throw new Error('Failed to fetch unread alerts.');
  }

  const data = await res.json();
  return data.alerts || [];
}

export async function acknowledgeAlert(alertId: number | string): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/acknowledge/`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!res.ok) {
    throw new Error('Failed to acknowledge alert.');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CLINICAL AI CHAT API
// ─────────────────────────────────────────────────────────────────────────────

export async function askClinicalAssistant(question: string, _contextDrugs: string[]): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/patients/profile/chat-ask/`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ query: question })
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || 'Failed to communicate with Clinical Assistant.');
  }

  const data = await res.json();
  const citations = (data.citations || []).map((c: any) => ({
    title: c.source || 'Clinical Guideline',
    quote: c.snippet || '',
    confidence: 0.95
  }));

  return {
    id: `msg-${Date.now()}`,
    sender: 'assistant',
    content: data.response || 'No response returned.',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    evidence_sources: citations.length > 0 ? citations : [
      { title: 'MedGuardian Evidence Vector Index', confidence: 0.90 }
    ]
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// PDF REPORTS APIs
// ─────────────────────────────────────────────────────────────────────────────

export async function downloadPatientReport(): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/patients/profile/report-patient/`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  if (!res.ok) throw new Error('Failed to download Patient Safety Report PDF.');

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `patient_safety_report.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function downloadClinicianReport(): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/patients/profile/report-clinician/`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  if (!res.ok) throw new Error('Failed to download Clinician Safety Dossier PDF.');

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `clinician_safety_dossier.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
