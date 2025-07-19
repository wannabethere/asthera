-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for Gong Transcripts
CREATE TABLE IF NOT EXISTS document_gong_transcript (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    document_name TEXT NOT NULL,
    document_content TEXT,
    title TEXT,
    date TEXT,
    participants TEXT[] DEFAULT ARRAY[]::TEXT[],
    duration TEXT,
    key_topics TEXT[] DEFAULT ARRAY[]::TEXT[],
    summary TEXT,
    action_items TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Table for Slack Conversations
CREATE TABLE IF NOT EXISTS document_slack_conversation (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    document_name TEXT NOT NULL,
    document_content TEXT,
    channel TEXT,
    date_range TEXT,
    participants TEXT[] DEFAULT ARRAY[]::TEXT[],
    key_topics TEXT[] DEFAULT ARRAY[]::TEXT[],
    summary TEXT,
    action_items TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Table for Contracts
CREATE TABLE IF NOT EXISTS document_contract (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    document_name TEXT NOT NULL,
    document_content TEXT,
    parties TEXT[] DEFAULT ARRAY[]::TEXT[],
    effective_date TEXT,
    term TEXT,
    key_clauses TEXT[] DEFAULT ARRAY[]::TEXT[],
    obligations TEXT[] DEFAULT ARRAY[]::TEXT[],
    termination_conditions TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Table for Generic Documents
CREATE TABLE IF NOT EXISTS document_generic (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    document_name TEXT NOT NULL,
    document_content TEXT,
    title TEXT,
    summary TEXT,
    keywords TEXT[] DEFAULT ARRAY[]::TEXT[]
);
