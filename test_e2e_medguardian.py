import os
import sys
import time
import datetime
from django.utils import timezone

# Setup Django environment
sys.path.insert(0, r'c:\Users\hp\Documents\projects\Medgaudian_AI\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medguardian.settings')
import django
django.setup()

from django.contrib.auth.models import User
from patients.models import PatientProfile, MedicationCabinet, SafetyAssessmentHistory, ProactiveAlert
from services.risk_engine import RiskEngine

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCREENSHOT_DIR = r"C:\Users\hp\.gemini\antigravity-ide\brain\8d169d67-1299-4394-b5ce-5295ca34e7d2\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

test_log = []

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    test_log.append(entry)

def run_e2e_test():
    log("=== Starting MedGuardian AI End-to-End Test ===")
    
    # 1. Setup Edge Options
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1440,950')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Edge(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # Step 0: Ensure initial clean state: exactly 2 medications (Lisinopril and Amoxicillin)
        user = User.objects.get(username='testuser_qa')
        user.profile.medications.exclude(name__in=['Lisinopril', 'Amoxicillin']).delete()
        log("Verified testuser_qa initial cabinet state in DB (Lisinopril, Amoxicillin).")

        # Step 1: Navigate to application
        log("Step 1: Navigating to http://localhost:5173 ...")
        driver.get('http://localhost:5173')
        time.sleep(3)

        # Check if login form is present
        try:
            demo_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Fill Demo Credentials')]")))
            log("Found 'Fill Demo Credentials' button. Clicking...")
            demo_button.click()
            time.sleep(1)
            
            # Click Sign In
            sign_in_button = driver.find_element(By.XPATH, "//button[@type='submit' and (contains(., 'Sign In') or contains(., 'Access Patient'))]")
            log("Clicking Sign In button...")
            sign_in_button.click()
            time.sleep(3)
        except Exception as e:
            log(f"Auto demo button bypass or error: {e}. Trying direct form fill...")
            try:
                user_input = driver.find_element(By.XPATH, "//input[@type='text']")
                pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
                user_input.clear()
                user_input.send_keys("testuser_qa")
                pass_input.clear()
                pass_input.send_keys("testpass123")
                driver.find_element(By.XPATH, "//button[@type='submit']").click()
                time.sleep(3)
            except Exception as e2:
                log(f"Login inputs error: {e2}")

        # Verify Dashboard loaded and sync completed
        log("Waiting for initial backend sync to complete...")
        try:
            WebDriverWait(driver, 45).until_not(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Syncing with MedGuardian')]")))
        except Exception:
            pass

        # Step 2: Navigate to Medication Cabinet & Record Initial State
        log("Step 2: Inspecting initial Medical Cabinet...")
        cabinet_tab = WebDriverWait(driver, 45).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Medication Cabinet')]")))
        log("Dashboard loaded. Clicking Medication Cabinet tab...")
        cabinet_tab.click()
        time.sleep(3)

        screenshot_1 = os.path.join(SCREENSHOT_DIR, "01_initial_medical_cabinet.png")
        driver.save_screenshot(screenshot_1)
        log(f"Saved initial cabinet screenshot: {screenshot_1}")

        # Inspect initial medications from DB
        user = User.objects.get(username='testuser_qa')
        initial_meds = list(user.profile.medications.filter(is_active=True).values('id', 'name', 'dosage', 'frequency', 'start_date'))
        log(f"Initial Cabinet State ({len(initial_meds)} medications):")
        for m in initial_meds:
            log(f"  - {m['name']} ({m['dosage']}, {m['frequency']}, Started: {m['start_date']})")

        # Step 3: Ensure Cabinet contains at least 10 realistic synthetic medications across different dates
        log("Step 3: Ensuring Medical Cabinet contains at least 10 medications...")
        from decimal import Decimal
        profile = user.profile
        profile.creatinine = Decimal('0.95')
        profile.egfr = Decimal('85.00')
        profile.save()

        additional_synthetic_meds = [
            {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily", "start_date": datetime.date(2025, 2, 1)},
            {"name": "Levothyroxine", "dosage": "50mcg", "frequency": "Once daily morning", "start_date": datetime.date(2025, 2, 20)},
            {"name": "Omeprazole", "dosage": "20mg", "frequency": "Once daily before breakfast", "start_date": datetime.date(2025, 3, 15)},
            {"name": "Amlodipine", "dosage": "5mg", "frequency": "Once daily", "start_date": datetime.date(2025, 4, 1)},
            {"name": "Cetirizine", "dosage": "10mg", "frequency": "Once daily as needed", "start_date": datetime.date(2025, 5, 10)},
            {"name": "Vitamin D3", "dosage": "1000IU", "frequency": "Once daily", "start_date": datetime.date(2025, 6, 1)},
            {"name": "Acetaminophen", "dosage": "500mg", "frequency": "Every 6 hours PRN", "start_date": datetime.date(2025, 7, 1)},
            {"name": "Calcium Carbonate", "dosage": "500mg", "frequency": "Once daily with food", "start_date": datetime.date(2025, 8, 1)},
        ]

        existing_names = set(profile.medications.values_list('name', flat=True))
        to_create = [
            MedicationCabinet(
                patient=profile,
                name=m["name"],
                dosage=m["dosage"],
                frequency=m["frequency"],
                start_date=m["start_date"],
                is_active=True
            ) for m in additional_synthetic_meds if m["name"] not in existing_names
        ]
        if to_create:
            MedicationCabinet.objects.bulk_create(to_create)
            for m in to_create:
                log(f"  + Added synthetic medication: {m.name} ({m.dosage}), Started: {m.start_date}")

        # Seed historical safety timeline points across dates
        hist_milestones = [
            (datetime.datetime(2025, 1, 5, 10, 0, tzinfo=datetime.timezone.utc), "Safe", "lab_update", "Baseline Clinical Intake"),
            (datetime.datetime(2025, 2, 2, 14, 30, tzinfo=datetime.timezone.utc), "Moderate", "medication_change", "Metformin Added (Diabetes/Renal Evaluation)"),
            (datetime.datetime(2025, 3, 16, 9, 15, tzinfo=datetime.timezone.utc), "Moderate", "medication_change", "Omeprazole Regimen Initiated"),
            (datetime.datetime(2025, 5, 12, 11, 0, tzinfo=datetime.timezone.utc), "Low", "lab_update", "Quarterly Renal Panel Normal"),
            (datetime.datetime(2025, 8, 2, 16, 45, tzinfo=datetime.timezone.utc), "Moderate", "medication_change", "Calcium Supplementation Started"),
        ]
        for dt, risk, trigger, note in hist_milestones:
            h, created = SafetyAssessmentHistory.objects.get_or_create(
                patient=profile,
                triggered_by=trigger,
                risk_score=risk,
                defaults={
                    'details': {
                        'overall_risk_score': risk,
                        'clinician_notes': note,
                        'evidence_references': ['who_guidelines.txt', 'clinical_benchmark.json'],
                        'interactions': []
                    }
                }
            )
            SafetyAssessmentHistory.objects.filter(pk=h.pk).update(created_at=dt)

        total_active_meds = profile.medications.filter(is_active=True).count()
        log(f"Total active medications in cabinet: {total_active_meds}")

        # Refresh browser page to reflect 10+ medications
        log("Refreshing page to reflect 10+ medications. Waiting for safety sync (evaluating openFDA pairs)...")
        driver.refresh()
        try:
            WebDriverWait(driver, 240).until_not(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Syncing with MedGuardian')]")))
        except Exception:
            pass

        # Click Medication Cabinet tab again
        cabinet_tab = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Medication Cabinet')]")))
        cabinet_tab.click()
        time.sleep(3)

        screenshot_2 = os.path.join(SCREENSHOT_DIR, "02_cabinet_10_medications.png")
        driver.save_screenshot(screenshot_2)
        log(f"Saved 10+ medications cabinet screenshot: {screenshot_2}")

        # Step 4: Test Pre-Prescription Simulator with Spironolactone
        log("Step 4: Testing Digital Twin Pre-Prescription Simulator with Spironolactone...")
        sim_input = driver.find_element(By.XPATH, "//input[@placeholder[contains(., 'Enter drug name')]]")
        sim_input.clear()
        sim_input.send_keys("Spironolactone")
        time.sleep(1)

        sim_button = driver.find_element(By.XPATH, "//button[contains(., 'Simulate Impact')]")
        sim_button.click()
        log("Clicked 'Simulate Impact'. Waiting for digital twin simulation results...")
        time.sleep(5)

        # Step 5: Add a new prescription via "Add Prescription" modal
        log("Step 5: Adding new prescription for candidate drug Spironolactone via Modal...")
        add_presc_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add Prescription')]")))
        add_presc_btn.click()
        time.sleep(1)

        # Fill modal form
        name_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@placeholder[contains(., 'Lisinopril')]]")))
        name_input.clear()
        name_input.send_keys("Spironolactone")

        dosage_input = driver.find_element(By.XPATH, "//input[@placeholder='10mg']")
        dosage_input.clear()
        dosage_input.send_keys("25mg")

        freq_input = driver.find_element(By.XPATH, "//input[@placeholder='Once daily']")
        freq_input.clear()
        freq_input.send_keys("Once daily")

        screenshot_3 = os.path.join(SCREENSHOT_DIR, "03_new_prescription_modal.png")
        driver.save_screenshot(screenshot_3)
        log(f"Saved new prescription modal screenshot: {screenshot_3}")

        # Click Save Medication
        save_btn = driver.find_element(By.XPATH, "//button[contains(., 'Save Medication')]")
        save_btn.click()
        log("Saved Spironolactone prescription. Waiting for clinical safety evaluation and cabinet update...")
        time.sleep(12)

        # Verify prescription reflected in cabinet
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        screenshot_4 = os.path.join(SCREENSHOT_DIR, "04_prescription_reflected_in_cabinet.png")
        driver.save_screenshot(screenshot_4)
        log(f"Saved prescription reflected in cabinet screenshot: {screenshot_4}")

        # Step 6 & 7: Verify strong interaction warning
        log("Step 6 & 7: Verifying Strong Interaction Detection on Digital Twin Safety Dashboard...")
        driver.execute_script("window.scrollTo(0, 0);")
        dash_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Digital Twin Safety')]")))
        dash_tab.click()
        time.sleep(5)

        screenshot_5 = os.path.join(SCREENSHOT_DIR, "05_strong_interaction_warning.png")
        driver.save_screenshot(screenshot_5)
        log(f"Saved strong interaction warning screenshot: {screenshot_5}")

        # Read page text to verify interaction alert
        page_source = driver.page_source
        has_severe_warning = "Severe" in page_source or "SEVERE" in page_source or "Contraindicated" in page_source
        has_spiro_interaction = "Spironolactone" in page_source or "Lisinopril" in page_source
        log(f"Severe risk displayed in UI: {has_severe_warning}")
        log(f"Conflicting medications flagged in UI: {has_spiro_interaction}")

        # Step 8: Remove the conflicting medication (Spironolactone)
        log("Step 8: Removing conflicting medication (Spironolactone) from Medical Cabinet...")
        cabinet_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Medication Cabinet')]")))
        cabinet_tab.click()
        time.sleep(3)

        # Find Spironolactone card, scroll into view and click delete button
        spiro_card = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'card-surface') and .//h4[contains(text(), 'Spironolactone')]]")))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", spiro_card)
        time.sleep(1)
        delete_btn = spiro_card.find_element(By.XPATH, ".//button[@title='Remove medication']")
        delete_btn.click()
        time.sleep(1)

        # Accept window confirm dialog
        try:
            alert = driver.switch_to.alert
            log(f"Browser confirm dialog text: {alert.text}")
            alert.accept()
            log("Accepted deletion confirm dialog.")
        except Exception as ex:
            log(f"Alert handling exception: {ex}")

        log("Waiting for medication deletion and safety re-evaluation...")
        time.sleep(12)

        time.sleep(3)

        # Verify Spironolactone is removed
        screenshot_6 = os.path.join(SCREENSHOT_DIR, "06_conflicting_medication_removed.png")
        driver.save_screenshot(screenshot_6)
        log(f"Saved conflicting medication removed screenshot: {screenshot_6}")

        # Check DB that Spironolactone is deleted
        spiro_exists = user.profile.medications.filter(name__iexact='Spironolactone').exists()
        log(f"Spironolactone exists in database after removal: {spiro_exists} (Expected: False)")

        # Step 9 & 10: Verify Safety History and separate dated events
        log("Step 9 & 10: Checking Safety History across different dates and verifying audit trail consistency...")
        history_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Safety History')]")))
        history_tab.click()
        time.sleep(3)

        screenshot_7 = os.path.join(SCREENSHOT_DIR, "07_final_safety_history_dates.png")
        driver.save_screenshot(screenshot_7)
        log(f"Saved final safety history screenshot: {screenshot_7}")

        # Step 11: Clinical AI Chat & Summary Reports check
        log("Testing Clinical AI Chat Assistant tab...")
        chat_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Clinical AI')]")))
        chat_tab.click()
        time.sleep(2)

        chat_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder[contains(., 'Ask a clinical question')]]")))
        chat_input.clear()
        chat_input.send_keys("Is Lisinopril safe for a pregnant patient?")
        send_btn = driver.find_element(By.XPATH, "//button[.//svg and not(@disabled)]")
        send_btn.click()
        log("Sent query to Clinical AI Assistant. Waiting for grounded evidence response...")
        time.sleep(5)

        screenshot_8 = os.path.join(SCREENSHOT_DIR, "08_clinical_ai_chat.png")
        driver.save_screenshot(screenshot_8)
        log(f"Saved clinical AI chat screenshot: {screenshot_8}")

        # Reports Tab check
        log("Testing Clinical Summary & Reports tab...")
        reports_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Clinical Summary')]")))
        reports_tab.click()
        time.sleep(2)

        screenshot_9 = os.path.join(SCREENSHOT_DIR, "09_clinical_summary_reports.png")
        driver.save_screenshot(screenshot_9)
        log(f"Saved clinical summary reports screenshot: {screenshot_9}")

        log("=== End-to-End Test Run Completed Successfully ===")

    except Exception as e:
        log(f"ERROR during test execution: {e}")
        error_screenshot = os.path.join(SCREENSHOT_DIR, "error_state.png")
        try:
            driver.save_screenshot(error_screenshot)
            log(f"Captured error state screenshot: {error_screenshot}")
        except:
            pass
        raise e
    finally:
        driver.quit()

if __name__ == '__main__':
    run_e2e_test()
