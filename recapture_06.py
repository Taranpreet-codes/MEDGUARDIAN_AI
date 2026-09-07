import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCREENSHOT_DIR = r"C:\Users\hp\.gemini\antigravity-ide\brain\8d169d67-1299-4394-b5ce-5295ca34e7d2\screenshots"

def recapture():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1440,950')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Edge(options=options)
    try:
        driver.get('http://localhost:5173')
        time.sleep(2)
        try:
            demo_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Fill Demo Credentials')]")))
            demo_btn.click()
            time.sleep(1)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()
        except:
            pass

        # Wait for sync to clear
        WebDriverWait(driver, 300).until(
            lambda d: len(d.find_elements(By.XPATH, "//*[contains(text(), 'Syncing with MedGuardian')]")) == 0
            and len(d.find_elements(By.XPATH, "//button[contains(., 'Medication Cabinet')]")) > 0
        )

        cabinet_tab = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Medication Cabinet')]")))
        cabinet_tab.click()
        time.sleep(3)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        screenshot_6 = os.path.join(SCREENSHOT_DIR, "06_conflicting_medication_removed.png")
        driver.save_screenshot(screenshot_6)
        print("Updated 06_conflicting_medication_removed.png successfully!")
    finally:
        driver.quit()

if __name__ == '__main__':
    recapture()
