import json
import logging
import time
from datetime import datetime
from pathlib import Path

from ollama import chat as ollama_chat

# ═══════════════════════════════════════════════════════════════════════════════
# ── CONFIGURATION ──────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

MODEL        = "gemma4:31b-cloud"
INPUT_ROOT   = Path("data")              # e.g., output/2002/april.json
OUTPUT_ROOT  = Path("output_cleaned")      # e.g., output_cleaned/2002/april.json
PROMPT_FILE  = Path("cfwod_prompt.md")
MAX_RETRIES  = 3
RETRY_DELAY  = 2

# ── Field Mapping (customize for your JSON structure) ──────────────────────────
DATE_FIELD       = "date"          # field name for workout date
WORKOUT_FIELD    = "wodRaw"        # field name for workout content
TITLE_FIELD      = "title"         # optional: workout title
OTHER_FIELD      = "otherRaw"      # optional: additional content (list/string)
SOURCE_FIELD     = "source"        # optional: source attribution

MIN_CONTENT_LEN  = 10              # skip if workout text is shorter than this

# ═══════════════════════════════════════════════════════════════════════════════
# ── LOGGING ────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("wod_parser.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ── HELPERS ────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def strip_fences(raw: str) -> str:
    """Remove accidental ```json ... ``` wrapping from model output."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def normalize_date(date_str: str) -> str:
    """
    Try to parse and normalize date to YYYY-MM-DD format.
    If already in that format or parsing fails, return as-is.
    """
    if not date_str:
        return ""
    
    date_str = str(date_str).strip()
    
    # Already in YYYY-MM-DD format
    if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
        return date_str
    
    # Try parsing common formats
    formats = [
        "%Y-%m-%d",      # 2002-04-01
        "%d-%b-%Y",      # 16-JAN-2023
        "%d-%B-%Y",      # 16-January-2023
        "%m/%d/%Y",      # 01/16/2023
        "%Y/%m/%d",      # 2023/01/16
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If all else fails, return original
    return date_str

# ═══════════════════════════════════════════════════════════════════════════════
# ── DATA EXTRACTION ────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def extract_workout_from_entry(entry: dict) -> dict | None:
    """
    Extract workout data from a single day entry.
    Returns None if content is invalid or too short.
    """
    # Get date (required)
    date = entry.get(DATE_FIELD, "")
    if not date:
        return None
    
    # Get workout content (required)
    workout_content = entry.get(WORKOUT_FIELD, "")
    if not isinstance(workout_content, str) or len(workout_content.strip()) < MIN_CONTENT_LEN:
        return None
    
    # Build the workout data
    data = {
        "date": date,
        "content": workout_content.strip(),
    }
    
    # Optional: title
    if TITLE_FIELD and TITLE_FIELD in entry:
        title = entry[TITLE_FIELD]
        if title:
            data["title"] = str(title)
    
    # Optional: other content (merge if list)
    if OTHER_FIELD and OTHER_FIELD in entry:
        other = entry[OTHER_FIELD]
        if isinstance(other, list):
            other_text = "\n".join(str(x) for x in other if x)
            if other_text:
                data["other"] = other_text
        elif isinstance(other, str) and other.strip():
            data["other"] = other
    
    # Optional: source
    if SOURCE_FIELD and SOURCE_FIELD in entry:
        source = entry[SOURCE_FIELD]
        if source:
            data["source"] = str(source)
    
    return data

# ═══════════════════════════════════════════════════════════════════════════════
# ── LLM CALL ───────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def call_llm(system_prompt: str, user_message: str) -> list:
    """
    Send all workouts from a file to LLM in one batch.
    Retries up to MAX_RETRIES times.
    Returns list of parsed workout dicts.
    """
    last_error = None
    raw = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("  LLM attempt %d/%d", attempt, MAX_RETRIES)

            response = ollama_chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                options={
                    "temperature": 0.1,
                    "format": "json",
                },
            )

            raw   = response.message.content.strip()
            clean = strip_fences(raw)
            parsed = json.loads(clean)
            
            # Ensure it's a list
            if not isinstance(parsed, list):
                parsed = [parsed]
            
            return parsed

        except json.JSONDecodeError as e:
            last_error = e
            log.warning("  Attempt %d — JSON parse error: %s", attempt, e)
            if raw:
                log.debug("  Raw response (first 300 chars): %s", raw[:300])
        except Exception as e:
            last_error = e
            log.warning("  Attempt %d — Ollama error: %s", attempt, e)

        if attempt < MAX_RETRIES:
            log.info("  Waiting %ds before retry...", RETRY_DELAY)
            time.sleep(RETRY_DELAY)

    raise RuntimeError(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")

# ═══════════════════════════════════════════════════════════════════════════════
# ── FILE PROCESSOR ─────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def process_json_file(input_path: Path, system_prompt: str) -> None:
    """
    Process a single JSON file:
    1. Load array of daily workouts
    2. Extract valid entries
    3. Send to LLM in one batch
    4. Write output
    """
    relative    = input_path.relative_to(INPUT_ROOT)
    output_path = OUTPUT_ROOT / relative
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("Processing: %s", input_path)

    # Load array from file
    try:
        raw_data = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error("  Failed to read %s — %s", input_path, e)
        return

    # Ensure it's an array
    if not isinstance(raw_data, list):
        log.error("  Expected array at root level, got %s", type(raw_data).__name__)
        return

    log.info("  Loaded %d entries", len(raw_data))

    # Extract valid workouts from each day
    filtered_workouts = []
    for idx, entry in enumerate(raw_data, start=1):
        if not isinstance(entry, dict):
            log.debug("  Skipping entry %d — not a dict", idx)
            continue
        
        extracted = extract_workout_from_entry(entry)
        if extracted:
            filtered_workouts.append(extracted)
        else:
            log.debug("  Skipping entry %d — invalid/empty content", idx)
    
    if not filtered_workouts:
        log.warning("  No valid workouts found after filtering")
        return

    log.info("  Extracted %d valid workouts", len(filtered_workouts))
    log.info("  Sending to LLM...", )

    # Build message with all workouts
    user_message = json.dumps(filtered_workouts, ensure_ascii=False, indent=2)

    # Send to LLM
    try:
        results = call_llm(system_prompt, user_message)
        log.info("  LLM returned %d workout(s)", len(results))

        # Post-process results
        for workout in results:
            if "metadata" not in workout:
                workout["metadata"] = {}
            
            # Normalize date
            date_val = workout.get("metadata", {}).get("date", "")
            if date_val:
                workout["metadata"]["date"] = normalize_date(date_val)
            
            # Ensure source
            if "source" not in workout["metadata"]:
                workout["metadata"]["source"] = "CrossFit.com"

        # Write output
        output_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("  ✓ Saved %d workouts → %s", len(results), output_path)

    except RuntimeError as e:
        log.error("  ✗ LLM processing failed — %s", e)
        
        # Save unprocessed data for manual review
        fail_path = output_path.with_suffix(".failed.json")
        fail_path.write_text(
            json.dumps(
                {"error": str(e), "entries": filtered_workouts},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        log.warning("  Saved unprocessed data to: %s", fail_path)

# ═══════════════════════════════════════════════════════════════════════════════
# ── MAIN ───────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    log.info("=== WOD Parser (Array Per File) ===")
    log.info("Model       : %s", MODEL)
    log.info("Input root  : %s", INPUT_ROOT)
    log.info("Output root : %s", OUTPUT_ROOT)
    log.info("Date field  : %s", DATE_FIELD)
    log.info("Workout field: %s", WORKOUT_FIELD)

    # Load prompt
    try:
        system_prompt = load_prompt(PROMPT_FILE)
        log.info("Prompt loaded: %s\n", PROMPT_FILE)
    except FileNotFoundError as e:
        log.error("Fatal: %s", e)
        return

    # Find all JSON files
    json_files = sorted(INPUT_ROOT.rglob("*.json"))

    if not json_files:
        log.warning("No JSON files found under %s", INPUT_ROOT)
        return

    log.info("Found %d JSON file(s) to process\n", len(json_files))

    start = datetime.now()

    for json_file in json_files:
        try:
            process_json_file(json_file, system_prompt)
            log.info("")  # blank line for readability
        except Exception as e:
            log.error("Unexpected error processing %s: %s\n", json_file, e)

    elapsed = datetime.now() - start
    log.info("=== Done in %s ===", elapsed)


if __name__ == "__main__":
    main()