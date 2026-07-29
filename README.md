# TalkToMyData

An AI-powered Database Agent that enables users to interact with any PostgreSQL database using natural language.

Instead of writing SQL manually, users can ask questions in plain English. The agent understands the request, explores the database schema when necessary, generates SQL, validates it through multiple security layers, and executes it safely.

---

## Features

- Natural language to SQL
- PostgreSQL database support
- Automatic schema exploration
- MCP (Model Context Protocol) tools
- OpenCode Zen LLM integration
- SQL syntax validation
- SQL semantic validation
- Permission-based query validation
- Safety validation against destructive operations
- Tool-calling agent architecture
- Modular and extensible codebase

---

## Project Architecture

```
                  User
                    │
                    ▼
              main.py (CLI)
                    │
                    ▼
                agent.py
                    │
                    ▼
            OpenCode Zen LLM
                    │
        Tool Calling (MCP Style)
                    │
     ┌──────────────┼──────────────┐
     │              │              │
     ▼              ▼              ▼
get_tables()   get_columns()   execute_sql()
                                    │
                                    ▼
                             SQL Validator
                                    │
       ┌────────────┬──────────────┬──────────────┬──────────────┐
       ▼            ▼              ▼              ▼
   Syntax      Semantic      Permission      Safety
   Validator   Validator     Validator      Validator
                                    │
                                    ▼
                             Query Executor
                                    │
                                    ▼
                              PostgreSQL
```

---

## Folder Structure

```
TalkToMyDataV2/

├── config/
│   └── permissions.json
│
├── src/
│   ├── agent/
│   │   └── agent.py
│   │
│   ├── db/
│   │   └── connection.py
│   │
│   ├── executor/
│   │   └── query_executor.py
│   │
│   ├── explorer/
│   │   └── schema_explorer.py
│   │
│   ├── llm/
│   │   └── zen_client.py
│   │
│   └── validator/
│       ├── sql_validator.py
│       ├── syntax_validator.py
│       ├── semantic_validator.py
│       ├── permission_validator.py
│       ├── safety_validator.py
│       └── validation_result.py
│
├── mcp_server.py
├── main.py
└── README.md
```

---

# How It Works

The execution flow is designed to ensure every SQL query is validated before it reaches the database.

```
User Question
      │
      ▼
OpenCode Zen
      │
      ▼
Tool Selection
      │
      ▼
execute_sql(query)
      │
      ▼
SQL Validator
      │
      ├── Syntax Validation
      ├── Semantic Validation
      ├── Permission Validation
      └── Safety Validation
      │
      ▼
Query Executor
      │
      ▼
PostgreSQL
      │
      ▼
LLM explains the result
```

---

# SQL Validation Pipeline

## 1. Syntax Validation

Uses **SQLGlot** to verify SQL syntax before execution.

Example:

```
SELECT * FROM employees;
```

Valid

Example:

```
SELECT FROM employees;
```

Invalid

---

## 2. Semantic Validation

Checks that the SQL references valid database objects.

Verifies:

- Tables exist
- Columns exist
- Schema matches the query

Example:

```
SELECT age FROM employees;
```

Rejected because `age` does not exist.

---

## 3. Permission Validation

Permissions are controlled using

```
config/permissions.json
```

Example configuration

```json
{
    "SELECT": true,
    "INSERT": true,
    "UPDATE": true,
    "DELETE": true,
    "DROP": false,
    "ALTER": false,
    "TRUNCATE": false
}
```

This prevents the AI from executing restricted SQL operations.

---

## 4. Safety Validation

Even if an operation is permitted, it must also be safe.

Examples blocked automatically:

```
DELETE FROM employees;
```

```
UPDATE employees SET salary=100000;
```

Both are rejected because they affect every row.

Allowed:

```
DELETE FROM employees
WHERE employee_id=5;
```

---

# MCP Tools

The agent exposes three tools.

### get_tables()

Returns every table in the database.

---

### get_columns(table)

Returns column names and metadata.

---

### execute_sql(query)

Validates the query and executes it only if every validation stage succeeds.

---

# Technologies Used

- Python
- PostgreSQL
- FastMCP
- OpenCode Zen API
- OpenAI Python SDK
- SQLGlot
- psycopg2
- dotenv

---

# Example Queries

```
Show all employees.
```

```
List all departments.
```

```
How many employees are there?
```

```
Add an employee named Shivani.
```

```
Show employees hired after 2024.
```

```
Delete employee with employee_id = 5.
```

---

# Validation Example

User:

```
Delete all employees.
```

Generated SQL

```sql
DELETE FROM employees;
```

Validation Result

```
Rejected

Reason:
DELETE without WHERE clause is not allowed.
```

---

# Current Capabilities

- Read data
- Insert records
- Update records
- Delete records safely
- Automatic schema discovery
- SQL validation
- Natural language interaction
- Tool-calling architecture

---

# Future Improvements

- Conversational memory
- Multi-turn reasoning
- SQL auto-correction
- Query history
- Authentication and user roles
- Support for MySQL and SQLite
- Streaming responses
- Web interface
- Docker deployment
- Observability and logging

---

# Learning Outcomes

This project demonstrates practical experience with

- AI Agents
- Model Context Protocol (MCP)
- Tool Calling
- Large Language Models
- PostgreSQL
- SQL Validation
- Agent Architecture
- Secure AI System Design

---

# Author

**Shivani Mudiga**

Built as part of an AI Engineering internship to explore secure, agentic database systems powered by Large Language Models.
