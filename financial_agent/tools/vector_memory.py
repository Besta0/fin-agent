from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from financial_agent.tools.memory import safe_user_id, user_memory_dir


HASH_DIMENSIONS = 512
DB_NAME = "vector_memory.sqlite"


def vector_memory_path(user_id: str | None = None) -> Path:
    return user_memory_dir(user_id) / DB_NAME


def _connect(user_id: str | None = None) -> sqlite3.Connection:
    path = vector_memory_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vector_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            ticker TEXT,
            company_name TEXT,
            title TEXT,
            rating TEXT,
            confidence REAL,
            summary TEXT,
            report_path TEXT,
            metadata_json TEXT,
            text TEXT NOT NULL,
            vector_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_vector_memories_user_id ON vector_memories(user_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_vector_memories_ticker ON vector_memories(user_id, ticker)"
    )
    _ensure_column(conn, "rating", "TEXT")
    _ensure_column(conn, "confidence", "REAL")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, name: str, column_type: str) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(vector_memories)")}
    if name not in columns:
        conn.execute(f"ALTER TABLE vector_memories ADD COLUMN {name} {column_type}")


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9.]{2,}", lowered)
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    for chunk in chinese:
        if len(chunk) == 1:
            tokens.append(chunk)
        else:
            tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return tokens


def _bucket(token: str) -> str:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
    value = int.from_bytes(digest, byteorder="big", signed=False)
    return str(value % HASH_DIMENSIONS)


def hash_tf_vector(text: str) -> dict[str, int]:
    counts = Counter(_bucket(token) for token in _tokens(text))
    return {key: int(value) for key, value in counts.items() if value > 0}


def _searchable_text(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key) or "")
        for key in ("ticker", "company_name", "title", "summary", "text")
    )


def append_vector_memory(user_id: str | None, record: dict[str, Any]) -> str:
    safe_id = safe_user_id(user_id)
    text = _searchable_text(record)
    vector = hash_tf_vector(text)
    metadata = record.get("metadata") or {}

    with _connect(safe_id) as conn:
        conn.execute(
            """
            INSERT INTO vector_memories (
                user_id,
                timestamp,
                ticker,
                company_name,
                title,
                rating,
                confidence,
                summary,
                report_path,
                metadata_json,
                text,
                vector_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                safe_id,
                datetime.now().isoformat(timespec="seconds"),
                record.get("ticker"),
                record.get("company_name"),
                record.get("title"),
                record.get("rating"),
                record.get("confidence"),
                record.get("summary"),
                record.get("report_path"),
                json.dumps(metadata, ensure_ascii=False),
                str(record.get("text") or ""),
                json.dumps(vector, ensure_ascii=False),
            ),
        )
        conn.commit()
    return str(vector_memory_path(safe_id))


def _load_rows(user_id: str | None = None) -> list[dict[str, Any]]:
    safe_id = safe_user_id(user_id)
    path = vector_memory_path(safe_id)
    if not path.exists():
        return []

    with _connect(safe_id) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                user_id,
                timestamp,
                ticker,
                company_name,
                title,
                rating,
                confidence,
                summary,
                report_path,
                metadata_json,
                text,
                vector_json
            FROM vector_memories
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (safe_id,),
        ).fetchall()

    records: list[dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        try:
            record["vector"] = json.loads(record.pop("vector_json") or "{}")
        except json.JSONDecodeError:
            record["vector"] = {}
        try:
            record["metadata"] = json.loads(record.pop("metadata_json") or "{}")
        except json.JSONDecodeError:
            record["metadata"] = {}
        records.append(record)
    return records


def _document_frequency(rows: list[dict[str, Any]]) -> Counter[str]:
    df: Counter[str] = Counter()
    for row in rows:
        vector = row.get("vector") or {}
        df.update(vector.keys())
    return df


def _tfidf(
    vector: dict[str, int | float],
    document_frequency: Counter[str],
    total_docs: int,
) -> dict[str, float]:
    weighted: dict[str, float] = {}
    for key, count in vector.items():
        tf = 1.0 + math.log(float(count))
        idf = math.log((1 + total_docs) / (1 + document_frequency.get(key, 0))) + 1.0
        weighted[key] = tf * idf
    return weighted


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    overlap = set(left) & set(right)
    numerator = sum(left[key] * right[key] for key in overlap)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def search_vector_memory(
    user_id: str | None,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows = _load_rows(user_id)
    if not rows:
        return []

    query_vector = hash_tf_vector(query)
    if not query_vector:
        return []

    df = _document_frequency(rows)
    total_docs = len(rows)
    query_tfidf = _tfidf(query_vector, df, total_docs)

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        memory_tfidf = _tfidf(row.get("vector") or {}, df, total_docs)
        score = _cosine(query_tfidf, memory_tfidf)
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "id": row.get("id"),
                    "user_id": row.get("user_id"),
                    "timestamp": row.get("timestamp"),
                    "ticker": row.get("ticker"),
                    "company_name": row.get("company_name"),
                    "title": row.get("title"),
                    "rating": row.get("rating"),
                    "confidence": row.get("confidence"),
                    "summary": row.get("summary"),
                    "report_path": row.get("report_path"),
                    "metadata": row.get("metadata") or {},
                    "text": row.get("text"),
                    "score": round(score, 3),
                    "source": "sqlite_vector_memory",
                },
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    return [memory for _, memory in scored[:limit]]
