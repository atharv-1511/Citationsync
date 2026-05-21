# Installation & Setup Guide

## 📋 Prerequisites
- Python 3.8+ installed
- Windows OS (or adapt commands for your OS)

## 🌐 Online Database + Sign In

This version runs on Supabase PostgreSQL instead of local SQLite.

### Supabase Setup (Production)

Set these environment variables before deploying:

```bash
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_SUPABASE_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres?sslmode=require
SECRET_KEY=your-secret-key-here-change-this
ADMIN_EMAIL=raskaratharv28@gmail.com
ADMIN_PASSWORD=Grayrock@04
ADMIN_FULL_NAME=Atharv Raskar
DEFAULT_USER_PASSWORD=choose-a-default-temp-password
```

The admin account is seeded automatically from `ADMIN_EMAIL` and `ADMIN_PASSWORD`. That user can add new directories. 

**Employee Management:** Employees are managed through your organization's email system. When an employee with an organization email signs in, they are automatically created in the system on first login and appear as regular employees.

### Data Import (Local Excel Files)

Keep the Excel files in the local `Data/` folder and run the import script:

```powershell
python scripts/import_data.py
```

After confirming the data is in Supabase, clean up the local files:

```powershell
python scripts/cleanup.py
```

## 🚀 Quick Start

### 1. Install Dependencies

Open PowerShell or Command Prompt in the project directory and run:

```bash
# Using pip directly
python -m pip install --upgrade pip

# Install requirements
python -m pip install -r requirements.txt
```

**If pip command fails**, try:
```bash
# Find python installation
where python
python -m pip install -r requirements.txt
```

### 2. Prepare Database & Import Data

```bash
# Navigate to project directory
cd "c:\Users\Atharv Raskar\Desktop\AI LB Prototype"

# Run the import script to populate database from Excel files
python scripts/import_data.py
```

**Expected Output:**
```
============================================================
Citation Building Management System - Data Import
============================================================

Initializing database...
✓ Database tables created

------------------------------------------------------------
Importing backlink directories...
✓ Imported 60 backlink directories
Importing dealers and citations...
✓ Imported 7 new dealers (Total: 7)
✓ Imported 35 new citations (Total: 35)
------------------------------------------------------------

✓ Data import completed successfully!

Database Summary:
  • Dealers: 7
  • Backlink Directories: 60
  • Citations Built: 35
============================================================
```

### 3. Run the Application

```bash
# Start the Flask development server
python app.py
```

### 4. Test the Database Connection

Open `http://localhost:5000/api/db-status` after starting the app. A healthy connection returns `ok: true` and `result: 1`.

### 5. Sign In

1. Open `http://localhost:5000/login`
2. Sign in with the admin email and password from your environment variables
3. Use the Admin page to add employees and new directories

**Expected Output:**
```
 * Running on http://127.0.0.1:5000
 * Press CTRL+C to quit
```

### 6. Access the Web Interface

Open your browser and visit: **http://localhost:5000**

## 📁 Project Structure

```
AI LB Prototype/
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── models.py                   # Database models
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── SETUP.md                    # This file
│
├── Data/                       # Input Excel files (source data)
│   ├── Backlink_Directories.xlsx
│   └── Cafe_Clients_Backlinks.xlsx
│
├── database/                   # Database storage
│   └── backlinks.db           # SQLite database (auto-created)
│
├── scripts/                    # Utility scripts
│   └── import_data.py         # Excel to database import script
│
├── templates/                  # HTML templates
│   ├── base.html              # Base template with navigation
│   ├── index.html             # Home page
│   ├── dealer_lookup.html     # Dealer search page
│   ├── add_citation.html      # Add citation form
│   └── dashboard.html         # Statistics dashboard
│
└── static/                     # Static assets
    └── script.js              # Common JavaScript utilities
```

## 🔧 Configuration

Edit `config.py` to change settings:

```python
CITATIONS_PER_DEALER_MONTHLY = 2      # Citations required per month
CITATION_RECENCY_MONTHS = 6           # Months to avoid repeating citations
SECRET_KEY = 'your-secret-key'        # Change this for production
ITEMS_PER_PAGE = 20                   # Items per page in pagination
```

## 📊 Features Implemented

✅ **Phase 1: Database & Models**
- Flask-SQLAlchemy models for Dealers, Directories, Citations
- Database initialization

✅ **Phase 2: Data Import**
- Import script to read Excel files
- Populate dealers, directories, and citation history
- Automatic timestamp assignment

✅ **Phase 3: REST API**
- `/api/dealer/<id>` - Get dealer info and history
- `/api/dealer/<id>/suggestions` - Get available citations (respects 6-month rule)
- `/api/citation/add` - Record new citation
- `/api/citations/stats` - Get overall statistics
- `/api/dealers` - List all dealers
- `/api/directories` - List all directories

✅ **Phase 4: Web UI**
- Home page with statistics
- Dealer lookup page
- Add citation form
- Dashboard with overview

## 🧪 Testing the System

### Test 1: Find a Dealer
1. Go to "Find Dealer" page
2. Enter dealer ID: **20000** (Brew Haven Cafe)
3. View their citations and get suggestions

### Test 2: Add a Citation
1. Go to "Add Citation" page
2. Enter dealer ID: **20000**
3. Select a suggested directory
4. Click "Add Citation"
5. Verify success message

### Test 3: Check Dashboard
1. Go to "Dashboard"
2. View statistics and dealers needing citations

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution:**
```bash
python -m pip install --upgrade pip setuptools
python -m pip install -r requirements.txt
```

### Issue: Database file not created
**Solution:**
```bash
# Ensure database directory exists
New-Item -ItemType Directory -Path "database" -Force

# Re-run import
python scripts/import_data.py
```

### Issue: Excel file not found during import
**Ensure files exist:**
- `Data/Backlink_Directories.xlsx`
- `Data/Cafe_Clients_Backlinks.xlsx`

### Issue: Port 5000 already in use
**Solution:**
```bash
# Change port in app.py, line at bottom:
app.run(debug=True, host='0.0.0.0', port=5001)  # Changed to 5001
```

## 📖 API Examples

### Get Dealer Information
```bash
curl http://localhost:5000/api/dealer/20000
```

### Get Suggestions for a Dealer
```bash
curl http://localhost:5000/api/dealer/20000/suggestions
```

### Add a Citation
```bash
curl -X POST http://localhost:5000/api/citation/add \
  -H "Content-Type: application/json" \
  -d '{
    "dealer_id": "20000",
    "directory_id": 1,
    "notes": "Citation added via API"
  }'
```

### Get Statistics
```bash
curl http://localhost:5000/api/citations/stats
```

## 🚀 Next Steps

1. **Test with sample data** - Use dealer IDs from the Excel file
2. **Deploy to team server** - Prepare for team access
3. **Add user authentication** - Secure the system (optional)
4. **Export features** - Add Excel export functionality
5. **Batch operations** - Add bulk citation import

## 📝 Notes

- All timestamps are stored in UTC
- The 6-month recency rule is calculated dynamically
- Citations can be added/edited via web UI or API
- Database is local SQLite (good for prototyping, consider PostgreSQL for production)

## 💡 Tips for Your Team

- **Bookmark the home page** - Quick access to statistics
- **Use dealer lookup** - Fastest way to find a specific dealer
- **Check dashboard regularly** - See which dealers need citations
- **Use suggested citations** - Algorithm ensures fair distribution

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review app logs in browser console (F12)
3. Check terminal output for Python errors
4. Verify database exists: `database/backlinks.db`

---

**Version:** 1.0  
**Last Updated:** 2026-05-20  
**Status:** Production Ready
