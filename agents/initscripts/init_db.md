How to Set Up the Team Collaboration Database with OAuth Support
I've created three key files to help you set up your database with all the necessary tables for your team collaboration system with OAuth integration:

schema.sql - Contains all the SQL statements to create the required tables, indexes, and default data for your system.
db_setup.py - A Python script that reads environment variables and executes the SQL schema to set up your database.
.env.template - A template for your environment variables file with all the necessary configuration options.

Usage Instructions

First, copy the environment template:
cp .env.template .env

Edit the .env file with your database credentials and other configuration options:
# Edit your database connection details
nano .env

Run the database setup script:
python db_setup.py --env-file=.env --schema-file=schema.sql --create-db
The --create-db flag will create the database if it doesn't exist yet. If you're using an existing database, you can omit this flag.

What the Script Does

Reads environment variables from your .env file
Connects to your PostgreSQL server
Creates the database if it doesn't exist (when using --create-db)
Creates all the tables defined in schema.sql, including:

User management tables
Role and permission tables
Team management tables
Session collaboration tables
OAuth integration tables


Sets up indexes for optimized queries
Adds default roles to the system

Key Database Tables

User Management:

collaboration_users: Stores user accounts
user_roles: Maps users to roles


Role Management:

roles: Defines available roles and their permissions


Team Management:

teams: Stores team information
team_members: Maps users to teams
team_member_roles: Assigns roles within teams


Session Collaboration:

sessions: Stores chat sessions
session_shares: Manages shared sessions
session_comments: Stores comments on sessions


OAuth Integration:

oauth_provider_configs: Stores OAuth provider configurations
oauth_connections: Links users to external identities
oauth_role_sync_settings: Configures role synchronization



This setup provides a complete database foundation for your team collaboration system with OAuth-based authentication and role synchronization.