USE mysql;
UPDATE user SET Host='%' WHERE User='root';
FLUSH PRIVILEGES;