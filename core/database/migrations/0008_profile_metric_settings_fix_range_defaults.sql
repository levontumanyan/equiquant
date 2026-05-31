-- Remove the legacy DEFAULT 0.0 / 100.0 from range_min / range_max so that
-- NULL is unambiguously "use benchmark default".  Rows whose range_min=0.0
-- and range_max=100.0 are treated as uncustomised and nulled out.
-- Safe on fresh databases: the table will be empty so no data is transformed.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS profile_metric_settings_new;

CREATE TABLE profile_metric_settings_new (
	profile_name TEXT,
	metric_key   TEXT,
	weight       REAL    DEFAULT 1.0,
	range_min    REAL,
	range_max    REAL,
	formula      TEXT,
	is_penalty   BOOLEAN DEFAULT 0,
	PRIMARY KEY (profile_name, metric_key),
	FOREIGN KEY (profile_name) REFERENCES investor_profiles(name)
);

INSERT OR IGNORE INTO profile_metric_settings_new
	(profile_name, metric_key, weight, range_min, range_max, formula, is_penalty)
SELECT
	profile_name,
	metric_key,
	weight,
	CASE WHEN range_min = 0.0 AND range_max = 100.0 THEN NULL ELSE range_min END,
	CASE WHEN range_min = 0.0 AND range_max = 100.0 THEN NULL ELSE range_max END,
	formula,
	is_penalty
FROM profile_metric_settings;

DROP TABLE profile_metric_settings;
ALTER TABLE profile_metric_settings_new RENAME TO profile_metric_settings;

PRAGMA foreign_keys = ON;
