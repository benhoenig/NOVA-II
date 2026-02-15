-- CLEAN START: Remove existing tables if they already exist
DROP TABLE IF EXISTS chat_history CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS business_portfolio CASCADE;
DROP TABLE IF EXISTS lessons_learned CASCADE;
DROP TABLE IF EXISTS knowledge_base CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS goals CASCADE;

-- Create goals table
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    start_date DATE,
    due_date DATE,
    status TEXT DEFAULT 'Active',
    priority TEXT DEFAULT 'Medium',
    reminder_schedule TEXT,
    last_reminded TIMESTAMPTZ,
    progress_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Create tasks (action plans) table
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    plan_id TEXT, -- Matches PLAN-XXX from sheet
    goal_id TEXT REFERENCES goals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    timeline TEXT,
    status TEXT DEFAULT 'Todo',
    due_date DATE,
    completed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create knowledge_base (Notes) table
CREATE TABLE IF NOT EXISTS knowledge_base (
    id TEXT PRIMARY KEY, -- Matches NOTE-XXX from sheet
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    tags TEXT[],
    source_reference TEXT,
    goal_id TEXT REFERENCES goals(id) ON DELETE SET NULL,
    business_id TEXT, -- Will link to business_portfolio(id) after it's defined
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create business_portfolio table
CREATE TABLE IF NOT EXISTS business_portfolio (
    id TEXT PRIMARY KEY, -- Matches BUS-XXX
    name TEXT NOT NULL,
    description TEXT,
    status TEXT,
    business_model TEXT,
    target_customer TEXT,
    revenue_model TEXT,
    current_stage TEXT,
    monthly_revenue NUMERIC,
    customer_count INTEGER,
    key_metrics TEXT,
    pain_points TEXT,
    next_steps TEXT,
    related_goals TEXT, -- Can contain goal IDs
    notes TEXT,
    started_date DATE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add missing FK to knowledge_base now that business_portfolio exists
ALTER TABLE knowledge_base ADD CONSTRAINT fk_kb_business FOREIGN KEY (business_id) REFERENCES business_portfolio(id) ON DELETE SET NULL;

-- Create customers table
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY, -- Matches CONTACT-XXX
    name TEXT NOT NULL,
    contact_type TEXT,
    company TEXT,
    contact_info TEXT,
    notes TEXT,
    last_contact DATE,
    tags TEXT[],
    business_id TEXT REFERENCES business_portfolio(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create lessons_learned table
CREATE TABLE IF NOT EXISTS lessons_learned (
    id TEXT PRIMARY KEY, -- Matches LESSON-XXX
    title TEXT NOT NULL,
    what_happened TEXT,
    what_i_learned TEXT,
    how_to_apply TEXT,
    category TEXT,
    lesson_date DATE,
    goal_id TEXT REFERENCES goals(id) ON DELETE SET NULL,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    business_id TEXT REFERENCES business_portfolio(id) ON DELETE SET NULL,
    customer_id TEXT REFERENCES customers(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create chat_history table for long-term memory
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user' or 'assistant'
    message TEXT NOT NULL,
    intent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Note: Run this manually in Supabase SQL Editor if not using migration tool
CREATE TABLE IF NOT EXISTS history_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
