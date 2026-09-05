import json
import requests
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://www.crossfit.com/workout/{}/{:02d}/{:02d}"
OUTPUT_DIR = Path("data")
LAST_DATE_FILE = Path("last_date.txt")

MONTHS = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec"
]


def read_last_date():
    if LAST_DATE_FILE.exists():
        return date.fromisoformat(LAST_DATE_FILE.read_text().strip())
    else:
        return date(2002, 1, 4)   # first run fallback


def write_last_date(d):
    LAST_DATE_FILE.write_text(d.isoformat())


def fetch_wod(wod_date):
    url = BASE_URL.format(
        wod_date.year,
        wod_date.month,
        wod_date.day
    )

    response = requests.get(
        url,
        headers={"Accept": "application/json"}
    )
    response.raise_for_status()

    data = response.json()["wods"]

    return {
        "date": wod_date.isoformat(),
        "title": data.get("title"),
        "wodRaw": data.get("wodRaw"),
        "otherRaw": data.get("otherRaw", []),
        "source": "crossfit.com"
    }


def main():
    last_saved = read_last_date()
    current_date = last_saved + timedelta(days=1)
    END_DATE = date.today()

    while current_date <= END_DATE:

        year = current_date.year
        month = current_date.month

        folder = OUTPUT_DIR / str(year)
        file_path = folder / f"{MONTHS[month - 1]}_{year}.json"

        folder.mkdir(parents=True, exist_ok=True)

        # Load existing monthly file
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                workouts = json.load(f)
        else:
            workouts = []

        iso = current_date.isoformat()

        # Don't fetch if this date already exists
        if any(w["date"] == iso for w in workouts):
            print(f"SKIP  {current_date}")
        else:
            print(f"FETCH {current_date}")

            try:
                wod = fetch_wod(current_date)

                if wod['wodRaw'] != 'Rest Day':
                    workouts.append(wod)

                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(workouts, f, indent=2, ensure_ascii=False)

                    print(f"SAVED {file_path}")
                else:
                    print("SKIPPED Rest Day")

            except Exception as e:
                print(f"ERROR {current_date}: {e}")

        # Update last_date.txt every loop
        write_last_date(current_date)

        current_date += timedelta(days=1)


if __name__ == "__main__":
    main()
