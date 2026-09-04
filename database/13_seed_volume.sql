-- Realistic seed volume. The original inserts give 2-8 rows per table, which is
-- too small for the analytical questions the agent is meant to answer and far
-- too small to ever hit the 500-row cap.
--
-- DESTRUCTIVE: replaces every row in the transactional tables. Run deliberately.
--   psql -d talk_to_my_data_v2 -f database/13_seed_volume.sql

BEGIN;

TRUNCATE employee_projects, attendance, leaves, payroll, projects, employees
    RESTART IDENTITY CASCADE;

SELECT setseed(0.42);  -- deterministic: the same seed produces the same database

INSERT INTO employees (first_name, last_name, email, phone, salary, hire_date, job_title, status, department_id)
SELECT
    (ARRAY['Ana','Ben','Chen','Dara','Eli','Farah','Gita','Hugo','Iris','Jonas',
           'Kira','Luca','Maya','Nils','Omar','Petra','Quinn','Rosa','Sami','Tara'])[1 + (i % 20)],
    (ARRAY['Alvarez','Bakker','Costa','Duarte','Eriksen','Fontaine','Gupta','Haas',
           'Ivanov','Jensen','Kaur','Lindqvist','Moreau','Novak','Okafor','Pereira'])[1 + (i % 16)] || '-' || i,
    'employee' || i || '@example.com',
    '+1-555-' || lpad(i::text, 4, '0'),
    round((45000 + random() * 95000)::numeric, 2),
    DATE '2019-01-01' + (random() * 2100)::int,
    (ARRAY['Analyst','Senior Analyst','Engineer','Senior Engineer','Lead',
           'Manager','Coordinator','Specialist'])[1 + (random() * 7)::int],
    CASE WHEN random() < 0.08 THEN 'Inactive' ELSE 'Active' END,
    (SELECT department_id FROM departments ORDER BY random() LIMIT 1)
FROM generate_series(1, 120) AS g(i);

-- Managers, assigned after the rows exist so the self-reference resolves.
UPDATE employees e
SET manager_id = m.employee_id
FROM (SELECT employee_id, department_id FROM employees WHERE employee_id % 17 = 0) AS m
WHERE e.department_id = m.department_id
  AND e.employee_id <> m.employee_id;

INSERT INTO projects (project_name, description, start_date, end_date, budget, status, client_id)
SELECT
    'Project ' || upper(substr(md5(i::text), 1, 6)),
    'Engagement ' || i,
    DATE '2023-01-01' + (random() * 700)::int,
    CASE WHEN random() < 0.6 THEN DATE '2024-06-01' + (random() * 500)::int END,
    round((50000 + random() * 900000)::numeric, 2),
    (ARRAY['Planned','Active','On Hold','Completed'])[1 + (random() * 3)::int],
    (SELECT client_id FROM clients ORDER BY random() LIMIT 1)
FROM generate_series(1, 25) AS g(i);

INSERT INTO employee_projects (employee_id, project_id, role, allocation_percentage, assigned_date)
SELECT DISTINCT ON (e.employee_id, p.project_id)
    e.employee_id,
    p.project_id,
    (ARRAY['Contributor','Reviewer','Owner','Advisor'])[1 + (random() * 3)::int],
    (ARRAY[10, 20, 25, 50, 75, 100])[1 + (random() * 5)::int],
    p.start_date + (random() * 60)::int
FROM employees e
CROSS JOIN LATERAL (SELECT project_id, start_date FROM projects ORDER BY random() LIMIT 3) AS p;

-- ~90 working days per employee: the table the row cap actually gets tested on.
INSERT INTO attendance (employee_id, attendance_date, check_in, check_out, work_hours)
SELECT
    e.employee_id,
    d.day,
    TIME '08:30' + (random() * interval '90 minutes'),
    TIME '17:00' + (random() * interval '150 minutes'),
    round((6.5 + random() * 3)::numeric, 2)
FROM employees e
CROSS JOIN generate_series(DATE '2025-01-06', DATE '2025-05-30', interval '1 day') AS d(day)
WHERE e.status = 'Active'
  AND extract(isodow FROM d.day) < 6
  AND random() < 0.94;  -- absences, so attendance rates are not all identical

INSERT INTO leaves (employee_id, leave_type, start_date, end_date, status)
SELECT
    e.employee_id,
    (ARRAY['Annual','Sick','Unpaid','Parental'])[1 + (random() * 3)::int],
    start_date,
    start_date + (1 + random() * 9)::int,
    (ARRAY['Approved','Approved','Approved','Pending','Rejected'])[1 + (random() * 4)::int]
FROM employees e
CROSS JOIN LATERAL (SELECT DATE '2025-01-01' + (random() * 330)::int AS start_date) AS s
CROSS JOIN generate_series(1, 2) AS g(n)
WHERE random() < 0.7;

INSERT INTO payroll (employee_id, payroll_month, basic_salary, bonus, tax, net_salary)
SELECT
    e.employee_id,
    m.month::date,
    round(e.salary / 12, 2),
    bonus,
    round((e.salary / 12 + bonus) * 0.22, 2),
    round((e.salary / 12 + bonus) * 0.78, 2)
FROM employees e
CROSS JOIN generate_series(DATE '2025-01-01', DATE '2025-08-01', interval '1 month') AS m(month)
CROSS JOIN LATERAL (SELECT round((random() * 4000)::numeric, 2) AS bonus) AS b;

COMMIT;

SELECT 'employees' AS table_name, count(*) FROM employees
UNION ALL SELECT 'projects', count(*) FROM projects
UNION ALL SELECT 'employee_projects', count(*) FROM employee_projects
UNION ALL SELECT 'attendance', count(*) FROM attendance
UNION ALL SELECT 'leaves', count(*) FROM leaves
UNION ALL SELECT 'payroll', count(*) FROM payroll;
