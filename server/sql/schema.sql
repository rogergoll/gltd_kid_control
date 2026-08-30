-- GLTD Kid Control — schema do banco (MariaDB)
-- Banco: gltd_kcontrol  |  Usuário: gltd_kcontrol_app@localhost

CREATE TABLE IF NOT EXISTS profiles (
  id VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  lan_ip VARCHAR(64) NOT NULL DEFAULT '',
  linux_user VARCHAR(64) NOT NULL DEFAULT '',
  allowed_browsers TEXT NOT NULL,
  block_lists TEXT NOT NULL,
  allow_lists TEXT NOT NULL,
  filters TEXT NOT NULL,
  client_token VARCHAR(128) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS history (
  id BIGINT NOT NULL AUTO_INCREMENT,
  profile_id VARCHAR(64) NOT NULL,
  channel_handle VARCHAR(128) NOT NULL DEFAULT '',
  channel_name VARCHAR(255) NOT NULL DEFAULT '',
  video_title TEXT,
  video_url TEXT,
  thumb_url TEXT,
  description TEXT,
  watched_at VARCHAR(64) NOT NULL DEFAULT '',
  PRIMARY KEY (id),
  KEY idx_history_profile (profile_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS app_usage (
  id BIGINT NOT NULL AUTO_INCREMENT,
  profile_id VARCHAR(64) NOT NULL,
  app_name VARCHAR(128) NOT NULL,
  duration_seconds INT NOT NULL DEFAULT 0,
  started_at VARCHAR(64) NOT NULL DEFAULT '',
  PRIMARY KEY (id),
  KEY idx_usage_profile (profile_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS url_log (
  id BIGINT NOT NULL AUTO_INCREMENT,
  profile_id VARCHAR(64) NOT NULL,
  url TEXT,
  title TEXT,
  visited_at VARCHAR(64) NOT NULL DEFAULT '',
  PRIMARY KEY (id),
  KEY idx_url_profile (profile_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(64) NOT NULL,
  v TEXT,
  PRIMARY KEY (k)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS client_heartbeat (
  profile_id VARCHAR(64) NOT NULL,
  mode VARCHAR(32) NOT NULL DEFAULT '',
  active TINYINT NOT NULL DEFAULT 0,
  server_ok TINYINT NOT NULL DEFAULT 0,
  last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (profile_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
