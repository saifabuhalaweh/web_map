import time
import requests
from flask import Flask, render_template, request, jsonify
import mysql.connector
from scraper import run_scraper
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "aluminium_db")

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return None

def get_coordinates(location_string):
    headers = {
        "User-Agent": "AluminiumScraperApp/1.0"
    }
    url = f"https://nominatim.openstreetmap.org/search?q={location_string}&format=json&limit=1"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        time.sleep(1) # Respect rate limits
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"Error geocoding {location_string}: {e}")
    return None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['GET'])
def search():
    location = request.args.get('location')
    if not location:
        return jsonify({"error": "Location parameter is required"}), 400

    print(f"Running scraper for: {location}")
    scraped_companies = run_scraper(location)

    if not scraped_companies:
         return jsonify({"message": "No companies found or scraping failed.", "companies": []})

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    enriched_companies = []

    try:
        for comp in scraped_companies:
            company_id = comp.get('company_id')
            name = comp.get('name')
            comp_location = comp.get('location', '')
            
            # Check if company exists to get coordinates if already geocoded
            cursor.execute("SELECT latitude, longitude FROM companies WHERE company_id = %s", (company_id,))
            existing = cursor.fetchone()
            
            lat, lon = None, None
            if existing and existing['latitude'] is not None and existing['longitude'] is not None:
                lat, lon = float(existing['latitude']), float(existing['longitude'])
            else:
                # Geocode
                lat, lon = get_coordinates(comp_location)
            
            # Insert or update company
            cursor.execute("""
                INSERT INTO companies (company_id, name, location_string, latitude, longitude) 
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE name=%s, location_string=%s, latitude=%s, longitude=%s
            """, (company_id, name, comp_location, lat, lon, name, comp_location, lat, lon))

            # Process categories
            categories = []
            if 'main_categories' in comp:
                categories.extend([(cat, 'MAIN') for cat in comp['main_categories']])
            if 'sub_categories' in comp:
                categories.extend([(cat, 'SUB') for cat in comp['sub_categories']])

            for cat_name, cat_type in categories:
                # Insert category ignore if exists
                cursor.execute("""
                    INSERT IGNORE INTO categories (name, type) VALUES (%s, %s)
                """, (cat_name, cat_type))
                
                # Get category_id
                cursor.execute("SELECT category_id FROM categories WHERE name = %s AND type = %s", (cat_name, cat_type))
                cat_row = cursor.fetchone()
                if cat_row:
                    cat_id = cat_row['category_id']
                    # Link company and category
                    cursor.execute("""
                        INSERT IGNORE INTO company_categories (company_id, category_id) VALUES (%s, %s)
                    """, (company_id, cat_id))
            
            conn.commit()

            # Prepare final enriched object for response
            enriched_comp = comp.copy()
            enriched_comp['latitude'] = lat
            enriched_comp['longitude'] = lon
            enriched_companies.append(enriched_comp)

    except Exception as e:
         print(f"Database operation failed: {e}")
         conn.rollback()
         return jsonify({"error": "Internal database error"}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify({"companies": enriched_companies})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
