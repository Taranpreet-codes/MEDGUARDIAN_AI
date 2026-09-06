export interface PatientProfile {
  id: number;
  username?: string;
  name: string;
  age: number;
  gender: string;
  weight_kg?: number;
  creatinine_clearance?: number;
  creatinine?: number;
  egfr?: number;
  alt?: number;
  ast?: number;
  allergies: string[];
  chronic_conditions: string[];
  chronic_diseases?: string[];
  is_pregnant: boolean;
  pregnancy_status?: boolean;
  is_lactating?: boolean;
  blood_pressure?: string;
}

export interface Medication {
  id: number;
  name: string;
  generic_name: string;
  dosage: string;
  frequency: string;
  route?: string;
  start_date: string;
  end_date?: string;
  prescribing_doctor?: string;
  indication?: string;
  status: 'active' | 'discontinued' | 'completed';
  is_active?: boolean;
}

export interface SafetyAlert {
  id: string;
  type: 'drug_drug' | 'drug_disease' | 'allergy' | 'organ_impairment' | 'cumulative_toxicity' | 'special_population';
  severity: 'low' | 'moderate' | 'high' | 'critical' | 'low' | 'Severe' | 'Moderate' | 'Low' | 'Safe';
  title: string;
  description: string;
  drugs_involved: string[];
  mechanism?: string;
  recommendation: string;
  evidence_source?: string;
  evidence_score?: number;
}

export interface SafetyCheckResult {
  overall_risk_score: number | string;
  overall_risk_level: 'Low' | 'Moderate' | 'High' | 'Critical' | 'Severe' | 'Safe';
  summary: string;
  alerts: SafetyAlert[];
  digital_twin_status: {
    renal_load: number;
    hepatic_load: number;
    cardiac_risk: number;
    cns_depression_risk: number;
  };
  recommendations: string[];
  clinician_notes?: string;
  evidence_references?: string[];
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  evidence_sources?: {
    title: string;
    source?: string;
    confidence?: number;
    quote?: string;
    snippet?: string;
  }[];
}

export interface SafetyHistoryPoint {
  id?: number;
  date: string;
  score: number;
  event: string;
  risk_level: string;
  triggered_by?: string;
}

export interface ProactiveAlert {
  id: number | string;
  severity: string;
  message: string;
  acknowledged: boolean;
  created_at: string;
  assessment_id?: number;
  evidence_references?: string[];
}
