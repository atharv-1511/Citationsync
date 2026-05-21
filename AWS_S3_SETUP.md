# AWS S3 Data Storage Setup Guide

Your Citation Manager is now using **AWS S3** for data storage instead of keeping files locally.

## ✅ What's Already Done:
- ✅ Updated `requirements.txt` with boto3 (AWS SDK)
- ✅ Created `aws_storage.py` module for S3 operations
- ✅ Updated `scripts/import_data.py` to read from S3
- ✅ Created setup and cleanup scripts

## 🚀 Quick Setup (3 Steps)

### Step 1: Get AWS Credentials

Go to **AWS Console** → **IAM** → **Users** → Create a user with:
- **Access Type:** Programmatic access
- **Permissions:** `AmazonS3FullAccess`
- **Download:** Access Key ID + Secret Access Key

### Step 2: Set Environment Variables (PowerShell)

```powershell
# Set AWS credentials
$env:AWS_ACCESS_KEY_ID="your-access-key-id"
$env:AWS_SECRET_ACCESS_KEY="your-secret-access-key"
$env:AWS_S3_BUCKET="citation-manager-data"  # Change if needed
$env:AWS_REGION="us-east-1"  # Change if needed
```

### Step 3: Run S3 Setup Script

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Run setup
python scripts/setup_s3.py
```

This will:
1. ✅ Create S3 bucket (if not exists)
2. ✅ Upload your Excel files to S3
3. ✅ Show you next steps

## 📊 After S3 Setup: Import Data to RDS

```powershell
# Set database credentials
$env:DATABASE_URL="postgresql+psycopg2://postgres:Grayrock04@database-citation-manager.civiomcuskqf.us-east-1.rds.amazonaws.com:5432/citations"

# Import data from S3 to RDS
python scripts/import_data.py
```

## 🗑️ Cleanup: Remove Local Files

Once you've confirmed:
- ✅ Files uploaded to S3
- ✅ Data imported to RDS

Run cleanup to remove local data:

```powershell
python scripts/cleanup.py
```

This removes:
- ❌ `Data/` folder
- ❌ `database/backlinks.db` (old SQLite file)

## 📋 Final Architecture

```
Your Device
    ↓
Flask App (localhost:5000)
    ↓
AWS RDS PostgreSQL (database-citation-manager.civiomcuskqf.us-east-1.rds.amazonaws.com)
AWS S3 (citation-manager-data bucket)
```

## 🔧 Environment Variables Summary

Add these to your `.env` file or set as system variables:

```bash
# Database (AWS RDS)
DATABASE_URL=postgresql+psycopg2://postgres:Grayrock04@database-citation-manager.civiomcuskqf.us-east-1.rds.amazonaws.com:5432/citations
SECRET_KEY=ai-lab-citation-manager-prod-key-2026

# Admin Account
ADMIN_EMAIL=raskaratharv28@gmail.com
ADMIN_PASSWORD=Grayrock@04
ADMIN_FULL_NAME=Atharv Raskar

# AWS S3
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_S3_BUCKET=citation-manager-data
AWS_REGION=us-east-1
```

## ✅ Verification Checklist

After setup, verify:

```powershell
# 1. Test S3 connection (should list your files)
python -c "from aws_storage import S3Storage; s = S3Storage(); print(s.list_files('data/'))"

# 2. Test RDS connection (should import data)
python scripts/import_data.py

# 3. Start app and verify
python app.py
```

## 🆘 Troubleshooting

**Problem:** "ModuleNotFoundError: No module named 'boto3'"
- **Solution:** `pip install -r requirements.txt`

**Problem:** "Unauthorized: An error occurred (InvalidAccessKeyId) when calling..."
- **Solution:** Check AWS credentials are correct

**Problem:** "NoSuchBucket: The specified bucket does not exist"
- **Solution:** Make sure bucket name matches `AWS_S3_BUCKET` env var

**Problem:** "Signature does not match"
- **Solution:** Check Secret Access Key is correct (no extra spaces)

## 📚 File Structure After Migration

```
AI LB Prototype/
├── app.py
├── config.py
├── models.py
├── aws_storage.py          ← NEW: S3 operations
├── requirements.txt
├── templates/
├── static/
├── scripts/
│   ├── import_data.py      ← UPDATED: reads from S3
│   ├── setup_s3.py         ← NEW: S3 setup
│   └── cleanup.py          ← NEW: removes local files
├── database/
│   └── (minimal, only for dev fallback)
├── Data/                   ← DELETE AFTER S3 SETUP
│   ├── Backlink_Directories.xlsx   (will be in S3)
│   └── Cafe_Clients_Backlinks.xlsx (will be in S3)
└── AWS_S3_SETUP.md         ← THIS FILE
```

---

**Questions?** Check the main README.md or SETUP.md
