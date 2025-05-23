# security_test.py
import os
import yaml
import requests
import sqlite3
from urllib.parse import urljoin, urlencode

def print_test_result(test_id, name, status_code, result_is_vulnerable, reason):
    """Prints the test result in the specified format."""
    result_icon = "❌ 취약" if result_is_vulnerable else "✅ 안전"
    print("--------------------------------------------------")
    print(f"[Test ID: {test_id}] {name}")
    print(f"Status Code: {status_code if status_code is not None else 'N/A'}")
    print(f"결과: {result_icon}")
    print(f"이유: {reason}")
    print("--------------------------------------------------\n")

def perform_db_read(db_path, table, column, value_to_check):
    conn = None
    try:
        # Ensure the DB path is correct. If main.py and security_test.py are in the same
        # directory, and main.py uses "mock_db.sqlite3", this should work.
        if not os.path.exists(db_path):
            return False, f"DB_CHECK_ERROR: Database file not found at '{os.path.abspath(db_path)}'. Ensure FastAPI app has run and created it."

        conn = sqlite3.connect(db_path, timeout=5) # Add a timeout
        cursor = conn.cursor()
        # Using placeholder for value_to_check to prevent SQLi in the test script itself.
        query = f"SELECT COUNT(*) FROM \"{table}\" WHERE \"{column}\" = ?" # Ensure table/column names are quoted if needed
        cursor.execute(query, (value_to_check,))
        count = cursor.fetchone()[0]
        return count > 0, None  # True if found, False if not found, no error
    except sqlite3.OperationalError as e:
        # This can happen if the DB is locked or table/column doesn't exist.
        return False, f"DB_CHECK_ERROR: sqlite3.OperationalError: {e}. (Is the table/column correct? Is the DB locked?)"
    except sqlite3.Error as e:
        return False, f"DB_CHECK_ERROR: An SQLite error occurred: {e}"
    except Exception as e:
        return False, f"DB_CHECK_ERROR: A non-SQLite error occurred during DB check: {e}"
    finally:
        if conn:
            conn.close()

# --- Main Test Execution ---
def run_tests(scenario_file_path):
    try:
        with open(scenario_file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Scenario file not found at {scenario_file_path}")
        return
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return

    base_url = config.get("base_url")
    db_path = config.get("database_path", "mock_db.sqlite3") # Get DB path from config
    test_scenarios = config.get("tests", [])

    if not base_url:
        print("Error: 'base_url' not defined in scenario file.")
        return

    session = requests.Session()

    for scenario in test_scenarios:
        test_id = scenario.get("id", "UnknownID")
        name = scenario.get("name", "Unnamed Test")
        method = scenario.get("method", "GET").upper()
        endpoint = scenario.get("endpoint", "/")
        params = scenario.get("params", {})
        expected_status = scenario.get("expected_status")

        actual_status = None
        is_vulnerable = False # Default to safe unless a vulnerability is proven
        reason = "Test not fully executed or condition not met."

        try:
            full_url = urljoin(base_url, endpoint)
            response = None

            clean_params = {k: v for k, v in params.items()} # if v is not None - requests handles None well

            if method == "POST":
                # For form data, requests expects a dict of strings or None.
                form_data = {k: str(v) if v is not None else None for k, v in clean_params.items()}
                response = session.post(full_url, data=form_data, allow_redirects=False)
            elif method == "GET":
                response = session.get(full_url, params=clean_params, allow_redirects=False)
            else:
                reason = f"Unsupported HTTP method: {method}"
                print_test_result(test_id, name, None, True, reason) # Mark as vulnerable/error
                continue

            actual_status = response.status_code

            # --- Determine Vulnerability ---
            # Special handling for A5 (API docs exposure)
            if scenario.get("interpret_status_match_as") == "vulnerable":
                if actual_status == expected_status:
                    is_vulnerable = True
                    reason = scenario["reason_if_vulnerable"]
                else:
                    is_vulnerable = False
                    reason = scenario["reason_if_safe"] % actual_status
            # Handling for tests with db_check
            elif "db_check" in scenario:
                if actual_status != expected_status:
                    is_vulnerable = True # HTTP status mismatch is a failure for this test type
                    reason = f"HTTP status was {actual_status}, expected {expected_status}. DB check not performed."
                else: # HTTP status is as expected, proceed to DB check
                    db_config = scenario["db_check"]
                    item_found, db_err_msg = perform_db_read(
                        db_path,
                        db_config["table"],
                        db_config["column"],
                        db_config["value_to_check"]
                    )

                    if db_err_msg:
                        is_vulnerable = True # Treat DB read error as a vulnerability/failure of the test
                        reason = db_err_msg
                    else:
                        # expect_to_find: False means finding it makes it vulnerable
                        # expect_to_find: True means NOT finding it makes it vulnerable (not used in current YAML)
                        if db_config["expect_to_find"] == False:
                            if item_found: # Found when we didn't want to
                                is_vulnerable = True
                                reason = scenario["reason_if_found_in_db"]
                            else: # Not found, and we didn't want to (this is "safe" for this check)
                                is_vulnerable = False
                                reason = scenario["reason_if_not_found_in_db"]
                        else: # expect_to_find == True
                            if not item_found: # Not found when we wanted to
                                is_vulnerable = True
                                reason = scenario.get("reason_if_not_found_but_expected", # New key needed in YAML if this path is used
                                                      "Vulnerable: Expected item was NOT found in DB.")
                            else: # Found, and we wanted to (this is "safe")
                                is_vulnerable = False
                                reason = scenario.get("reason_if_found_and_expected", # New key
                                                      "Safe: Expected item was found in DB.")
            else:
                if actual_status == expected_status:
                    is_vulnerable = False
                    reason = f"HTTP status {actual_status} matches expected. No other checks defined for this test."
                else:
                    is_vulnerable = True
                    reason = f"HTTP status was {actual_status}, but expected {expected_status}."

        except requests.exceptions.ConnectionError as e:
            is_vulnerable = True
            reason = f"Connection Error: {e}. Ensure the FastAPI server is running at {base_url}."
            actual_status = None
        except Exception as e:
            is_vulnerable = True
            reason = f"An unexpected error occurred during test execution: {e}"
            actual_status = actual_status if 'actual_status' in locals() else None

        print_test_result(test_id, name, actual_status, is_vulnerable, reason)

if __name__ == "__main__":
    current_script_dir = os.path.dirname(__file__)
    if not current_script_dir:
        current_script_dir = "."
    
    scenario_file_abs_path = os.path.abspath(os.path.join(current_script_dir, "scenario.yaml"))
    
    print(f"Attempting to load scenarios from: {scenario_file_abs_path}\n")
    run_tests(scenario_file_abs_path)