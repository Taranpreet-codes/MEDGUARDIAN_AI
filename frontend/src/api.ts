import type { PatientProfile, Medication, SafetyCheckResult, ChatMessage, SafetyHistoryPoint, SafetyAlert } from './types';

const API_BASE = '/api';

export const mockPatient: PatientProfile = {
  id: 1,
  name: 'Eleanor Vance',
  age: 67,
  gender: 'Female',
  weight_kg: 68.5,
  creatinine_clearance: 42,
  egfr: 45, // Stage 3a CKD
  alt: 28,
  ast: 31,
  allergies: ['Penicillin', 'Sulfa Drugs'],
  chronic_conditions: ['Stage 3 CKD', 'Hypertension', 'Atrial Fibrillation', 'Type 2 Diabetes'],
  is_pregnant: false,
  is_lactating: false,
  blood_pressure: '138/84 mmHg'
};

export const mockMedications: Medication[] = [
  {
    id: 1,
    name: 'Warfarin',
    generic_name: 'Warfarin Sodium',
    dosage: '5mg',
    frequency: 'Once daily (Evening)',
    route: 'Oral',
    start_date: '2024-01-15',
    prescribing_doctor: 'Dr. Sarah Jenkins (Cardiology)',
    indication: 'Atrial Fibrillation / Stroke Prevention',
    status: 'active'
  },
  {
    id: 2,
    name: 'Lisinopril',
    generic_name: 'Lisinopril',
    dosage: '10mg',
    frequency: 'Once daily (Morning)',
    route: 'Oral',
    start_date: '2023-08-10',
    prescribing_doctor: 'Dr. Marcus Reynolds (Nephrology)',
    indication: 'Hypertension & Renal Protection',
    status: 'active'
  },
  {
    id: 3,
    name: 'Metformin',
    generic_name: 'Metformin Hydrochloride',
    dosage: '500mg',
    frequency: 'Twice daily with meals',
    route: 'Oral',
    start_date: '2022-11-04',
    prescribing_doctor: 'Dr. Emily Chen (Endocrinology)',
    indication: 'Type 2 Diabetes Mellitus',
    status: 'active'
  },
  {
    id: 4,
    name: 'Atorvastatin',
    generic_name: 'Atorvastatin Calcium',
    dosage: '20mg',
    frequency: 'Once daily at bedtime',
    route: 'Oral',
    start_date: '2023-04-12',
    prescribing_doctor: 'Dr. Sarah Jenkins (Cardiology)',
    indication: 'Hyperlipidemia',
    status: 'active'
  }
];

export const mockSafetyCheck: SafetyCheckResult = {
  overall_risk_score: 38,
  overall_risk_level: 'Moderate',
  summary: '2 moderate clinical alerts identified. Renal clearance monitoring advised given eGFR of 45 mL/min/1.73m².',
  digital_twin_status: {
    renal_load: 64,
    hepatic_load: 32,
    cardiac_risk: 41,
    cns_depression_risk: 15
  },
  alerts: [
    {
      id: 'alt-1',
      type: 'organ_impairment',
      severity: 'moderate',
      title: 'Metformin Dose Adjustment in Moderate Renal Impairment',
      description: 'Patient eGFR is 45 mL/min/1.73m² (Stage 3a CKD). Maximum recommended Metformin daily dose is 1000mg to mitigate lactic acidosis risk.',
      drugs_involved: ['Metformin'],
      mechanism: 'Decreased renal clearance of metformin increases systemic accumulation.',
      recommendation: 'Current dose (1000mg/day) is at upper safety limit. Monitor eGFR every 3-6 months. Discontinue if eGFR drops below 30 mL/min.',
      evidence_source: 'KDIGO 2023 Clinical Practice Guideline for Diabetes Management in CKD',
      evidence_score: 94
    },
    {
      id: 'alt-2',
      type: 'drug_drug',
      severity: 'low',
      title: 'Lisinopril + Metformin: Periodic Electrolyte & Renal Monitoring',
      description: 'Concomitant ACE inhibitor therapy in diabetic kidney disease requires baseline potassium and creatinine surveillance.',
      drugs_involved: ['Lisinopril', 'Metformin'],
      recommendation: 'Check serum potassium and creatinine within 2 weeks of any dose titration.',
      evidence_source: 'WHO Model Formulary 2023 / AHA Hypertension Guidelines',
      evidence_score: 88
    }
  ],
  recommendations: [
    'Schedule routine comprehensive metabolic panel (CMP) within 30 days.',
    'Maintain strict INR target of 2.0-3.0 for Warfarin anticoagulation therapy.',
    'Counsel patient to avoid over-the-counter NSAIDs (Ibuprofen, Naproxen) which drastically heighten bleeding and acute kidney injury risk.'
  ],
  timestamp: new Date().toISOString()
};

