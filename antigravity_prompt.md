# SYSTEM ROLE
You are an Expert Full-Stack Developer and Database Architect. Your task is to build a complete web application utilizing Flask (Backend), MySQL (Database), and Vanilla HTML/JS with Leaflet.js (Frontend). 

# PROJECT OBJECTIVE
I have an existing Python script that scrapes and uses an AI API (DeepSeek) to find Aluminium companies based on a location. Currently, it runs in the CLI and saves output to a JSON file. 
I want you to build a web wrapper around this script. The web app should allow a user to input a location, trigger the script, process the output by fetching Geolocation coordinates via Nominatim, store the normalized data in a MySQL database, and finally display the companies on an interactive Leaflet map.

# TECH STACK
- Backend: Python 3, Flask, Requests
- Database: MySQL (using `mysql-connector-python` or `SQLAlchemy`)
- Frontend: HTML, CSS, JavaScript, Leaflet.js (via CDN)
- Existing Script Dependencies: OpenAI (DeepSeek), DDGS (DuckDuckGo Search), BeautifulSoup

# ARCHITECTURE & WORKFLOW
1. **Frontend Request:** User enters a location (e.g., "Istanbul, Turkey") and clicks Search. A GET request is sent to the Flask backend.
2. **Script Execution:** Flask runs the provided scraper script (you will need to slightly adapt the script to accept the location as a function argument instead of `input()` and return the JSON list in memory rather than writing to a file).
3. **Database Normalization & Storage:** Flask parses the returned data. It inserts companies and their categories into a normalized MySQL database (Many-to-Many relationship).
4. **Geocoding & Caching:** For each company, Flask checks the database for existing Latitude/Longitude for that specific location string. 
    - If it exists (Cache Hit): Use it.
    - If missing (Cache Miss): Call the Nominatim API, wait for 1 second (`time.sleep(1)`) to respect rate limits, get coordinates, and save them to the database.
5. **Response:** Flask returns the fully enriched JSON (with coordinates) to the Frontend.
6. **Map Rendering:** Leaflet.js plots the markers. Clicking a marker shows the company name.

# 1. DATABASE SCHEMA (MySQL)
You MUST use the following normalized structure to avoid storing JSON strings in the database:

```sql
CREATE TABLE companies (
    company_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    location_string VARCHAR(255),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL,
    type ENUM('MAIN', 'SUB') NOT NULL
);

CREATE TABLE company_categories (
    company_id VARCHAR(50),
    category_id INT,
    PRIMARY KEY (company_id, category_id),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
);
```

# 2. BACKEND REQUIREMENTS (Flask)
- Create `app.py`.
- **Adapt the Scraper:** Import the provided scraper script. Modify its `main()` function or logic so it accepts `location` as a parameter and returns the `parsed_companies` list directly to Flask instead of calling `deduplicate_and_save()`.
- **Geocoding Logic:** Create a helper function `get_coordinates(location_string)`. It should query Nominatim: `https://nominatim.openstreetmap.org/search?q={location_string}&format=json`. ALWAYS add `time.sleep(1)` after an API call to prevent getting banned. User-Agent must be set in the headers.
- **Data Insertion Flow:**
    1. Insert/Update `companies` table.
    2. Loop through `main_categories` and `sub_categories`.
    3. `INSERT IGNORE` into `categories`.
    4. Fetch the `category_id`.
    5. `INSERT IGNORE` into `company_categories`.

# 3. FRONTEND REQUIREMENTS
- Provide an `index.html` file (can be served via Flask `render_template`).
- Include a simple, clean UI with an input field and a "Search" button.
- Include a `<div id="map"></div>` with a defined height.
- Include Leaflet.js CSS and JS via CDN.
- Write JavaScript to handle the `fetch` call to the Flask API.
- While fetching, show a loading indicator (the scraper takes time).
- Once data is received, clear old map markers, iterate over the JSON, and add `L.marker` to the map using the `latitude` and `longitude`. Bind a popup with the company `name`.

