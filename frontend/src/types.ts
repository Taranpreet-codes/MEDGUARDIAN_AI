export interface PatientProfile {
  id: number;
  name: string;
  age: number;
  gender: string;
  weight_kg: number;
  creatinine_clearance?: number;
  egfr?: number;
  alt?: number;
  ast?: number;
  allergies: string[];
  chronic_conditions: string[];
  is_pregnant: boolean;
  is_lactating: boolean;
  blood_pressure?: string;
}

export interface Medication {
  id: number;
  name: string;
  generic_name: string;
  dosage: string;
  frequency: string;
  route: string;
  start_date: string;
  end_date?: string;
  prescribing_doctor?: string;
  indication?: string;
  status: 'active' | 'discontinued' | 'completed';
}

export interface SafetyAlert {
  id: string;
  type: 'drug_drug' | 'drug_disease' | 'allergy' | 'organ_impairment' | 'cumulative_toxicity' | 'special_population';
  severity: 'low' | 'moderate' | 'high' | 'critical';
  title: string;
  description: string;
  drugs_involved: string[];
  mechanism?: string;
  recommendation: string;
  evidence_source?: string;
  evidence_score?: number;
}

export interface SafetyCheckResult {
  overall_risk_score: number;
  overall_risk_level: 'Low' | 'Moderate' | 'High' | 'Critical';
  summary: string;
  alerts: SafetyAlert[];
  digital_twin_status: {
    renal_load: number;
    hepatic_load: number;
    cardiac_risk: number;
    cns_depression_risk: number;
  };
  recommendations: string[];
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  evidence_sources?: {
    title: string;
    doi_or_url?: string;
    confidence?: number;
    quote?: string;
  }[];
}

export interface SafetyHistoryPoint {
  date: string;
  score: number;
  event: string;
  risk_level: string;
}