export const mockHistory: SafetyHistoryPoint[] = [
  { date: 'May 2024', score: 18, event: 'Monotherapy: Lisinopril initiated', risk_level: 'Low' },
  { date: 'Aug 2024', score: 25, event: 'Added Atorvastatin 20mg', risk_level: 'Low' },
  { date: 'Nov 2024', score: 32, event: 'Added Metformin 500mg BID', risk_level: 'Moderate' },
  { date: 'Jan 2025', score: 58, event: 'Warfarin initiated after AFib diagnosis', risk_level: 'Moderate' },
  { date: 'Mar 2025', score: 78, event: 'High Risk Alert: Patient prescribed OTC NSAID (resolved)', risk_level: 'High' },
  { date: 'Present', score: 38, event: 'Optimized regimen post-pharmacist review', risk_level: 'Moderate' }
];

export const mockAlertsStream: SafetyAlert[] = [
  {
    id: 'stream-1',
    type: 'drug_drug',
    severity: 'critical',
    title: 'Simulated Warning: Avoid Co-administration of Ibuprofen with Warfarin',
    description: 'NSAIDs displace warfarin from albumin and inhibit platelet aggregation, increasing gastrointestinal hemorrhage hazard by 4.2x.',
    drugs_involved: ['Ibuprofen', 'Warfarin'],
    recommendation: 'Use Acetaminophen (max 2g/day) or topical analgesic alternatives.',
    evidence_source: 'FDA Drug Safety Communication / Cochrane Review'
  },
  {
    id: 'stream-2',
    type: 'allergy',
    severity: 'high',
    title: 'Allergy Warning: Penicillin Cross-Reactivity Risk',
    description: 'Avoid Ampicillin, Amoxicillin, and 1st-generation Cephalosporins due to confirmed Type I hypersensitivity.',
    drugs_involved: ['Penicillin'],
    recommendation: 'Utilize Macrolides (Azithromycin) or Fluoroquinolones if antibiotic therapy is required.',
    evidence_source: 'AAAAI Drug Allergy Practice Parameter'
  }
];

