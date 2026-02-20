-- Initialize two databases and a dedicated user for the project
CREATE DATABASE nfse_prod;
CREATE DATABASE nfse_dev;

-- Create a project user and grant privileges
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'nfse_user') THEN
      CREATE ROLE nfse_user WITH LOGIN PASSWORD 'L@ise1301';
   END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE nfse_prod TO nfse_user;
GRANT ALL PRIVILEGES ON DATABASE nfse_dev TO nfse_user;
