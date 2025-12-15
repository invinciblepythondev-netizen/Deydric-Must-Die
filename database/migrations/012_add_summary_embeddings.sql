-- Migration: Add embedding tracking to memory summaries
-- Allows memory summaries to be stored in Qdrant for semantic search

-- Add embedding tracking columns
ALTER TABLE memory.memory_summary
ADD COLUMN IF NOT EXISTS is_embedded BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS embedding_id TEXT,
ADD COLUMN IF NOT EXISTS embedding_version TEXT DEFAULT 'descriptive'; -- 'descriptive' or 'condensed' - which version was embedded

-- Add index for finding non-embedded summaries
CREATE INDEX IF NOT EXISTS idx_memory_summary_not_embedded
ON memory.memory_summary(is_embedded)
WHERE is_embedded = false;

-- Add index for embedding lookups
CREATE INDEX IF NOT EXISTS idx_memory_summary_embedding_id
ON memory.memory_summary(embedding_id)
WHERE embedding_id IS NOT NULL;

-- Update comments
COMMENT ON COLUMN memory.memory_summary.is_embedded IS 'Whether this summary has been embedded in the vector database';
COMMENT ON COLUMN memory.memory_summary.embedding_id IS 'ID of this summary in the vector database (Qdrant)';
COMMENT ON COLUMN memory.memory_summary.embedding_version IS 'Which version was embedded: descriptive (default) or condensed';
