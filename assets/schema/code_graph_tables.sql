-- Code Graph Tables
-- Run this script to create the code graph persistence tables
-- Supports MySQL/SQLite (DB-GPT uses SQLAlchemy, so these are auto-created by ORM models)

-- ============================================================================
-- Table: code_graph_vertex
-- Stores AST-extracted code nodes (classes, functions, modules, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS code_graph_vertex (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id VARCHAR(100) NOT NULL,
    vid VARCHAR(500) NOT NULL,
    name VARCHAR(500) NOT NULL,
    node_type VARCHAR(50) NOT NULL DEFAULT '',
    source_file VARCHAR(500) DEFAULT '',
    language VARCHAR(30) DEFAULT '',
    community VARCHAR(50) DEFAULT '',
    props TEXT,
    gmt_create TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gmt_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_id, vid)
);
CREATE INDEX IF NOT EXISTS idx_cgv_knowledge_id ON code_graph_vertex (knowledge_id);
CREATE INDEX IF NOT EXISTS idx_cgv_name ON code_graph_vertex (name);
CREATE INDEX IF NOT EXISTS idx_cgv_node_type ON code_graph_vertex (node_type);
CREATE INDEX IF NOT EXISTS idx_cgv_source_file ON code_graph_vertex (source_file);

-- ============================================================================
-- Table: code_graph_edge
-- Stores structural relationships (contains, calls, imports, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS code_graph_edge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id VARCHAR(100) NOT NULL,
    sid VARCHAR(500) NOT NULL,
    tid VARCHAR(500) NOT NULL,
    edge_type VARCHAR(50) NOT NULL DEFAULT 'references',
    confidence VARCHAR(20) DEFAULT 'EXTRACTED',
    source_file VARCHAR(500) DEFAULT '',
    source_location VARCHAR(30) DEFAULT '',
    props TEXT,
    gmt_create TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gmt_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_id, sid, tid, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_cge_knowledge_id ON code_graph_edge (knowledge_id);
CREATE INDEX IF NOT EXISTS idx_cge_sid ON code_graph_edge (sid);
CREATE INDEX IF NOT EXISTS idx_cge_tid ON code_graph_edge (tid);
CREATE INDEX IF NOT EXISTS idx_cge_edge_type ON code_graph_edge (edge_type);

-- ============================================================================
-- Table: code_graph_meta
-- Stores per-knowledge-space graph metadata (counts, build info)
-- ============================================================================
CREATE TABLE IF NOT EXISTS code_graph_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id VARCHAR(100) NOT NULL UNIQUE,
    vertex_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0,
    community_count INTEGER DEFAULT 0,
    build_source VARCHAR(20) DEFAULT '',
    repo_url VARCHAR(500) DEFAULT '',
    branch VARCHAR(100) DEFAULT '',
    build_status VARCHAR(20) DEFAULT 'completed',
    graph_version INTEGER DEFAULT 1,
    gmt_create TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gmt_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cgm_knowledge_id ON code_graph_meta (knowledge_id);
