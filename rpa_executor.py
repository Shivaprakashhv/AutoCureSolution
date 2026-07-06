import os
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

# Import our custom AutoCure Agent
from autocure import AutoCureAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class RPAAutomationEngine:
    def __init__(self, xml_locator_path: str, excel_data_path: str, baseline_html_path: str):
        self.xml_path = Path(xml_locator_path)
        self.excel_path = Path(excel_data_path)
        self.baseline_html_path = baseline_html_path
        self.locators: Dict[str, str] = {}
        
        # Initialize the AI Agent
        self.autocure = AutoCureAgent()
        
        self._load_xml_locators()

    def _load_xml_locators(self) -> None:
        """Parses the XML locator repository file into memory. (Called initially and post-healing)"""
        self.locators.clear()
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            for element in root.findall("Element"):
                name = element.get("name")
                xpath = element.get("xpath")
                if name and xpath:
                    self.locators[name] = xpath
            logger.info(f"Loaded {len(self.locators)} locators from {self.xml_path.name}.")
        except Exception as e:
            logger.error(f"Failed to load locators: {e}")
            raise e

    def get_excel_records(self) -> list[Dict[str, Any]]:
        df = pd.read_excel(self.excel_path)
        df = df.fillna("")
        return df.to_dict(orient="records")
    
    def process_record(self, driver: webdriver.Chrome, wait: WebDriverWait, record: Dict[str, Any], target_url: str) -> None:
        """Processes a single record. Raises TimeoutException if an element is missing."""
        driver.get(target_url)

        # 1. Fill out the form
        for field_name, xpath in self.locators.items():
            # Skip the buttons/messages during the typing phase
            if field_name in ["SubmitButton", "SuccessMessage"]:
                continue 
            
            if field_name in record:
                value_to_input = str(record[field_name])
                element = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
                element.clear()
                element.send_keys(value_to_input)

        # 2. Submit and Verify using XML paths (No hardcoding)
        submit_xpath = self.locators.get("SubmitButton")
        success_xpath = self.locators.get("SuccessMessage")

        if submit_xpath and success_xpath:
            # Click the button
            submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, submit_xpath)))
            submit_btn.click()
            
            # Wait for the success banner
            wait.until(EC.visibility_of_element_located((By.XPATH, success_xpath)))
        else:
            logger.error("SubmitButton or SuccessMessage configuration missing in XML.")

    def execute_onboarding(self, target_url: str) -> None:
        records = self.get_excel_records()
        if not records:
            return

        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, timeout=5) # Lowered timeout for faster failure detection

        try:
            for index, record in enumerate(records, start=1):
                logger.info(f"Processing record {index}/{len(records)}: {record.get('CandidateID')}")
                
                max_retries = 1
                retry_count = 0
                success = False

                while retry_count <= max_retries and not success:
                    try:
                        self.process_record(driver, wait, record, target_url)
                        logger.info(f"Record {index} processed successfully.")
                        success = True
                        
                    except TimeoutException as e:
                        logger.warning(f"Execution failed on record {index} due to DOM change. Triggering AutoCure...")
                        
                        if retry_count < max_retries:
                            # 1. Grab the live broken HTML directly from the browser
                            live_source = driver.page_source
                            
                            # 2. Call AutoCure with the baseline file, the live source, and the current XML
                            healed = self.autocure.heal_locators(
                                baseline_html_path=self.baseline_html_path,
                                live_html_source=live_source,
                                xml_locator_path=str(self.xml_path)
                            )
                            
                            if healed:
                                # 3. Reload the newly fixed XML into memory
                                self._load_xml_locators()
                                logger.info("AutoCure complete. Retrying record...")
                                retry_count += 1
                            else:
                                logger.error("AutoCure failed to heal the locators. Aborting record.")
                                break # Move to the next record or halt
                        else:
                            logger.error(f"Max retries reached for record {index}. AutoCure could not resolve the issue.")
                            break

        except WebDriverException as web_err:
            logger.critical(f"Critical WebDriver error: {web_err}")
        finally:
            driver.quit()


if __name__ == "__main__":
    # Must include http:// for Selenium to understand it
    TARGET_PORTAL_URL = "http://127.0.0.1:5000/" 
    
    executor = RPAAutomationEngine(
        xml_locator_path="locators_v1.xml",
        excel_data_path="input_data.xlsx",
        baseline_html_path="index_v1.html" 
    )
    
    executor.execute_onboarding(target_url=TARGET_PORTAL_URL)