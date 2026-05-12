-- Migration 002: add s2_paper_id column for direct S2 citation API lookups
ALTER TABLE papers ADD COLUMN s2_paper_id TEXT;
CREATE INDEX IF NOT EXISTS idx_papers_s2_id ON papers(s2_paper_id);
