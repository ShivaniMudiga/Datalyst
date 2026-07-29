from src.db.connection import DatabaseConnection


class SchemaExplorer:

    def __init__(self):
        self.db = DatabaseConnection()
        self.connection = self.db.connect()

    def get_tables(self):
        """
        Returns all user tables in the database.
        """

        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        AND table_type='BASE TABLE'
        ORDER BY table_name;
        """

        with self.connection.cursor() as cursor:
            cursor.execute(query)

            rows = cursor.fetchall()

        return [row["table_name"] for row in rows]

    def get_columns(self, table_name):
        """
        Returns all columns of a table with metadata.
        """

        query = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        ORDER BY ordinal_position;
        """

        with self.connection.cursor() as cursor:
            cursor.execute(query, (table_name,))
            rows = cursor.fetchall()

        columns = []

        for row in rows:
            columns.append({
                "column_name": row["column_name"],
                "data_type": row["data_type"],
                "nullable": row["is_nullable"] == "YES"
            })

        return columns

    def close(self):
        self.db.close()


    def get_database_schema(self):
        """
        Returns the complete database schema.

        Example:
        {
            "employees": {
                "employee_id": {
                    "data_type": "integer",
                    "nullable": False
                },
                "first_name": {
                    "data_type": "character varying",
                    "nullable": False
                }
            },
            "departments": {
                ...
            }
        }
        """

        schema = {}

        tables = self.get_tables()

        for table in tables:

            columns = self.get_columns(table)

            schema[table] = {}

            for column in columns:

                schema[table][column["column_name"]] = {
                    "data_type": column["data_type"],
                    "nullable": column["nullable"]
                }

        return schema