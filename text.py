# from openai import OpenAI
# import os

# client = OpenAI(
#     api_key='sk-0ct42niKaLHidqsxbgaTMenSgAphSb0JnlcAeVm4YIXLUGNbqDFQz2I02bZmsczG',
#     base_url="https://opencode.ai/zen/v1"
# )

# models = client.models.list()

# for model in models.data:
#     print(model.id)


# from src.validator.syntax_validator import SyntaxValidator

# validator = SyntaxValidator()

# queries = [
#     "SELECT * FROM employees;",
#     "SELECT FROM employees;",
#     "INSERT INTO employees(name VALUES('John');",
# ]

# for query in queries:

#     result = validator.validate(query)

#     print("--------------------------")
#     print(query)
#     print(result)



# from src.validator.semantic_validator import SemanticValidator

# validator = SemanticValidator()

# queries = [

#     "SELECT * FROM employees;",

#     "SELECT first_name FROM employees;",

#     "SELECT age FROM employees;",

#     "SELECT * FROM doctors;",

#     "UPDATE employees SET salary = 50000;",

#     "DELETE FROM employees WHERE employee_id = 1;",

#     "INSERT INTO employees(first_name,last_name,email,hire_date) VALUES ('John','Doe','john@test.com','2026-07-29');"

# ]

# for query in queries:

#     print("--------------------------------")
#     print(query)

#     result = validator.validate(query)

#     print(result)

# from src.validator.permission_validator import PermissionValidator

# validator = PermissionValidator()

# queries = [

#     "SELECT * FROM employees;",

#     "INSERT INTO employees(first_name,last_name,email,hire_date) VALUES ('John','Doe','john@test.com','2026-07-29');",

#     "UPDATE employees SET salary = 100000;",

#     "DELETE FROM employees WHERE employee_id = 1;",

#     "DROP TABLE employees;",

#     "ALTER TABLE employees ADD COLUMN age INT;",

#     "TRUNCATE TABLE employees;"

# ]

# for query in queries:

#     print("------------------------------------")
#     print(query)

#     result = validator.validate(query)

#     print(result)

# from src.validator.safety_validator import SafetyValidator

# validator = SafetyValidator()

# queries = [

#     "SELECT * FROM employees;",

#     "UPDATE employees SET salary=50000;",

#     "UPDATE employees SET salary=50000 WHERE employee_id=1;",

#     "DELETE FROM employees;",

#     "DELETE FROM employees WHERE employee_id=1;",

#     "DROP TABLE employees;",

#     "ALTER TABLE employees ADD COLUMN age INT;",

#     "TRUNCATE TABLE employees;"
# ]

# for q in queries:

#     print("--------------------------------")

#     print(q)

#     print(validator.validate(q))


from src.validator.sql_validator import SQLValidator

validator = SQLValidator()

queries = [

    "SELECT * FROM employees;",

    "SELECT age FROM employees;",

    "SELECT * FROM doctors;",

    "UPDATE employees SET salary=50000;",

    "UPDATE employees SET salary=50000 WHERE employee_id=1;",

    "DELETE FROM employees;",

    "DELETE FROM employees WHERE employee_id=1;",

    "DROP TABLE employees;",

    "ALTER TABLE employees ADD COLUMN age INT;"
]

for q in queries:

    print("--------------------------------")

    print(q)

    print(validator.validate(q))