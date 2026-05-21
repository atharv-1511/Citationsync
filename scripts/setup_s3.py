"""
Setup script to initialize AWS S3 storage and upload data files
Run this once to migrate your data to the cloud
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aws_storage import S3Storage


def setup_s3():
    """Initialize S3 bucket and upload data files"""
    
    # Check for AWS credentials
    if not os.getenv('AWS_ACCESS_KEY_ID') or not os.getenv('AWS_SECRET_ACCESS_KEY'):
        print("❌ Error: AWS credentials not found!")
        print("\nSet these environment variables before running:")
        print("  $env:AWS_ACCESS_KEY_ID='your-access-key'")
        print("  $env:AWS_SECRET_ACCESS_KEY='your-secret-key'")
        print("  $env:AWS_S3_BUCKET='your-bucket-name'")
        print("  $env:AWS_REGION='us-east-1'")
        return False
    
    print("🔄 Initializing S3 storage...")
    storage = S3Storage()
    
    # Create bucket
    print("\n1️⃣ Creating S3 bucket...")
    if not storage.create_bucket():
        print("❌ Failed to create bucket")
        return False
    
    # Upload data files
    print("\n2️⃣ Uploading data files to S3...")
    
    local_files = [
        (
            os.path.join(PROJECT_ROOT, 'Data', 'Backlink_Directories.xlsx'),
            'data/Backlink_Directories.xlsx'
        ),
        (
            os.path.join(PROJECT_ROOT, 'Data', 'Cafe_Clients_Backlinks.xlsx'),
            'data/Cafe_Clients_Backlinks.xlsx'
        ),
    ]
    
    uploaded = 0
    for local_path, s3_key in local_files:
        if os.path.exists(local_path):
            if storage.upload_file(local_path, s3_key):
                uploaded += 1
        else:
            print(f"  ⚠️ File not found: {local_path}")
    
    print(f"\n✅ Successfully uploaded {uploaded} files to S3!")
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("1. Run the data import script:")
    print("   python scripts/import_data.py")
    print("\n2. After confirming data is imported, delete local Data folder:")
    print("   Remove-Item -Path '.\\Data' -Recurse")
    print("="*60)
    
    return True


if __name__ == '__main__':
    setup_s3()