// Safety check simulation when adding a new medication
export function evaluateNewMedication(newMedName: string, _currentMeds: Medication[], _patient: PatientProfile): SafetyCheckResult {
  const normalized = newMedName.toLowerCase().trim();
  const alerts: SafetyAlert[] = [...mockSafetyCheck.alerts];
  let riskScore = mockSafetyCheck.overall_risk_score;

  if (normalized.includes('ibuprofen') || normalized.includes('advil') || normalized.includes('naproxen') || normalized.includes('aspirin') || normalized.includes('nsaid')) {
    alerts.unshift({
      id: `sim-${Date.now()}`,
      type: 'drug_drug',
      severity: 'critical',
      title: `CRITICAL: Major Interaction between ${newMedName} and Warfarin`,
      description: 'Severe hemorrhage hazard. NSAIDs inhibit COX-1 platelet aggregation and cause gastric mucosal erosion when combined with systemic anticoagulation.',
      drugs_involved: [newMedName, 'Warfarin', 'Lisinopril'],
      mechanism: 'Synergistic bleeding risk and triple whammy renal insult (ACEi + NSAID + baseline CKD).',
      recommendation: 'CONTRAINDICATED. Switch to Acetaminophen or discuss non-pharmacological pain management.',
      evidence_source: 'Clinical Pharmacology / American College of Cardiology Guidelines',
      evidence_score: 99
    });
    riskScore = 86;
  } else if (normalized.includes('amoxicillin') || normalized.includes('penicillin') || normalized.includes('ampicillin') || normalized.includes('augmentin')) {
    alerts.unshift({
      id: `sim-${Date.now()}`,
      type: 'allergy',
      severity: 'critical',
      title: `ALLERGY CONTRAINDICATION: ${newMedName} violates Penicillin Allergy`,
      description: `Patient Eleanor Vance has documented severe Penicillin allergy. Administering ${newMedName} presents high risk of anaphylaxis.`,
      drugs_involved: [newMedName, 'Penicillin Allergy'],
      recommendation: 'DO NOT DISPENSE. Select a non-beta-lactam alternative such as Azithromycin or Clindamycin.',
      evidence_source: 'FDA Boxed Warning / Electronic Health Record Cross-Check',
      evidence_score: 99
    });
    riskScore = 92;
  } else if (normalized.includes('cipro') || normalized.includes('ciprofloxacin') || normalized.includes('bactrim')) {
    alerts.unshift({
      id: `sim-${Date.now()}`,
      type: 'drug_drug',
      severity: 'high',
      title: `HIGH RISK: CYP1A2 / CYP2C9 Interaction with Warfarin`,
      description: `${newMedName} potently inhibits Warfarin metabolism, causing acute INR spikes and severe spontaneous bleeding.`,
      drugs_involved: [newMedName, 'Warfarin'],
      recommendation: 'Reduce Warfarin dose by 30-50% with daily INR monitoring or substitute antibiotic.',
      evidence_source: 'Chest Antithrombotic Therapy Guidelines',
      evidence_score: 96
    });
    riskScore = 74;
  } else {
    alerts.unshift({
      id: `sim-${Date.now()}`,
      type: 'drug_drug',
      severity: 'low',
      title: `Compatibility Review for ${newMedName}`,
      description: `No major absolute contraindications detected with current active regimen. Renal dosing should be verified for eGFR 45.`,
      drugs_involved: [newMedName],
      recommendation: 'Standard dosing appropriate. Monitor for common side effects.',
      evidence_source: 'MedGuardian Knowledge Graph & RAG Core',
      evidence_score: 85
    });
    riskScore = Math.min(100, riskScore + 5);
  }

  const riskLevel = riskScore >= 75 ? 'Critical' : riskScore >= 50 ? 'High' : riskScore >= 25 ? 'Moderate' : 'Low';

  return {
    overall_risk_score: riskScore,
    overall_risk_level: riskLevel,
    summary: alerts[0].title,
    digital_twin_status: {
      renal_load: normalized.includes('ibuprofen') ? 89 : 68,
      hepatic_load: 35,
      cardiac_risk: normalized.includes('ibuprofen') ? 72 : 44,
      cns_depression_risk: 15
    },
    alerts,
    recommendations: [
      alerts[0].recommendation,
      ...mockSafetyCheck.recommendations
    ],
    timestamp: new Date().toISOString()
  };
}

export async function getPatientProfile(): Promise<PatientProfile> {
  try {
    const res = await fetch(`${API_BASE}/patients/profile/`);
    if (res.ok) return await res.json();
  } catch (_e) {
    // fallback
  }
  return mockPatient;
}

export async function getSafetyCheck(): Promise<SafetyCheckResult> {
  try {
    const res = await fetch(`${API_BASE}/patients/profile/safety-check/`);
    if (res.ok) return await res.json();
  } catch (_e) {
    // fallback
  }
  return mockSafetyCheck;
}