# 4. EXISTING PYTHON SCRAPER SCRIPT
Below is the original script. Adapt it as requested in Step 2:

```python
import os
import re
import json
import hashlib
import time
from dotenv import load_dotenv
from ddgs import DDGS
from openai import OpenAI
import requests
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
    print("ERROR: DEEPSEEK_API_KEY is not set or is using the default placeholder.")
    print("Please update the .env file with your actual DeepSeek API key.")
    exit(1)

# DeepSeek Configuration
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

OUTPUT_FILE = "companies_data.json"

SEARCH_KEYWORDS = [
    "LED Profile", "LED Aluminium Profile", "LED Strip Profile",
    "Tile Trim Profile", "Tile Edge Profile", "Ceramic Tile Trim",
    "Furniture Profiles", "Cabinet/Kitchen Profiles",
    "Glass Profiles", "Shower & Glass Profiles",
    "Decorative Profiles", "Wall & Ceiling Profiles",
    "Small/Light Aluminium Extrusion"
]

EXCLUDED_DOMAINS = [
    "alibaba.com", "made-in-china.com", "globalsources.com",
    "indiamart.com", "exportersindia.com", "tradeindia.com",
    "ec21.com", "europages.com", "europages.co.uk", "kompass.com",
    "wlw.de", "yellowpages.com", "linkedin.com", "facebook.com",
    "youtube.com", "pinterest.com", "instagram.com", "twitter.com",
]

COUNTRY_REGION_MAP = {
    "argentina": "ar-es", "australia": "au-en", "austria": "at-de",
    "belgium": "be-nl", "brazil": "br-pt", "bulgaria": "bg-bg",
    "canada": "ca-en", "chile": "cl-es", "china": "cn-zh",
    "colombia": "co-es", "croatia": "hr-hr", "czech republic": "cz-cs",
    "czechia": "cz-cs", "denmark": "dk-da", "estonia": "ee-et",
    "finland": "fi-fi", "france": "fr-fr", "germany": "de-de",
    "greece": "gr-el", "hong kong": "hk-tzh", "hungary": "hu-hu",
    "india": "in-en", "indonesia": "id-id", "ireland": "ie-en",
    "israel": "il-he", "italy": "it-it", "japan": "jp-jp",
    "south korea": "kr-kr", "korea": "kr-kr", "latvia": "lv-lv",
    "lithuania": "lt-lt", "malaysia": "my-ms", "mexico": "mx-es",
    "netherlands": "nl-nl", "holland": "nl-nl", "new zealand": "nz-en",
    "norway": "no-no", "peru": "pe-es", "philippines": "ph-en",
    "poland": "pl-pl", "portugal": "pt-pt", "romania": "ro-ro",
    "russia": "ru-ru", "singapore": "sg-en", "slovakia": "sk-sk",
    "slovak republic": "sk-sk", "slovenia": "sl-sl", "south africa": "za-en",
    "spain": "es-es", "sweden": "se-sv", "switzerland": "ch-de",
    "taiwan": "tw-tzh", "thailand": "th-th", "turkey": "tr-tr",
    "türkiye": "tr-tr", "turkiye": "tr-tr", "ukraine": "ua-uk",
    "united kingdom": "uk-en", "uk": "uk-en", "britain": "uk-en",
    "great britain": "uk-en", "united states": "us-en", "usa": "us-en",
    "u.s.": "us-en", "u.s.a.": "us-en", "united states of america": "us-en",
    "venezuela": "ve-es", "vietnam": "vn-vi",
    
    # Arab League & Others
    "algeria": "xa-en", "egypt": "xa-en", "iraq": "xa-en",
    "jordan": "xa-en", "kuwait": "xa-en", "lebanon": "xa-en",
    "morocco": "xa-en", "oman": "xa-en", "palestine": "xa-en",
    "qatar": "xa-en", "saudi arabia": "xa-en", "ksa": "xa-en",
    "syria": "xa-en", "tunisia": "xa-en", "united arab emirates": "xa-en",
    "uae": "xa-en", "dubai": "xa-en", "yemen": "xa-en"
}


def guess_region(location: str) -> str:
    loc_lower = location.lower()
    for country in sorted(COUNTRY_REGION_MAP, key=len, reverse=True):
        if country in loc_lower:
            return COUNTRY_REGION_MAP[country]
    return "wt-wt"


def location_tokens(location: str) -> list:
    parts = re.split(r"[,/]", location)
    tokens = [p.strip().lower() for p in parts if p.strip()]
    return tokens


def generate_company_id(name: str) -> str:
    normalized_name = name.strip().lower()
    return hashlib.md5(normalized_name.encode('utf-8')).hexdigest()


def scrape_website_text(url: str) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()

        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)

        return cleaned_text[:4000]
    except Exception as e:
        print(f"    - Failed to scrape {url}: {e}")
        return None


def fetch_search_results(location: str) -> list:
    print(f"Starting deep search for aluminium companies in {location}...")

    region = guess_region(location)
    print(f"Using DDGS region bias: {region}")

    exclude_clause = " ".join(f"-site:{d}" for d in EXCLUDED_DOMAINS)

    unique_urls = set()
    fallback_snippets = {} 

    start_time = time.time()
    time_limit = 300  # 5 minutes

    clean_loc = location.replace(',', ' ')

    for keyword in SEARCH_KEYWORDS:
        if time.time() - start_time >= time_limit:
            break

        query = f'{keyword} aluminium {clean_loc} {exclude_clause}'
        print(f"  Searching: '{query}'")

        try:
            results = DDGS().text(query, region=region, max_results=30)
            if results:
                for r in results:
                    url = r.get('href', '')
                    snippet = r.get('body', '')
                    if not url or url in unique_urls:
                        continue
                    if any(domain in url for domain in EXCLUDED_DOMAINS):
                        continue
                    unique_urls.add(url)
                    fallback_snippets[url] = {
                        "title": r.get('title', ''),
                        "snippet": snippet
                    }
        except Exception as e:
            print(f"    - Error fetching search results: {e}")

        time.sleep(1)

    results_list = []
    url_list = list(unique_urls)
    
    for idx, url in enumerate(url_list):
        data = fallback_snippets[url]
        title = data['title']
        snippet = data['snippet']
        scraped_text = scrape_website_text(url)
        content = scraped_text if scraped_text else snippet
        results_list.append(f"Result {idx+1}:\nTitle: {title}\nURL: {url}\nContent: {content}\n")

    return results_list


def parse_with_ai(raw_text_chunk: str, location: str) -> list:
    prompt = f"""You are a data extraction expert. Read the following batch of scraped text.
TARGET LOCATION: {location}
RULE: Extract companies that operate in or are based in {location}.
Schema: {{"name": "string", "location": "string", "main_categories": ["string"], "sub_categories": ["string"]}}
Raw Text Batch:
{raw_text_chunk}
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that strictly outputs valid JSON. Return ONLY the requested JSON format."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.endswith("```"): content = content[:-3]

        parsed_data = json.loads(content)
        if isinstance(parsed_data, dict) and "companies" in parsed_data:
            return parsed_data["companies"]
        return []
    except Exception as e:
        return []

def filter_by_location(companies: list, location: str) -> list:
    tokens = location_tokens(location)
    if not tokens:
        return companies
    kept = []
    for comp in companies:
        comp_location = str(comp.get("location", "")).lower()
        if all(tok in comp_location for tok in tokens):
            kept.append(comp)
    return kept

# NOTE FOR AI: The original deduplicate_and_save() saved to a file. 
# You should replace this logic to integrate with MySQL instead.
```

# REQUIRED DELIVERABLES FROM YOU:
1. `database_setup.sql`: To create the tables.
2. `scraper.py`: The adapted version of the provided script (acting as a module).
3. `app.py`: The Flask backend handling the API route, DB logic, and Geocoding.
4. `templates/index.html`: The frontend map interface.
5. `requirements.txt` and quick run instructions.