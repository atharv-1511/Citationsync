# Link Building Citation Manager

A web-based platform to manage backlink citations for multiple dealers, preventing duplicate citations within 6 months and tracking citation history.

## Problem Statement
- 5,000+ clients (35+ active dealers in prototype)
- 60 backlink directories available
- 2 citations required per dealer per month
- Citations can't repeat within 6 months
- Currently tracking citations manually in Excel sheets across 8 files
- Time-consuming to find dealers and track citation status

## Solution
A centralized platform with:
- **Database Backend**: PostgreSQL on Supabase for storing dealer data and citation history
- **REST API**: Flask-based API for querying and updating citation data
- **Web UI**: Simple interface to look up dealers and record citations
- **Smart Logic**: Automatically suggest available citations based on:
  - Citations already built for the dealer
  - 6-month recency rule
  - Random selection from available pool

## Project Structure
```
AI LB Prototype/
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── app.py                    # Main Flask application
├── config.py                 # Configuration settings
├── models.py                 # Database models
├── database/                 # Database files
│   └── backlinks.db         # SQLite database
├── data/                     # Input Excel files
│   ├── Backlink_Directories.xlsx
│   └── Cafe_Clients_Backlinks.xlsx
├── templates/                # HTML templates
│   ├── base.html
│   ├── dealer_lookup.html
│   └── add_citation.html
├── static/                   # CSS/JS
│   └── style.css
└── scripts/                  # Utility scripts
    └── import_data.py       # Import Excel data to DB
```

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Supabase and Import Data from Excel

Set `DATABASE_URL` to your Supabase Postgres connection string. The app automatically adds `sslmode=require` for Supabase hosts.

```bash
python scripts/import_data.py
```

This will:
- Read `Data/Backlink_Directories.xlsx` and populate available citations
- Read `Data/Cafe_Clients_Backlinks.xlsx` and populate dealer data with history

### 3. Run the Application
```bash
python app.py
```

Access at `http://localhost:5000`

## Features

### 1. **Dealer Lookup**
- Input dealer ID (e.g., 20000)
- View dealer name and contact info
- See all citations already built
- Get suggestions for next 2 citations to build

### 2. **Add Citation**
- Input dealer ID and citation name
- System records timestamp
- Citation won't be suggested for this dealer for 6 months
- Web UI updates immediately

### 3. **Suggested Citations**
- Excludes citations built in last 6 months
- Randomly selects from available pool
- Ensures fair distribution across directories

### 4. **Reporting**
- Export citation history per dealer
- Track citation completion rate
- Identify dealers needing citations

## Database Schema

### Tables
- **dealers**: Dealer ID, Name, Contact Info
- **backlink_directories**: All 60+ available directories
- **citations**: Links dealers to citations with timestamps
- **citation_history**: 6-month history for recency checking

## API Endpoints

### GET /api/dealer/{dealer_id}
Returns dealer info and citation history

### GET /api/dealer/{dealer_id}/suggestions
Returns 2 random citations available for the dealer

### POST /api/citation/add
Adds a new citation record for a dealer

### GET /api/citations/export
Exports citation data to Excel

## Next Steps
1. Install dependencies
2. Run `python scripts/import_data.py`
3. Launch `python app.py`
4. Test with dealer ID 20000 (Brew Haven Cafe)
