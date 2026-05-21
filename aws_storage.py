"""
AWS S3 Storage utility for managing data files in the cloud
"""
import os
import boto3
import io
import pandas as pd
from botocore.exceptions import ClientError


class S3Storage:
    """Handle file operations with AWS S3"""
    
    def __init__(self):
        self.bucket_name = os.getenv('AWS_S3_BUCKET', 'citation-manager-data')
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
    
    def upload_file(self, file_path, s3_key):
        """Upload a local file to S3"""
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            print(f"✓ Uploaded {file_path} to s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            print(f"✗ Error uploading file: {e}")
            return False
    
    def download_file(self, s3_key, file_path):
        """Download a file from S3 to local storage"""
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, file_path)
            print(f"✓ Downloaded s3://{self.bucket_name}/{s3_key} to {file_path}")
            return True
        except ClientError as e:
            print(f"✗ Error downloading file: {e}")
            return False
    
    def read_excel(self, s3_key, sheet_name=None):
        """Read Excel file directly from S3"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            df = pd.read_excel(io.BytesIO(response['Body'].read()), sheet_name=sheet_name)
            print(f"✓ Read {s3_key} from S3")
            return df
        except ClientError as e:
            print(f"✗ Error reading file from S3: {e}")
            return None
    
    def list_files(self, prefix=''):
        """List all files in S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            files = [obj['Key'] for obj in response.get('Contents', [])]
            return files
        except ClientError as e:
            print(f"✗ Error listing files: {e}")
            return []
    
    def delete_file(self, s3_key):
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            print(f"✓ Deleted s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            print(f"✗ Error deleting file: {e}")
            return False
    
    def create_bucket(self):
        """Create S3 bucket if it doesn't exist"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"✓ Bucket {self.bucket_name} already exists")
            return True
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                print(f"✓ Created bucket {self.bucket_name}")
                return True
            except ClientError as e:
                print(f"✗ Error creating bucket: {e}")
                return False
