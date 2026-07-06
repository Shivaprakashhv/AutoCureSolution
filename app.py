import os
import logging
import pandas as pd
from flask import Flask, request, jsonify, send_file
from pathlib import Path

# ---------------------------------------------------------
# Configuration & Logging Setup
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Define the absolute or relative path for the Excel file
EXCEL_FILE_PATH = Path("Infosys_Onboarding_Records.xlsx")

def save_to_excel(data: dict) -> None:
    """
    Saves the provided dictionary data to an Excel file.
    Creates a new file and headers if it does not exist.
    """
    try:
        # Convert the dictionary to a pandas DataFrame (1 row)
        df_new = pd.DataFrame([data])

        if EXCEL_FILE_PATH.exists():
            # If file exists, append without overwriting existing data
            with pd.ExcelWriter(EXCEL_FILE_PATH, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                # Find the last row to append properly
                startrow = writer.sheets['Sheet1'].max_row
                df_new.to_excel(writer, index=False, header=False, startrow=startrow)
            logger.info(f"Appended new candidate {data.get('CandidateID')} to existing Excel file.")
        else:
            # If file doesn't exist, create it with headers
            df_new.to_excel(EXCEL_FILE_PATH, index=False)
            logger.info(f"Created new Excel file and saved candidate {data.get('CandidateID')}.")

    except Exception as e:
        logger.error(f"Failed to write to Excel: {e}")
        raise IOError("Could not save data to Excel file.") from e

# ---------------------------------------------------------
# Application Routes
# ---------------------------------------------------------
@app.route("/")
def serve_portal():
    """Serves the main HTML onboarding portal."""
    # Ensure index.html is in the same directory or a 'templates' folder
    return send_file("index.html")

@app.route("/api/submit", methods=["POST"])
def handle_submission():
    """Receives JSON data from the frontend and triggers the Excel save."""
    try:
        payload = request.get_json()
        
        if not payload:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # Extract data to ensure strict mapping
        candidate_record = {
            "CandidateID": payload.get("candidateId"),
            "FullName": payload.get("fullName"),
            "PhoneNumber": payload.get("phoneNumber"),
            "PAN_Number": payload.get("panNumber"),
            "Aadhaar_Number": payload.get("aadhaarNumber"),
            "DateOfBirth": payload.get("dob"),
            "Address": payload.get("address")
        }

        # Save to Excel
        save_to_excel(candidate_record)

        return jsonify({
            "status": "success", 
            "message": "Data saved successfully",
            "name": candidate_record["FullName"]
        }), 200

    except Exception as e:
        logger.error(f"Error processing submission: {e}")
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500

if __name__ == "__main__":
    # Run the server securely on localhost
    app.run(host="127.0.0.1", port=5000, debug=False)