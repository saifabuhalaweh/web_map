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

client = None
if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your_deepseek_api_key_here":
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

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
    if not client:
        print("ERROR: DeepSeek API client is not initialized.")
        return []
        
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
        print(f"Error parsing with AI: {e}")
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

def run_scraper(location: str) -> list:
    """Main execution entry point that returns a list of dictionaries."""
    results = fetch_search_results(location)
    if not results:
        return []
        
    all_companies = []
    chunk_size = 5
    for i in range(0, len(results), chunk_size):
        chunk = results[i:i + chunk_size]
        text_batch = "\n---\n".join(chunk)
        extracted = parse_with_ai(text_batch, location)
        all_companies.extend(extracted)
        
    filtered = filter_by_location(all_companies, location)
    
    for comp in filtered:
        comp['company_id'] = generate_company_id(comp['name'] + comp.get('location', ''))
        
    return filtered