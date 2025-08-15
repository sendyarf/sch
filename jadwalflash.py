import json
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException

# List of URLs to scrape
urls = [
    {"url": "https://www.flashscore.com/football/england/premier-league/fixtures/", "league": "Premier League"},
    {"url": "https://www.flashscore.com/football/england/championship/fixtures/", "league": "Championship"}
]

# Set up Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Run in headless mode
chrome_options.add_argument("--disable-gpu")  # Disable GPU for compatibility
chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems

# Print initial notification
print("Starting to scrape football schedules from Flashscore...")

# Initialize the WebDriver with headless options
driver = webdriver.Chrome(options=chrome_options)

data = []
# Get current date dynamically and calculate the end date (3 days from now)
current_date = datetime.now()
end_date = current_date + timedelta(days=3)
# Set current_date to start of day for accurate date comparison
current_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
current_year = current_date.year
current_month = current_date.month

# Iterate over each URL
for league_info in urls:
    url = league_info["url"]
    league_name = league_info["league"]
    print(f"Navigating to {league_name} fixtures page: {url}")

    # Navigate to the URL
    driver.get(url)

    # Wait for the page to load
    print(f"Waiting for {league_name} page to load...")
    time.sleep(5)  # Basic wait; can be improved with WebDriverWait

    # Handle "Show more matches" if present
    print(f"Checking for 'Show more matches' button for {league_name}...")
    while True:
        try:
            show_more = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.wclButtonLink"))
            )
            print(f"Clicking 'Show more matches' to load additional {league_name} fixtures...")
            show_more.click()
            time.sleep(2)  # Wait for more content to load
        except:
            print(f"No more matches to load for {league_name}.")
            break

    # Find all match elements
    print(f"Collecting match data for {league_name}...")
    match_elements = driver.find_elements(By.CSS_SELECTOR, ".event__match--twoLine, .event__match--static")

    for match in match_elements:
        try:
            # Home team
            home_participant = match.find_element(By.CLASS_NAME, "event__homeParticipant")
            home_name = home_participant.find_element(By.CSS_SELECTOR, "span.wcl-name_jjfMf").text

            # Away team
            away_participant = match.find_element(By.CLASS_NAME, "event__awayParticipant")
            away_name = away_participant.find_element(By.CSS_SELECTOR, "span.wcl-name_jjfMf").text

            # Time and date
            time_div = match.find_element(By.CLASS_NAME, "event__time")
            time_text = time_div.text.split("\n")[0]  # Get the time line, ignore preview if present
            date_parts = time_text.split(" ")[0].rstrip(".").split(".")
            day = date_parts[0].zfill(2)
            month = date_parts[1].zfill(2)
            kickoff_time = time_text.split(" ")[1]

            # Determine the year dynamically
            match_month = int(month)
            # If current month is August or later, matches in January or early months belong to next year
            if current_month >= 8 and match_month <= 3:
                match_year = current_year + 1
            else:
                match_year = current_year

            # Construct date
            kickoff_date = f"{match_year}-{month}-{day}"

            # Validate and filter date
            try:
                match_date = datetime.strptime(kickoff_date, "%Y-%m-%d")
                # Include today's matches and next 3 days
                if current_date <= match_date <= end_date:
                    # Adjust match_time by subtracting 10 minutes
                    try:
                        time_obj = datetime.strptime(kickoff_time, "%H:%M")
                        adjusted_time = time_obj - timedelta(minutes=10)
                        adjusted_time_str = adjusted_time.strftime("%H:%M")
                    except ValueError:
                        # If time format is invalid, keep original time
                        adjusted_time_str = kickoff_time
                        print(f"Warning: Invalid time format for {league_name} match {home_name} vs {away_name}, using original time: {kickoff_time}")

                    # ID without spaces
                    match_id = f"{league_name.replace(' ', '')}-{home_name.replace(' ', '')}-{away_name.replace(' ', '')}"

                    # Build the item
                    item = {
                        "id": match_id,
                        "league": league_name,
                        "team1": {
                            "name": home_name
                        },
                        "team2": {
                            "name": away_name
                        },
                        "kickoff_date": kickoff_date,
                        "kickoff_time": kickoff_time,
                        "match_date": kickoff_date,  # Same format as kickoff_date (YYYY-MM-DD)
                        "match_time": adjusted_time_str,  # Adjusted time (-10 min)
                        "duration": "3.5",
                        "servers": []
                    }

                    data.append(item)
            except ValueError:
                # If invalid date, skip
                print(f"Skipping {league_name} match {home_name} vs {away_name} due to invalid date: {kickoff_date}")
                continue

        except NoSuchElementException:
            # Skip if elements not found
            print(f"Skipping a {league_name} match due to missing elements.")
            continue

# Save to event.json
print(f"Saving {len(data)} matches to event.json...")
with open("event.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Scraping completed successfully! Data saved to event.json.")

# Close the driver
driver.quit()