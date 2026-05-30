import urllib.request
import csv
import io
import os
import shutil
from datetime import datetime

SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRIakaBzNVNdA3Y6v6ve54-CEKD22Tk4bREgvKI4noaPiqLqqc_YZwdwc2xXOMq0t3Ma6teLoa7p2Rf/pub?output=csv"
OUTPUT_FILE = "/home/codar/data/events.csv"
BACKUP_DIR = "/home/codar/data/backups"

# Map the days in the spreadsheet to the exact dates of the festival
DATE_MAP = {
    "Wednesday": "2026-06-03",
    "Thursday":  "2026-06-04",
    "Friday":    "2026-06-05",
    "Saturday":  "2026-06-06",
    "Sunday":    "2026-06-07",
    "Monday":    "2026-06-08"
}

def sync():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting sync process...")
    try:
        response = urllib.request.urlopen(SHEET_URL)
        csv_data = response.read().decode('utf-8')

        if os.path.exists(OUTPUT_FILE):
            if not os.path.exists(BACKUP_DIR):
                os.makedirs(BACKUP_DIR)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(BACKUP_DIR, f"events_backup_{timestamp}.csv")
            shutil.copy2(OUTPUT_FILE, backup_file)

        # Use standard reader instead of DictReader to bypass the messy top rows
        reader = csv.reader(io.StringIO(csv_data))

        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            # The exact headers the rotary phone engine requires
            writer.writerow(['time', 'description', 'camp'])

            valid_rows = 0
            for row in reader:
                # Skip rows that don't even have enough columns
                if len(row) < 9:
                    continue

                day = row[2].strip()
                start_time = row[3].strip()
                camp = row[5].strip()
                event_name = row[7].strip()
                event_desc = row[8].strip()

                # Skip the header row itself and any day-divider rows
                if day == "Day" or not start_time:
                    continue

                # Look up the calendar date based on the day of the week
                date_str = DATE_MAP.get(day)
                if not date_str:
                    continue # Skip if the day isn't in our map

                # Format: "2026-05-28 09:00"
                formatted_time = f"{date_str} {start_time}"

                # Combine the title and description for Espeak/Flite to read naturally
                full_description = f"{event_name}. {event_desc}"

                # Write to the file!
                writer.writerow([formatted_time, full_description, camp])
                valid_rows += 1

        print(f"Success! Saved {valid_rows} events to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error syncing events: {e}")

if __name__ == "__main__":
    sync()
