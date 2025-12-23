-- Supabase Database Schema for Survey Portal
-- Run these commands in Supabase SQL Editor to create all tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Surveys Table
CREATE TABLE IF NOT EXISTS surveys (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'Draft',
    json_path TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'Enumerator',
    language TEXT DEFAULT 'en',
    contact TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Respondents Table
CREATE TABLE IF NOT EXISTS respondents (
    id BIGSERIAL PRIMARY KEY,
    survey_id BIGINT REFERENCES surveys(id) ON DELETE CASCADE,
    name TEXT,
    dob TEXT,
    gender TEXT,
    aadhaar_number TEXT UNIQUE,
    address TEXT,
    start_time TEXT,
    end_time TEXT,
    device_info TEXT,
    geo_latitude TEXT,
    geo_longitude TEXT,
    ip_address TEXT,
    ip_city TEXT,
    ip_country TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Answers Table
CREATE TABLE IF NOT EXISTS answers (
    id BIGSERIAL PRIMARY KEY,
    respondent_id BIGINT REFERENCES respondents(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_surveys_status ON surveys(status);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_respondents_survey_id ON respondents(survey_id);
CREATE INDEX IF NOT EXISTS idx_respondents_aadhaar ON respondents(aadhaar_number);
CREATE INDEX IF NOT EXISTS idx_answers_respondent_id ON answers(respondent_id);

-- Enable Row Level Security (RLS)
ALTER TABLE surveys ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE respondents ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;

-- Create policies for public access (adjust as needed for your security requirements)
CREATE POLICY "Enable read access for all users" ON surveys FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON surveys FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update access for all users" ON surveys FOR UPDATE USING (true);
CREATE POLICY "Enable delete access for all users" ON surveys FOR DELETE USING (true);

CREATE POLICY "Enable read access for all users" ON users FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON users FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update access for all users" ON users FOR UPDATE USING (true);
CREATE POLICY "Enable delete access for all users" ON users FOR DELETE USING (true);

CREATE POLICY "Enable read access for all users" ON respondents FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON respondents FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update access for all users" ON respondents FOR UPDATE USING (true);
CREATE POLICY "Enable delete access for all users" ON respondents FOR DELETE USING (true);

CREATE POLICY "Enable read access for all users" ON answers FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON answers FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update access for all users" ON answers FOR UPDATE USING (true);
CREATE POLICY "Enable delete access for all users" ON answers FOR DELETE USING (true);
