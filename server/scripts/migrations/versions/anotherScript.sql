ALTER TABLE teams
ADD COLUMN description TEXT DEFAULT 'No description provided';

ALTER TABLE user_tokens ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE user_tokens ADD COLUMN last_used_at TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE user_tokens ADD COLUMN device_info VARCHAR(255) NULL;
ALTER TABLE user_tokens ADD COLUMN ip_address VARCHAR(255) NULL;
ALTER TABLE user_tokens ALTER COLUMN token_type SET DEFAULT 'access';
ALTER TABLE user_tokens ALTER COLUMN is_revoked SET DEFAULT false;
ALTER TABLE user_tokens ALTER COLUMN is_active SET DEFAULT true;
alter table teams add column description VARCHAR(255) default '';


UPDATE threads
SET description = 'No description provided'
WHERE description IS NULL;

ALTER TABLE workspaces ADD COLUMN created_by VARCHAR(255) default '';

alter table thread_messages add column response VARCHAR(max) default '';

alter table thread_messages add column status VARCHAR(255) default '';

alter table thread_messages add column timestamp TIMESTAMP WITH TIME ZONE NULL;