export async function askClinicalAssistant(question: string, contextDrugs: string[]): Promise<ChatMessage> {
  try {
    const res = await fetch(`${API_BASE}/patients/profile/chat-ask/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, context_drugs: contextDrugs })
    });
    if (res.ok) {
      const data = await res.json();
      return {
        id: `msg-${Date.now()}`,
        sender: 'assistant',
        content: data.answer || data.response || data.content,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        evidence_sources: data.sources || data.evidence
      };
    }
  } catch (_e) {
    // simulated RAG response
  }

  const q = question.toLowerCase();
  let content = `Based on MedGuardian AI evidence retrieval across WHO guidelines and clinical monographs:`;
  let sources = [
    { title: 'WHO Essential Medicines Guidelines (2023)', confidence: 0.94, quote: 'Patients with renal clearance below 50 mL/min require tailored dosing.' },
    { title: 'Goodman & Gilman\'s Pharmacological Basis of Therapeutics (14th Ed)', confidence: 0.91, quote: 'Warfarin metabolism is predominantly CYP2C9 and CYP3A4 mediated.' }
  ];

  if (q.includes('ibuprofen') || q.includes('advil') || q.includes('pain') || q.includes('nsaid')) {
    content = `⚠️ **Critical Warning: Avoid Ibuprofen / NSAIDs**

For Eleanor Vance, taking **Ibuprofen (Advil/Motrin)** is strictly **contraindicated** due to two compounding factors:

1. **Warfarin Bleeding Risk (4.2x hazard increase)**: Ibuprofen displaces Warfarin from protein binding sites and causes platelet inhibition and mucosal erosion, drastically increasing the risk of serious GI and intracranial hemorrhage.
2. **Triple Whammy Acute Kidney Injury (AKI)**: In combination with **Lisinopril (ACE inhibitor)** and pre-existing **Stage 3 CKD (eGFR 45)**, NSAIDs cause constriction of the afferent renal arterioles, which can induce sudden acute renal decompensation.

**Recommended Safe Alternative:**
• **Acetaminophen (Paracetamol)**: Up to 500mg-1000mg as needed (max 2g/24h) for mild-to-moderate pain.`;
    sources = [
      { title: 'ACC/AHA Anticoagulation Management Guidelines', confidence: 0.98, quote: 'NSAIDs should be avoided in patients receiving oral anticoagulation unless strictly unavoidable.' },
      { title: 'KDIGO 2023 Clinical Practice Guideline for CKD', confidence: 0.96, quote: 'Avoid NSAIDs in patients with eGFR < 60 mL/min/1.73m² receiving ACE inhibitors.' }
    ];
  } else if (q.includes('metformin') || q.includes('kidney') || q.includes('egfr') || q.includes('renal')) {
    content = `📊 **Metformin Renal Dosing Evaluation**

• **Current eGFR**: 45 mL/min/1.73m² (Stage 3a Moderate CKD)
• **Current Dose**: 500 mg twice daily (1,000 mg/day total)

**Clinical Evaluation:**
1. **Dose Adequacy**: According to FDA and ADA guidelines, Metformin is safe in patients with eGFR 45–59 mL/min up to a maximum dose of 1,000 mg daily. Eleanor's current regimen is at the optimal therapeutic ceiling.
2. **Monitoring Strategy**: Schedule renal function panel (eGFR & serum creatinine) every 3 to 6 months.
3. **Contrast Caution**: If scheduled for iodinated radiocontrast procedures, Metformin must be held at the time of procedure and for 48 hours post-procedure.`;
    sources = [
      { title: 'ADA Standards of Medical Care in Diabetes (2024)', confidence: 0.97, quote: 'Metformin can be safely continued if eGFR remains between 30 and 45 mL/min at maximum 1000mg daily.' }
    ];
  } else if (q.includes('alcohol') || q.includes('wine') || q.includes('drink')) {
    content = `🍷 **Alcohol Interaction Advisory**

• **Warfarin**: Acute alcohol intake reduces Warfarin metabolism, causing an elevation in INR and sudden bleeding hazard. Chronic heavy intake may paradoxically increase clearance.
• **Metformin**: Alcohol consumption increases risk of lactic acidosis and hypoglycemia.
• **Lisinopril**: Alcohol can accentuate hypotensive dizziness.

**Recommendation**: Limit alcohol strictly or avoid entirely while on active Warfarin anticoagulation.`;
  } else {
    content = `MedGuardian AI analyzed Eleanor Vance's active profile (Warfarin 5mg, Lisinopril 10mg, Metformin 500mg BID, Atorvastatin 20mg, Stage 3 CKD, Penicillin allergy).

Regarding your query: "${question}"

• **Safety Status**: Current multi-drug regimen is stable with a moderate risk score (38/100).
• **Precautions**: Avoid any OTC NSAIDs, monitor serum potassium and creatinine, and adhere to regular INR checks.
• Please consult the primary care physician or nephrologist before introducing any supplements or herbal compounds.`;
  }

  return {
    id: `msg-${Date.now()}`,
    sender: 'assistant',
    content,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    evidence_sources: sources
  };
}
