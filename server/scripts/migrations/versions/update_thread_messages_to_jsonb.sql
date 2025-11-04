-- Migration: Update thread_messages content to JSONB
-- Description: Converts the content column in thread_messages from TEXT to JSONB
-- Author: System
-- Date: 2024-03-14

-- First, create a backup of the existing messages
CREATE TABLE thread_messages_backup AS 
SELECT * FROM thread_messages;

-- Add a new JSONB column
ALTER TABLE thread_messages 
ADD COLUMN content_jsonb JSONB;

-- Convert existing TEXT content to JSONB format
UPDATE thread_messages 
SET content_jsonb = jsonb_build_object(
    'text', content,
    'type', 'text',
    'metadata', jsonb_build_object(
        'migrated_at', CURRENT_TIMESTAMP,
        'original_format', 'text'
    )
);

-- Drop the old TEXT column
ALTER TABLE thread_messages 
DROP COLUMN content;

-- Rename the new column to content
ALTER TABLE thread_messages 
RENAME COLUMN content_jsonb TO content;

-- Add NOT NULL constraint to the new content column
ALTER TABLE thread_messages 
ALTER COLUMN content SET NOT NULL;

-- Create an index on the content column for better query performance
CREATE INDEX idx_thread_messages_content ON thread_messages USING gin (content);

-- Add a comment to the table explaining the change
COMMENT ON TABLE thread_messages IS 'Thread messages with JSONB content format. Content structure: {text: string, type: string, metadata: object}';

-- Add a comment to the content column
COMMENT ON COLUMN thread_messages.content IS 'JSONB field containing message content with structure: {text: string, type: string, metadata: object}';

-- Create a rollback function in case we need to revert
CREATE OR REPLACE FUNCTION rollback_thread_messages_content()
RETURNS void AS $$
BEGIN
    -- Restore from backup
    DROP TABLE IF EXISTS thread_messages;
    CREATE TABLE thread_messages AS 
    SELECT id, thread_id, user_id, 
           (content->>'text')::TEXT as content,
           created_at, updated_at
    FROM thread_messages_backup;
    
    -- Restore constraints and indexes
    ALTER TABLE thread_messages 
    ADD PRIMARY KEY (id),
    ADD CONSTRAINT fk_thread_messages_thread 
        FOREIGN KEY (thread_id) 
        REFERENCES threads(id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_thread_messages_user 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE CASCADE;
    
    CREATE INDEX idx_thread_messages_thread_id ON thread_messages(thread_id);
    CREATE INDEX idx_thread_messages_user_id ON thread_messages(user_id);
END;
$$ LANGUAGE plpgsql;

-- Add a comment explaining the rollback function
COMMENT ON FUNCTION rollback_thread_messages_content() IS 'Function to rollback the thread_messages content column from JSONB back to TEXT format';

-- Verify the migration
DO $$
BEGIN
    -- Check if all messages were migrated successfully
    IF EXISTS (
        SELECT 1 FROM thread_messages 
        WHERE content IS NULL 
        OR NOT jsonb_typeof(content) = 'object'
        OR NOT content ? 'text'
        OR NOT content ? 'type'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: Some messages were not properly migrated';
    END IF;
    
    -- Check if the backup was created
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'thread_messages_backup'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: Backup table was not created';
    END IF;
    
    RAISE NOTICE 'Migration verification passed successfully';
END $$;

-- Example: Assign 'admin' role to admin@example.com, 'authenticated_user' to others
INSERT INTO user_roles (user_id, role_id, role_name, role_type, object_id, object_type, created_at, updated_at)
SELECT
  'd27ee9a4-4ebf-4f55-9ed5-0c5cb0ba2a94',
  r.id,
  r.name,
  r.role_type,
  NULL,
  NULL,
  NOW(),
  NOW()
FROM roles r WHERE r.name = 'admin'
UNION ALL
SELECT
  '894ff027-f47d-471b-b4d6-b2454b0ca580',
  r.id,
  r.name,
  r.role_type,
  NULL,
  NULL,
  NOW(),
  NOW()
FROM roles r WHERE r.name = 'authenticated_user'
UNION ALL
SELECT
  '00000000-0000-0000-0000-000000000000',
  r.id,
  r.name,
  r.role_type,
  NULL,
  NULL,
  NOW(),
  NOW()
FROM roles r WHERE r.name = 'system_admin'
UNION ALL
SELECT
  'a26ea6c0-4396-4b36-8244-24fef0195599',
  r.id,
  r.name,
  r.role_type,
  NULL,
  NULL,
  NOW(),
  NOW()
FROM roles r WHERE r.name = 'authenticated_user'
UNION ALL
SELECT
  '8ab32736-f121-4695-a323-a2dcd38519f0',
  r.id,
  r.name,
  r.role_type,
  NULL,
  NULL,
  NOW(),
  NOW()
FROM roles r WHERE r.name = 'authenticated_user'
UNION ALL
SELECT
  '60f51092-f34a-46c2-afe5-2eec647e7b43',
  r.id,
  r.name,
  r.role_type,
  NULL,
  NULL,
  NOW(),
  NOW()
FROM roles r WHERE r.name = 'authenticated_user'
UNION ALL
SELECT
  '3dd1ad55-98ae-4e94-b9f6-6088573349be',
  r.id,
  r.name,
  r.role_type,
  NULL,
  NULL,
  NOW(),
  NOW()
FROM roles r WHERE r.name = 'authenticated_user'; 