-- Database Schema for NewsCheck AI

-- Table to store source domains and their known credibility/bias scores
CREATE TABLE IF NOT EXISTS sources (
    domain TEXT PRIMARY KEY,
    credibility_score REAL NOT NULL, -- Value between 0.0 and 1.0
    bias_rating TEXT,                -- 'Left', 'Center-Left', 'Center', 'Center-Right', 'Right', etc.
    description TEXT
);

-- Table to store articles/text analysed by the users
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    url TEXT,                        -- NULL if text input
    title TEXT,
    content TEXT,
    summary TEXT,
    verdict TEXT,                    -- 'TRUE', 'LIKELY TRUE', 'MISLEADING', 'UNVERIFIED', 'LIKELY FALSE', 'FALSE'
    credibility_score INTEGER,       -- 0 to 100
    bias_rating TEXT,                -- 'Left', 'Center', 'Right', 'Objective' etc.
    tone_rating TEXT,                -- 'Neutral', 'Sensational', 'Fear-inducing'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table to store individual claims extracted from the article/text
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    verdict TEXT,                    -- 'TRUE', 'LIKELY TRUE', 'MISLEADING', 'UNVERIFIED', 'LIKELY FALSE', 'FALSE'
    explanation TEXT,
    FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
);

-- Table to store gathered evidence for claims
CREATE TABLE IF NOT EXISTS evidences (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    source_domain TEXT,
    source_url TEXT,
    source_title TEXT,
    snippet TEXT,
    type TEXT,                       -- 'SUPPORTING', 'CONTRADICTING', 'NEUTRAL'
    relevance_score REAL,            -- FAISS similarity score or semantic similarity
    FOREIGN KEY(claim_id) REFERENCES claims(id) ON DELETE CASCADE,
    FOREIGN KEY(source_domain) REFERENCES sources(domain)
);

-- Cache table to store search and LLM results
CREATE TABLE IF NOT EXISTS cache (
    cache_key TEXT PRIMARY KEY,
    cache_value TEXT NOT NULL,
    expiry_time TIMESTAMP NOT NULL
);

-- Insert default trusted and known source profiles
INSERT OR REPLACE INTO sources (domain, credibility_score, bias_rating, description) VALUES
('apnews.com', 0.95, 'Center', 'Associated Press - highly reliable, neutral wire service'),
('reuters.com', 0.95, 'Center', 'Reuters - highly reliable, neutral wire service'),
('bbc.co.uk', 0.90, 'Center', 'British Broadcasting Corporation - high reliability, slight left-center bias'),
('bbc.com', 0.90, 'Center', 'British Broadcasting Corporation - high reliability, slight left-center bias'),
('nytimes.com', 0.85, 'Center-Left', 'The New York Times - high reliability, left-center bias'),
('washingtonpost.com', 0.85, 'Center-Left', 'The Washington Post - high reliability, left-center bias'),
('wsj.com', 0.88, 'Center-Right', 'The Wall Street Journal - high reliability, right-center bias'),
('snopes.com', 0.92, 'Center', 'Snopes - prominent independent fact-checking website'),
('factcheck.org', 0.94, 'Center', 'FactCheck.org - nonpartisan, nonprofit consumer advocate for voters'),
('politifact.com', 0.92, 'Center-Left', 'PolitiFact - Pulitzer Prize-winning fact-checking website');
