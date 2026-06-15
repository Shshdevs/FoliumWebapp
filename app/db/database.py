from typing import Any, Dict, Sequence, Tuple, List
from core.config import config
import psycopg2
from psycopg2.extras import RealDictCursor


class Database:
    def __init__(self):
        self.db_url = config.DB_URL

    def _build_where(self, eq: Sequence[Tuple[str, Any]] = None) -> Tuple[str, list]:
        if not eq:
            return "", []
        conditions = [f"{k} = %s" for k, v in eq]
        where_clause = " WHERE " + " AND ".join(conditions)
        params = [v for _, v in eq]
        return where_clause, params

    def select(
        self,
        table: str,
        values: Sequence[Tuple[str, Any]] = "*",
        eq: Sequence[Tuple[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        where_clause, params = self._build_where(eq)
        query = f"SELECT {values} FROM {table}{where_clause};"
        return self.execute_fetch(query, params)

    def insert(self, table: str, data: Dict[str, Any]) -> None:
        if not data:
            return
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders});"
        self.execute_commit(query, list(data.values()))

    def update(
        self, table: str, data: Dict[str, Any], eq: Sequence[Tuple[str, Any]] = None
    ) -> None:
        if not data:
            return
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        where_clause, where_params = self._build_where(eq)

        query = f"UPDATE {table} SET {set_clause}{where_clause};"
        params = list(data.values()) + where_params
        self.execute_commit(query, params)

    def execute_commit(self, query: str, params: list = None) -> None:
        with psycopg2.connect(self.db_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)

    def execute_fetch(self, query: str, params: list = None) -> List[Dict[str, Any]]:
        with psycopg2.connect(self.db_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()


db = Database()
