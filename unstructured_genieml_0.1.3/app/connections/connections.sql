-- enable uuid generator
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- drop & recreate table for clarity (or use ALTER TABLE on existing)
DROP TABLE IF EXISTS connections;
DROP TABLE IF EXISTS data_sources;

CREATE TABLE data_sources (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  connector_name TEXT NOT NULL,
  connector_type TEXT NOT NULL,
  description TEXT,
  config JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE connections (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  description TEXT,
  settings JSONB NOT NULL,
  source_id TEXT,
  user_id TEXT,
  role TEXT,
  version TEXT NOT NULL DEFAULT '1.0',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- seed connector configs
INSERT INTO data_sources (connector_name, connector_type, description, config) VALUES
-- 1) Google Drive PDFs
(
  'Google Drive PDFs',
  'google-drive',
  'Airbyte source for ingesting PDF files from Google Drive',
  '{
    "sourceType": "google-drive",
    "streams": [
      {
        "name": "pdfs",
        "globs": ["*.pdf"],
        "format": {
          "filetype": "unstructured",
          "processing": { "mode": "local" }
        }
      }
    ],
    "folder_url": "https://example.com",
    "credentials": {
      "auth_type": "Service",
      "service_account_info": "The JSON key of the service account to use for authorization."
    }
  }'::jsonb
),
-- 2) S3 JSONL Source
(
  'S3 JSONL Source',
  's3',
  'Airbyte source for JSONL files from an S3 bucket',
  '{
    "sourceType": "s3",
    "streams": [
      {
        "name": "name",
        "format": { "filetype": "jsonl" }
      }
    ],
    "bucket": "s3-bucket-name",
    "aws_access_key_id": "1234",
    "aws_secret_access_key": "123",
    "role_arn": "123",
    "endpoint": "my-s3-endpoint.com",
    "region_name": "us-east-1"
  }'::jsonb
),
-- 3) Gong Calls Source
(
  'Gong Calls Source',
  'gong',
  'Airbyte source for ingesting Gong call data',
  '{
    "sourceType": "gong",
    "gong_access_key": "YOUR_KEY",
    "gong_access_key_secret": "YOUR_SECRET",
    "start_date": "2021-01-01T00:00:00Z"
  }'::jsonb
),
-- 4) Salesforce Source
(
  'Salesforce Source',
  'salesforce',
  'Airbyte source for Salesforce data streams',
  '{
    "sourceType": "salesforce",
    "client_id": "client id string",
    "client_secret": "silent secret 123",
    "refresh_token": "refresh token 123",
    "start_date": "2021-07-25",
    "streams_criteria": [
      { "value": "filter value" }
    ]
  }'::jsonb
);