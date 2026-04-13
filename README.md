# Lead Generation ERP System

A web-based ERP solution for scraping business leads from various sources like Google Maps, IndiaMART, Zoho Partners, etc.

## Features

- Multi-source web scraping (Google Maps, IndiaMART, Zoho Partners)
- Configurable scraping parameters (sector, city, data amount)
- Database storage for leads
- Web interface for scraping and viewing leads
- REST API for integration

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup Database**
   - Install SQL Server Express and SSMS
   - Ensure your server name is `ADMIN\SQLEXPRESS`
   - Install the Microsoft ODBC Driver for SQL Server (17 or 18)
   - Run the setup script:
     ```bash
     python setup_db.py
     ```
   - If needed, update the server name in `backend/models/db.py` and `setup_db.py`

3. **Install ChromeDriver**
   - Download ChromeDriver from https://chromedriver.chromium.org/
   - Add to PATH or place in the project directory

4. **Run the Application**
   ```bash
   python backend/app.py
   ```
5. **Verify DB Connection**
   - Open `frontend/index.html`
   - Enter `ADMIN\\SQLEXPRESS` and `leads_db`
   - Click `Test DB Connection`
   - If it works, then click `Start Scraping`

## SQL Server troubleshooting

If the connection still fails:

- Open **SQL Server Configuration Manager**
- Under **SQL Server Services**, ensure **SQL Server (SQLEXPRESS)** is running
- Under **SQL Server Network Configuration**, enable **TCP/IP** and **Named Pipes**
- Start the **SQL Server Browser** service if it is stopped
- Try `localhost\\SQLEXPRESS` or `127.0.0.1\\SQLEXPRESS` as the server name
- Make sure the instance name is exactly `SQLEXPRESS`

5. **Open Frontend**
   - Open `frontend/index.html` in your browser
   - Or serve it with a web server

## Usage

1. Select a scraper source
2. Enter sector/keyword (e.g., "restaurants")
3. Enter city (e.g., "New York")
4. Specify data amount (max results)
5. Click "Start Scraping"
6. View results and stored leads

## API Endpoints

- `POST /scrape` - Start scraping job
- `GET /leads` - Retrieve stored leads

## Adding New Scrapers

1. Create a new scraper function in `scrapers/`
2. Add to SCRAPERS dict in `routes/scrape_routes.py`
3. Update frontend select options

## Note

This is a demo implementation. For production use:
- Implement proper error handling
- Add authentication and authorization
- Use headless browsers for scraping
- Implement rate limiting
- Add data validation and sanitization