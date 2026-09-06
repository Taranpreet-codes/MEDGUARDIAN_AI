import os
import json
import logging
import requests
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from patients.models import PatientProfile, MedicationCabinet, InteractionLog
from services.rag import RAGEngine

logger = logging.getLogger(__name__)

# Pydantic schemas for Gemini Risk Evaluator
class WarningDetail(BaseModel):
    severity: str = Field(description="Warning severity: Severe, Moderate, or Low")
    description: str = Field(description="Explanation of the safety warning, interaction, or dosage conflict")
    drug_involved: str = Field(description="Specific drug(s) causing the alert")

class SafetyEvaluation(BaseModel):
    overall_risk_score: str = Field(description="Highest risk tier detected: Severe, Moderate, Low, or Safe")
    interactions: list[WarningDetail] = Field(description="Detailed clinical warnings generated")
    evidence_references: list[str] = Field(description="Clinical document names or guidelines referenced from the context")
    clinician_notes: str = Field(description="Professional summary of considerations for the treating physician")


# Predefined local fallback rules for testing and offline execution
FALLBACK_INTERACTIONS = [
    {
        "drugs": {"lisinopril", "spironolactone"},
        "severity": "Severe",
        "description": "Concomitant use may result in severe hyperkalemia. Monitor serum potassium closely.",
    },
    {
        "drugs": {"lisinopril", "ibuprofen"},
        "severity": "Moderate",
        "description": "NSAIDs may decrease the antihypertensive effect of Lisinopril and increase the risk of renal function deterioration.",
    },
    {
        "drugs": {"metformin", "contrast"},
        "severity": "Moderate",
        "description": "Iodinated contrast media may cause acute renal failure; Metformin must be paused to prevent lactic acidosis.",
    }
]

