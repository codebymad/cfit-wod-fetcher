# CrossFit WOD Scraper

This repository automatically collects daily CrossFit.com workouts (WODs) and stores them in a structured JSON archive. 
The scraper runs incrementally - only fetching new workouts since the last run - and is fully automated using GitHub Actions.


---


## 🔎 Overview

- Scrapes CrossFit.com WODs using their JSON API
- Saves each workout into monthly JSON files
- Skips "Rest Day" entries
- Tracks the last scraped date in `last_date.txt`
- Runs automatically at month end
- Creates a new branch with updated data
- Opens a Pull Request automatically


---


## 🔍 Repository Structure

```
python crossfit_wod.py	 # Main scraper script
last_date.txt	         #holds the last scraped date
data/
  2024/
    sep_2024.json	     # Example monthly WOD file
.github/
  workflows/
    crossfit_scrapper.yml	 # GitHub Actions workflow
```


---

## 🔌 Incremental Scraping Logic

The scraper reads the date stored in `last_date.txt`.

Example:

```text
2026-09-05
```

It then:

1. Converts this to a Python `date`
2. Starts scraping from *last_date + 1 day*)
3. Continues until *today*
4. Saves new workouts into the correct monthly JSON file
5. Updates `last_date.txtt` after each process

This ensures:

- No duplicate scraping
- No wasted API calls
- No reprocessing old data
- Fully incremental monthly updates


---


## 🔌 GitHub Actions Automation

The workflow (`.github/workflows/crossfit_scrapper.yml`) does:

- Running the scraper monthly
- Detecting whether new data was added
- Creating a new branch (e.g. `wod-update-2026-09-30`)
- Committing updated JSON files + `last_date.txtt`
- Opening a Pull Request automatically


## Schedule

GitHub cron runs:

```text
0 5 1 * *  #0 500 UTC on the 1st of every month
```

This maps to:

- 12:00 AM EST (winter)
- 1:00 AM EDT (summer)

GitHub cron uses UTC and does not adjast for DST.


---

## 🔎 Manual Run

You can trigger the scraper manually:


1. Go to Actions tab 
2. Select *Monthly CrossFit WOD Scraper**
3. Click *Run workflow*


---


## 🔎 Running Locally

Install dependencies:

```bash
pip setup requests
```

Run the scraper:

```bash
python0myscraper.py
```

Ensure `last_date.txt` contains a valid ISO Date:

```text
2002-01-04```


---


## 🔌 Monthly JSON Format

Each monthly file contains a list of workouts:

````json
  [
    {
      "date": "2024-09-12",
      "title": "For Time",
      "wodRaw": "21-15-9 reps of: Deadlifts, Handstand Push-Ups",
      "otherRaw": [],
      "source": "crossfit.com"
    }
  ]```


---


## ' Future Enhancements

- HTML fallback scraping 
- Movement parsing / normalization
- SQLite or MongoDB storage
- Daily workflow
- Slack/Discord notifications
- Retry logic for failed dates


---


## 📄 Legal Notice

CrossFit® is a registered trademark of CrossFit LLC.  
All workout descriptions, titles, and related content belong to CrossFit LLC and are sourced from CrossFit.com.  
This project is an independent archival tool and is not affiliated with or endorsed by CrossFit LLC.

---

## 💆 License

CrossFit® is a registered trademark and all workout content belongs to CrossFit LLC.
This project is open-source and free to use.
