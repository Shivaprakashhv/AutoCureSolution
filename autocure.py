import os
import shutil
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

# Using python-dotenv as best practice
from dotenv import load_dotenv
# Importing the NEW Google GenAI SDK
from google import genai
from google.genai import types

load_dotenv()
logger = logging.getLogger(__name__)

class AutoCureAgent:
    """
    Agentic AI that self-heals broken RPA locators.
    Compares a baseline HTML file against a live DOM string, updates the XML, 
    and handles file versioning/backups using the modern google-genai SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("API Key not found. Please set GOOGLE_API_KEY environment variable.")
        
        # New syntax for initializing the client
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        
        self.system_instruction = (
            "You are AutoCure, an expert RPA Engineer and DOM Analyst. "
            "Analyze the Baseline HTML and the Live Broken HTML, map the elements based on their "
            "logical intent, and output an updated XML file with highly resilient, RELATIVE XPaths. "
            "Output strictly valid XML and nothing else."
        )

    def _backup_old_xml(self, xml_path: Path) -> None:
        """Follows file management steps to backup the old XML file before overwriting."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{xml_path.stem}_old_{timestamp}{xml_path.suffix}"
        backup_path = xml_path.parent / backup_name
        
        shutil.copy(xml_path, backup_path)
        logger.info(f"AutoCure Version Control: Backed up old XML to {backup_path}")

    def heal_locators(self, baseline_html_path: str, live_html_source: str, xml_locator_path: str) -> bool:
        """Executes the healing workflow using a live DOM extraction."""
        logger.info("AutoCure triggered: Analyzing DOM structural changes...")
        xml_path = Path(xml_locator_path)

        try:
            with open(baseline_html_path, "r", encoding="utf-8") as file:
                baseline_html = file.read()
            with open(xml_path, "r", encoding="utf-8") as file:
                current_xml = file.read()
        except Exception as e:
            logger.error(f"AutoCure failed to read local context files: {e}")
            return False
        
        prompt = f"""
        Baseline HTML (Original):
        ```html
        {baseline_html}
        ```

        Live HTML (The updated portal that broke the bot):
        ```html
        {live_html_source}
        ```

        Current Broken RPA XML:
        ```xml
        {current_xml}
        ```

        Task:
        1. Find the corresponding elements in the Live HTML.
        2. Create resilient, relative XPaths for the Live HTML.
        3. Output the fully updated XML string inside <Locators> tags. Do not use markdown like ```xml.
        4. CRITICAL RULE: You MUST keep the 'name' attributes exactly as they are in the Original XML. Do not change them, or the Excel mapping will break!
        """

        try:
            # New syntax for generating content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.1
                )
            )
            
            generated_xml = response.text.strip()
            if generated_xml.startswith("```xml"):
                generated_xml = generated_xml[6:]
            if generated_xml.endswith("```"):
                generated_xml = generated_xml[:-3]
            generated_xml = generated_xml.strip()

            # Validate XML syntax
            ET.fromstring(generated_xml)
            
            # Version Control
            self._backup_old_xml(xml_path)
            
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(generated_xml)
                
            logger.info(f"AutoCure Successful: Re-generated {xml_path.name} with updated XPaths.")
            return True

        except ET.ParseError as e:
            logger.error(f"AutoCure generated invalid XML: {e}")
            return False
        except Exception as e:
            logger.error(f"AutoCure failed during AI generation: {e}")
            return False