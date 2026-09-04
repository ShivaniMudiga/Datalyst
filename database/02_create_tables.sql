CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    location VARCHAR(100),
    budget NUMERIC(12,2) CHECK (budget >= 0)
);

CREATE TABLE clients (
    client_id SERIAL PRIMARY KEY,
    client_name VARCHAR(150) NOT NULL,
    industry VARCHAR(100),
    country VARCHAR(100),
    contact_email VARCHAR(150) UNIQUE
);

CREATE TABLE employees (

    employee_id SERIAL PRIMARY KEY,

    first_name VARCHAR(100) NOT NULL,

    last_name VARCHAR(100) NOT NULL,

    email VARCHAR(150) UNIQUE NOT NULL,

    phone VARCHAR(20),

    salary NUMERIC(10,2) CHECK (salary > 0),

    hire_date DATE NOT NULL,

    job_title VARCHAR(100),

    status VARCHAR(30) DEFAULT 'Active',

    department_id INTEGER,

    manager_id INTEGER,

    CONSTRAINT fk_department
        FOREIGN KEY(department_id)
        REFERENCES departments(department_id),

    CONSTRAINT fk_manager
        FOREIGN KEY(manager_id)
        REFERENCES employees(employee_id)
);

CREATE TABLE projects (

    project_id SERIAL PRIMARY KEY,

    project_name VARCHAR(150) NOT NULL,

    description TEXT,

    start_date DATE,

    end_date DATE,

    budget NUMERIC(12,2),

    status VARCHAR(30),

    client_id INTEGER,

    CONSTRAINT fk_client
        FOREIGN KEY(client_id)
        REFERENCES clients(client_id)
);

CREATE TABLE employee_projects (

    employee_id INTEGER,

    project_id INTEGER,

    role VARCHAR(100),

    allocation_percentage INTEGER
        CHECK(allocation_percentage BETWEEN 0 AND 100),

    assigned_date DATE,

    PRIMARY KEY(employee_id, project_id),

    FOREIGN KEY(employee_id)
        REFERENCES employees(employee_id),

    FOREIGN KEY(project_id)
        REFERENCES projects(project_id)
);

CREATE TABLE attendance (

    attendance_id SERIAL PRIMARY KEY,

    employee_id INTEGER,

    attendance_date DATE,

    check_in TIME,

    check_out TIME,

    work_hours NUMERIC(4,2),

    FOREIGN KEY(employee_id)
        REFERENCES employees(employee_id)
);

CREATE TABLE leaves (

    leave_id SERIAL PRIMARY KEY,

    employee_id INTEGER,

    leave_type VARCHAR(50),

    start_date DATE,

    end_date DATE,

    status VARCHAR(30),

    FOREIGN KEY(employee_id)
        REFERENCES employees(employee_id)
);


CREATE TABLE payroll (

    payroll_id SERIAL PRIMARY KEY,

    employee_id INTEGER,

    payroll_month DATE,

    basic_salary NUMERIC(10,2),

    bonus NUMERIC(10,2),

    tax NUMERIC(10,2),

    net_salary NUMERIC(10,2),

    FOREIGN KEY(employee_id)
        REFERENCES employees(employee_id)
);


