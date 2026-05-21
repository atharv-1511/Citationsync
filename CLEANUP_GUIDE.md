# Files to Delete - Cloud Migration Cleanup

This document lists unnecessary files that can be deleted after AWS migration.

## 🗑️ Files Safe to Delete

### 1. **Documentation Files** (Development artifacts - no longer needed)
- ❌ `FINAL_CHECKLIST.md` - Development checklist, outdated
- ❌ `PROJECT_INDEX.md` - Old project index, replaced by README.md
- ✅ Keep `README.md` - Main documentation
- ✅ Keep `TEAM_GUIDE.md` - Team instructions
- ✅ Keep `AWS_S3_SETUP.md` - AWS setup guide

### 2. **Local Data** (Now in AWS S3 & RDS)
- ❌ `Data/` folder - All files now in S3
  - `Data/Backlink_Directories.xlsx` → S3
  - `Data/Cafe_Clients_Backlinks.xlsx` → S3

### 3. **Old Database** (Migrated to AWS RDS)
- ❌ `database/backlinks.db` - Old SQLite file

### 4. **Cache Folders** (Automatically regenerated)
- ❌ `__pycache__/` - Python cache (auto-generated)

### 5. **Optional Development Files**
- ❌ `.env` - If using environment variables instead

## ✅ Files to Keep

### Core Application
- ✅ `app.py` - Main Flask application
- ✅ `config.py` - Configuration
- ✅ `models.py` - Database models
- ✅ `aws_storage.py` - S3 operations
- ✅ `requirements.txt` - Dependencies

### Templates & Static Assets
- ✅ `templates/` - All HTML templates
- ✅ `static/` - CSS, JavaScript

### Scripts
- ✅ `scripts/import_data.py` - Data import (now uses S3)
- ✅ `scripts/setup_s3.py` - S3 setup helper
- ✅ `scripts/cleanup.py` - Cleanup utility

### Documentation
- ✅ `README.md` - Main docs
- ✅ `SETUP.md` - Setup guide
- ✅ `TEAM_GUIDE.md` - Team instructions
- ✅ `AWS_S3_SETUP.md` - AWS guide

### Virtual Environment
- ✅ `venv/` - Keep (contains all dependencies)

---

## 🧹 Quick Cleanup Commands

```powershell
# 1. Delete documentation files
Remove-Item -Path "FINAL_CHECKLIST.md"
Remove-Item -Path "PROJECT_INDEX.md"

# 2. Delete local data (after confirming in S3)
Remove-Item -Path "Data" -Recurse

# 3. Delete old database
Remove-Item -Path "database\backlinks.db"

# 4. Delete Python cache
Remove-Item -Path "__pycache__" -Recurse -Force
Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force

# 5. (Alternative) Run the cleanup script
python scripts/cleanup.py
```

## 📊 Before & After Disk Space

### ❌ Before (With Local Data)
```
AI LB Prototype/
├── Data/
│   ├── Backlink_Directories.xlsx (~50 KB)
│   └── Cafe_Clients_Backlinks.xlsx (~25 KB)
├── database/
│   └── backlinks.db (~1-5 MB)
├── FINAL_CHECKLIST.md
├── PROJECT_INDEX.md
└── (other files)

Total: ~6-20 MB locally
```

### ✅ After (Cloud-Based)
```
AI LB Prototype/
├── app.py
├── config.py
├── models.py
├── aws_storage.py
├── requirements.txt
├── templates/
├── static/
├── scripts/
├── README.md
├── SETUP.md
├── TEAM_GUIDE.md
├── AWS_S3_SETUP.md
└── venv/

Total: ~1-2 MB locally (no data!)
Data is in: AWS S3 ✅
Database is in: AWS RDS ✅
```

---

**Ready to clean up?** Run `python scripts/cleanup.py`