class RiskEngine:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        if self.api_key and "your_gemini_api_key" not in self.api_key.lower():
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("GEMINI_API_KEY not set or is placeholder. Using rule-based fallback and clinical evaluator.")
        self.rag_engine = RAGEngine()

    def resolve_rxcui(self, drug_name: str) -> str | None:
        """Resolves generic drug name to RxNorm RxCUI using NLM RxNav API."""
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}"
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                data = res.json()
                id_group = data.get("idGroup", {})
                rxnorm_ids = id_group.get("rxnormId", [])
                if rxnorm_ids:
                    return rxnorm_ids[0]
        except Exception as e:
            logger.error(f"RxNav RxCUI lookup failed for {drug_name}: {e}")
        return None

    def check_rxnav_interactions(self, meds: list[str]) -> list[dict]:
        """Queries NLM RxNav API for drug-drug interaction alerts among a list of medications."""
        # 1. Resolve RxCUIs
        rxcuis = []
        cui_to_name = {}
        for med in meds:
            cui = self.resolve_rxcui(med)
            if cui:
                rxcuis.append(cui)
                cui_to_name[cui] = med

        if len(rxcuis) < 2:
            if len(meds) >= 2:
                return self._check_local_interactions(meds)
            return []

        # 2. Query list interactions
        cui_str = "+".join(rxcuis)
        url = f"https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis={cui_str}"
        interactions = []

        try:
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                # Parse NLM JSON hierarchy
                full_interaction_groups = data.get("fullInteractionTypeGroup", [])
                for group in full_interaction_groups:
                    for interaction_type in group.get("fullInteractionType", []):
                        for pair in interaction_type.get("interactionPair", []):
                            description = pair.get("description", "")
                            severity = pair.get("severity", "Moderate") # RxNav defaults to high/moderate
                            
                            # Determine drugs involved
                            concepts = pair.get("interactionConcept", [])
                            involved_names = []
                            for c in concepts:
                                source_concept = c.get("minConceptItem", {})
                                rxcui = source_concept.get("rxcui", "")
                                name = cui_to_name.get(rxcui, source_concept.get("name", "Unknown"))
                                involved_names.append(name)
                            
                            interactions.append({
                                "severity": "Severe" if severity.lower() == "high" else "Moderate",
                                "description": description,
                                "drug_involved": ", ".join(involved_names)
                            })
            if not interactions:
                return self._check_local_interactions(meds)
            return interactions
        except Exception as e:
            logger.error(f"RxNav interaction check failed: {e}")
        
        # 3. Fallback to local rule-based matching if API fails or offline
        return self._check_local_interactions(meds)

    def _check_local_interactions(self, meds: list[str]) -> list[dict]:
        """Local rule-based lookup for drug-drug interactions."""
        alerts = []
        normalized_meds = {m.lower().strip() for m in meds}
        for rule in FALLBACK_INTERACTIONS:
            # Check if all drugs in rule are active in cabinet
            if rule["drugs"].issubset(normalized_meds):
                alerts.append({
                    "severity": rule["severity"],
                    "description": rule["description"],
                    "drug_involved": " + ".join([d.capitalize() for d in rule["drugs"]])
                })
        return alerts

    def evaluate_patient_safety(self, profile: PatientProfile) -> dict:
        """
        Gathers profile, active medications, checks interactions (RxNav/local),
        queries ChromaDB clinical guidelines, and prompts Gemini to compile structured analysis.
        """
        # Fetch cabinet meds
        active_med_objects = MedicationCabinet.objects.filter(patient=profile, is_active=True)
        med_names = [m.name for m in active_med_objects]

        if not med_names:
            return {
                "overall_risk_score": "Safe",
                "interactions": [],
                "evidence_references": ["Patient profile contains 0 active medications."],
                "clinician_notes": "No medications currently active. Maintain healthy lifestyle."
            }

        # 1. API check interactions
        interaction_alerts = self.check_rxnav_interactions(med_names)

        # 2. Query RAG vector guidelines
        rag_snippets = []
        # Build query strings representing profile risks
        queries = []
        for med in med_names:
            if profile.pregnancy_status:
                queries.append(f"pregnancy and {med} warnings and contraindications")
            if profile.egfr and float(profile.egfr) < 60:
                queries.append(f"kidney renal dysfunction dosing adjustment for {med}")
            for disease in profile.chronic_diseases:
                queries.append(f"clinical guideline {disease} warnings for {med}")
            for allergy in profile.allergies:
                queries.append(f"{allergy} drug allergy reaction with {med}")

        for q in queries[:6]: # Limit to avoid context overload in dev
            snippets = self.rag_engine.retrieve_evidence(q, limit=2)
            rag_snippets.extend(snippets)

        # Formulate prompt context
        profile_summary = (
            f"Patient demographics: Age {profile.age}, Gender {profile.gender}. "
            f"Pregnancy status: {profile.pregnancy_status}. "
            f"Kidney Labs: Creatinine {profile.creatinine} mg/dL, eGFR {profile.egfr} mL/min/1.73m². "
            f"Chronic Conditions: {', '.join(profile.chronic_diseases) if profile.chronic_diseases else 'None'}. "
            f"Allergies: {', '.join(profile.allergies) if profile.allergies else 'None'}."
        )

        formatted_snippets = ""
        for s in rag_snippets:
            formatted_snippets += f"- [{s['source']}] {s['text']}\n"

        # 3. Prompt Gemini or use Mock Fallback
        if not self.client:
            return self._run_mock_safety_evaluation(profile, med_names, interaction_alerts, rag_snippets)

        try:
            prompt = (
                f"You are a clinical decision support risk engine.\n\n"
                f"PATIENT CLINICAL PROFILE:\n{profile_summary}\n\n"
                f"ACTIVE MEDICATIONS:\n{', '.join(med_names)}\n\n"
                f"RETRIEVED DRUG INTERACTIONS (RxNav/rules):\n{json.dumps(interaction_alerts)}\n\n"
                f"RETRIEVED CLINICAL GUIDELINES (RAG):\n{formatted_snippets if formatted_snippets else 'No relevant guidelines retrieved.'}\n\n"
                f"Evaluate safety. Check for:\n"
                f"1. Drug-drug interactions.\n"
                f"2. Drug-condition contraindications (e.g. Lisinopril in pregnancy).\n"
                f"3. Renal dosing conflicts (check eGFR < 60).\n"
                f"4. Allergy matches.\n\n"
                f"Generate a structured safety evaluation report."
            )

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SafetyEvaluation,
                ),
            )

            data = json.loads(response.text)
            
            # Validate response matches expected schema key structure
            if not isinstance(data.get("interactions"), list) or "overall_risk_score" not in data:
                raise ValueError("Gemini response schema mismatch: missing required safety evaluation fields.")
            
            # Save log
            InteractionLog.objects.create(
                patient=profile,
                risk_score=data.get("overall_risk_score", "Safe"),
                details=data
            )
            return data

        except Exception as e:
            logger.error(f"Gemini clinical risk assessment failed: {e}. Using mock evaluator.")
            return self._run_mock_safety_evaluation(profile, med_names, interaction_alerts, rag_snippets, error_context=str(e))

    def _run_mock_safety_evaluation(self, profile, med_names, interactions, rag_snippets, error_context=None) -> dict:
        """Fallback rule-based clinical safety evaluator."""
        warnings = []
        overall_risk = "Safe"

        # 1. Map drug-drug warnings
        for inter in interactions:
            warnings.append({
                "severity": inter["severity"],
                "description": inter["description"],
                "drug_involved": inter["drug_involved"]
            })
            if inter["severity"] == "Severe":
                overall_risk = "Severe"
            elif inter["severity"] == "Moderate" and overall_risk != "Severe":
                overall_risk = "Moderate"

        # 2. Check pregnancy contraindications
        normalized_meds = {m.lower().strip() for m in med_names}
        if profile.pregnancy_status:
            # Lisinopril is strictly contraindicated in pregnancy
            if "lisinopril" in normalized_meds:
                warnings.append({
                    "severity": "Severe",
                    "description": "Lisinopril is contraindicated in pregnancy due to risks of fetal toxicity and birth defects.",
                    "drug_involved": "Lisinopril"
                })
                overall_risk = "Severe"

        # 3. Check renal contraindications
        if profile.egfr and float(profile.egfr) < 45:
            # Ibuprofen has caution in severe kidney disease
            if "ibuprofen" in normalized_meds:
                warnings.append({
                    "severity": "Moderate",
                    "description": f"Patient has renal impairment (eGFR {profile.egfr}). NSAIDs like Ibuprofen should be avoided or minimized.",
                    "drug_involved": "Ibuprofen"
                })
                if overall_risk != "Severe":
                    overall_risk = "Moderate"

        # 4. Check allergy matches
        normalized_allergies = {a.lower().strip() for a in profile.allergies}
        for allergy in normalized_allergies:
            for med in normalized_meds:
                if allergy in med or (allergy == "penicillin" and "amox" in med.lower()): # e.g. "penicillin" allergy and "amoxicillin" drug
                    warnings.append({
                        "severity": "Severe",
                        "description": f"Potential allergic reaction: Patient is allergic to {allergy.capitalize()} and active cabinet contains {med.capitalize()}.",
                        "drug_involved": med.capitalize()
                    })
                    overall_risk = "Severe"

        details = {
            "overall_risk_score": overall_risk,
            "interactions": warnings,
            "evidence_references": [s["source"] for s in rag_snippets] if rag_snippets else ["openFDA database warnings", "RxNav interaction lists"],
            "clinician_notes": (
                "Rule-based safety evaluator triggered. "
                "Verify drug combinations manually. Monitor electrolyte and renal values."
            )
        }

        # Cache log
        InteractionLog.objects.create(
            patient=profile,
            risk_score=overall_risk,
            details=details
        )
        return details
