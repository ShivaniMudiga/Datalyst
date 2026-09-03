-- Two throwaway databases from unrelated domains.
--
-- Rule 1 of this project is that only the schema and the purpose text know your
-- domain. These exist to prove it: point the app at either one and nothing in
-- any prompt, label, suggestion or error should mention employees, departments
-- or salaries. If it does, that string is a bug.
--
--   psql -d postgres -f database/14_domain_leakage_check.sql

CREATE DATABASE leakage_check_transit;
\connect leakage_check_transit

CREATE TABLE lines (
    line_id SERIAL PRIMARY KEY,
    line_name VARCHAR(80) NOT NULL UNIQUE,
    colour VARCHAR(30),
    opened_on DATE
);

CREATE TABLE stations (
    station_id SERIAL PRIMARY KEY,
    station_name VARCHAR(120) NOT NULL,
    line_id INTEGER REFERENCES lines(line_id),
    platform_count INTEGER,
    step_free BOOLEAN DEFAULT FALSE
);

CREATE TABLE footfall (
    footfall_id BIGSERIAL PRIMARY KEY,
    station_id INTEGER REFERENCES stations(station_id),
    recorded_on DATE NOT NULL,
    entries INTEGER,
    exits INTEGER
);

INSERT INTO lines (line_name, colour, opened_on) VALUES
    ('Northern Loop', 'navy', DATE '1998-04-12'),
    ('Riverside', 'teal', DATE '2006-09-30'),
    ('Airport Link', 'amber', DATE '2015-02-18');

INSERT INTO stations (station_name, line_id, platform_count, step_free)
SELECT 'Station ' || i, 1 + (i % 3), 1 + (i % 4), i % 3 = 0
FROM generate_series(1, 24) AS g(i);

INSERT INTO footfall (station_id, recorded_on, entries, exits)
SELECT s.station_id, d.day, (800 + random() * 9000)::int, (700 + random() * 9000)::int
FROM stations s
CROSS JOIN generate_series(DATE '2025-03-01', DATE '2025-05-31', interval '1 day') AS d(day);

\connect postgres

CREATE DATABASE leakage_check_clinic;
\connect leakage_check_clinic

CREATE TABLE owners (
    owner_id SERIAL PRIMARY KEY,
    owner_name VARCHAR(120) NOT NULL,
    town VARCHAR(80),
    registered_on DATE
);

CREATE TABLE animals (
    animal_id SERIAL PRIMARY KEY,
    animal_name VARCHAR(80) NOT NULL,
    species VARCHAR(40),
    date_of_birth DATE,
    owner_id INTEGER REFERENCES owners(owner_id)
);

CREATE TABLE visits (
    visit_id BIGSERIAL PRIMARY KEY,
    animal_id INTEGER REFERENCES animals(animal_id),
    visited_on DATE NOT NULL,
    reason VARCHAR(120),
    fee NUMERIC(8,2)
);

INSERT INTO owners (owner_name, town, registered_on)
SELECT 'Owner ' || i, (ARRAY['Ashford','Belmont','Carrow','Dunmore'])[1 + (i % 4)],
       DATE '2020-01-01' + (i * 7)
FROM generate_series(1, 30) AS g(i);

INSERT INTO animals (animal_name, species, date_of_birth, owner_id)
SELECT 'Animal ' || i,
       (ARRAY['cat','dog','rabbit','parrot'])[1 + (i % 4)],
       DATE '2018-01-01' + (random() * 2200)::int,
       1 + (i % 30)
FROM generate_series(1, 60) AS g(i);

INSERT INTO visits (animal_id, visited_on, reason, fee)
SELECT a.animal_id,
       DATE '2025-01-01' + (random() * 240)::int,
       (ARRAY['vaccination','check-up','dental','injury','follow-up'])[1 + (random() * 4)::int],
       round((25 + random() * 300)::numeric, 2)
FROM animals a
CROSS JOIN generate_series(1, 4) AS g(n);
