CREATE TABLE thread (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE thread_message (
    id SERIAL PRIMARY KEY,
    thread_id INT NOT NULL REFERENCES thread(id) ON DELETE CASCADE,
    message_id VARCHAR(255) NULL,
    message_type VARCHAR(255) NOT NULL,
    message_content JSONB,
    message_extra JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
