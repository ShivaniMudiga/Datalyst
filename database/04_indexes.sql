CREATE INDEX idx_employee_department
ON employees(department_id);

CREATE INDEX idx_employee_manager
ON employees(manager_id);

CREATE INDEX idx_project_client
ON projects(client_id);

CREATE INDEX idx_attendance_employee
ON attendance(employee_id);

CREATE INDEX idx_leave_employee
ON leaves(employee_id);

CREATE INDEX idx_payroll_employee
ON payroll(employee_id);

CREATE INDEX idx_employee_email
ON employees(email);