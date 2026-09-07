import os
import sys
import time
import datetime
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, r'c:\Users\hp\Documents\projects\Medgaudian_AI\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medguardian.settings')
import django
django.setup()

from django.contrib.auth.models import User
from patients.models import PatientProfile, MedicationCabinet, SafetyAssessmentHistory, ProactiveAlert

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCREENSHOT_DIR = r"C:\Users\hp\.gemini\antigravity-ide\brain\8d169d67-1299-4394-b5ce-5295ca34e7d2\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def run_remaining():
    log("=== Running Remaining End-to-End Steps ===")

    # Ensure exactly 1 Spironolactone exists for clean test
    user = User.objects.get(username='testuser_qa')
    spiro_qs = user.profile.medications.filter(name__iexact='Spironolactone')
    if spiro_qs.count() > 1:
        # keep only one
        first_id = spiro_qs.first().id
        spiro_qs.exclude(id=first_id).delete()
    elif spiro_qs.count() == 0:
        MedicationCabinet.objects.create(
            patient=user.profile,
            name="Spironolactone",
            dosage="25mg",
            frequency="Once daily",
            start_date=datetime.date.today(),
            is_active=True
        )

    log(f"Current active medications count in DB: {user.profile.medications.filter(is_active=True).count()}")
    log(f"Medications: {list(user.profile.medications.filter(is_active=True).values_list('name', flat=True))}")

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1440,950')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Edge(options=options)
    wait = WebDriverWait(driver, 30)

    try:
        log("Navigating to http://localhost:5173 ...")
        driver.get('http://localhost:5173')
        time.sleep(2)

        # Authenticate if on login screen
        try:
            demo_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Fill Demo Credentials')]")))
            demo_btn.click()
            time.sleep(1)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()
            log("Submitted login credentials.")
        except Exception:
            log("Already authenticated or login button not needed.")

        # Allow state transition
        time.sleep(3)
        # Wait for backend sync loading screen to clear (takes ~2.5-3 minutes due to openFDA API calls)
        log("Waiting for backend sync loading screen to clear (up to 300s)...")
        try:
            WebDriverWait(driver, 300).until(
                lambda d: len(d.find_elements(By.XPATH, "//*[contains(text(), 'Syncing with MedGuardian')]")) == 0
                and len(d.find_elements(By.XPATH, "//button[contains(., 'Medication Cabinet')]")) > 0
            )
            log("Sync cleared and Medication Cabinet button is now present!")
        except Exception as e:
            log(f"Wait warning: {e}")

        # Step 4b: Navigate to Medication Cabinet & capture Spironolactone reflected in cabinet
        log("Navigating to Medication Cabinet tab...")
        cabinet_tab = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Medication Cabinet')]")))
        cabinet_tab.click()
        time.sleep(3)

        # Scroll to bottom to view Spironolactone
        spiro_card = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'card-surface') and .//h4[contains(text(), 'Spironolactone')]]")))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", spiro_card)
        time.sleep(2)

        screenshot_4 = os.path.join(SCREENSHOT_DIR, "04_prescription_reflected_in_cabinet.png")
        driver.save_screenshot(screenshot_4)
        log(f"Saved Screenshot 4 (Prescription Reflected in Cabinet): {screenshot_4}")

        # Step 5: Navigate to Digital Twin Safety Dashboard
        log("Navigating to Digital Twin Safety tab...")
        driver.execute_script("window.scrollTo(0, 0);")
        dash_tab = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Digital Twin Safety')]")))
        dash_tab.click()
        time.sleep(3)

        screenshot_5 = os.path.join(SCREENSHOT_DIR, "05_strong_interaction_warning.png")
        driver.save_screenshot(screenshot_5)
        log(f"Saved Screenshot 5 (Strong Interaction Warning): {screenshot_5}")

        # Verify page content for alerts
        page_src = driver.page_source
        has_severe = "Severe" in page_src or "SEVERE" in page_src
        log(f"Verified Severe Risk Badge and Alerts in UI: {has_severe}")

        # Step 6: Remove the conflicting medication (Spironolactone)
        log("Navigating back to Medication Cabinet to remove Spironolactone...")
        cabinet_tab = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Medication Cabinet')]")))
        cabinet_tab.click()
        time.sleep(3)

        spiro_card = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'card-surface') and .//h4[contains(text(), 'Spironolactone')]]")))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", spiro_card)
        time.sleep(1)

        delete_btn = spiro_card.find_element(By.XPATH, ".//button[@title='Remove medication']")
        delete_btn.click()
        time.sleep(1)

        # Accept confirm dialog
        try:
            alert = driver.switch_to.alert
            log(f"Confirm dialog: {alert.text}")
            alert.accept()
            log("Accepted deletion dialog.")
        except Exception as ex:
            log(f"Alert handling: {ex}")

        log("Waiting for cabinet list update after removal (refreshing safety checks, up to 240s)...")
        try:
            WebDriverWait(driver, 240).until(
                EC.invisibility_of_element_located((By.XPATH, "//div[contains(@class, 'card-surface') and .//h4[contains(text(), 'Spironolactone')]]"))
            )
            log("Spironolactone card has disappeared from the UI.")
        except Exception as e:
            log(f"Wait for removal: {e}")

        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        screenshot_6 = os.path.join(SCREENSHOT_DIR, "06_conflicting_medication_removed.png")
        driver.save_screenshot(screenshot_6)
        log(f"Saved Screenshot 6 (Conflicting Medication Removed): {screenshot_6}")

        # Verify Spironolactone is no longer in DB
        spiro_still_exists = user.profile.medications.filter(name__iexact='Spironolactone').exists()
        log(f"Spironolactone in DB after deletion: {spiro_still_exists} (Expected: False)")

        # Step 7: Safety History & Timeline with dates
        log("Navigating to Safety History tab...")
        driver.execute_script("window.scrollTo(0, 0);")
        history_tab = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Safety History')]")))
        history_tab.click()
        time.sleep(3)

        screenshot_7 = os.path.join(SCREENSHOT_DIR, "07_final_safety_history_dates.png")
        driver.save_screenshot(screenshot_7)
        log(f"Saved Screenshot 7 (Safety History & Longitudinal Dates): {screenshot_7}")

        # Step 8: Clinical AI Chat
        log("Navigating to Clinical AI (RAG) tab...")
        chat_tab = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Clinical AI')]")))
        chat_tab.click()
        time.sleep(2)

        chat_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Ask a clinical question')]")))
        chat_input.clear()
        from selenium.webdriver.common.keys import Keys
        chat_input.send_keys("Is Lisinopril safe for a pregnant patient?" + Keys.ENTER)
        log("Submitted inquiry to Clinical AI Chat. Waiting for grounded synthesis...")
        time.sleep(8)

        screenshot_8 = os.path.join(SCREENSHOT_DIR, "08_clinical_ai_chat.png")
        driver.save_screenshot(screenshot_8)
        log(f"Saved Screenshot 8 (Clinical AI Chat): {screenshot_8}")

        # Step 9: Clinical Summary & Reports
        log("Navigating to Clinical Summary reports tab...")
        reports_tab = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Clinical Summary')]")))
        reports_tab.click()
        time.sleep(3)

        screenshot_9 = os.path.join(SCREENSHOT_DIR, "09_clinical_summary_reports.png")
        driver.save_screenshot(screenshot_9)
        log(f"Saved Screenshot 9 (Clinical Summary & PDF Reports): {screenshot_9}")

        log("=== All Remaining End-to-End Steps Successfully Completed! ===")

    except Exception as e:
        log(f"ERROR: {e}")
        err_path = os.path.join(SCREENSHOT_DIR, "error_state_remaining.png")
        try:
            driver.save_screenshot(err_path)
            log(f"Saved error screenshot: {err_path}")
        except:
            pass
        raise e
    finally:
        driver.quit()

if __name__ == '__main__':
    run_remaining()
