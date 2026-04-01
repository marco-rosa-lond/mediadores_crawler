"""
Camada de persistência: SQLite para armazenamento estruturado
e exportação para Excel com pandas.

Esquema:
    mediadores      — informação base de cada site
    pages           — páginas individuais visitadas
    seguradoras     — seguradoras detetadas por mediador
    detections      — evidências de simuladores e formulários
"""
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import DB_PATH, OUTPUT_EXCEL

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS mediadores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    base_url        TEXT UNIQUE NOT NULL,
    nome            TEXT,
    has_simulator   INTEGER DEFAULT 0,
    simulator_score REAL DEFAULT 0,
    has_contact_form INTEGER DEFAULT 0,
    contact_form_score REAL DEFAULT 0,
    has_partners    INTEGER DEFAULT 0,
    seguradoras_count INTEGER DEFAULT 0,
    pages_crawled   INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'ok',   -- ok | error | timeout
    error_msg       TEXT,
    crawled_at      TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mediador_id     INTEGER REFERENCES mediadores(id),
    url             TEXT NOT NULL,
    title           TEXT,
    http_status     INTEGER,
    text_snippet    TEXT,   -- primeiros 500 chars do texto
    crawled_at      TEXT
);

CREATE TABLE IF NOT EXISTS seguradoras_detetadas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mediador_id     INTEGER REFERENCES mediadores(id),
    seguradora      TEXT NOT NULL,
    score           REAL,
    fonte           TEXT    -- 'texto' | 'logo' | 'ambos'
);

CREATE TABLE IF NOT EXISTS detections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mediador_id     INTEGER REFERENCES mediadores(id),
    tipo            TEXT,   -- 'simulator_iframe' | 'contact_form' | 'partner_section'
    score           REAL,
    evidencias_json TEXT,   -- JSON com keywords, src, etc.
    page_url        TEXT
);
"""


@contextmanager
def get_conn(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH) -> None:
    """Cria as tabelas se não existirem."""
    with get_conn(db_path) as conn:
        conn.executescript(DDL)
    logger.info(f"Base de dados iniciada: {db_path}")


def upsert_mediador(data: dict, db_path: str = DB_PATH) -> int:
    """
    Insere ou actualiza um mediador. Devolve o id.

    data esperado:
        base_url, nome?, has_simulator, simulator_score,
        has_contact_form, contact_form_score, has_partners,
        seguradoras_count, pages_crawled, status, error_msg?
    """
    now = datetime.utcnow().isoformat()
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO mediadores
                (base_url, nome, has_simulator, simulator_score,
                 has_contact_form, contact_form_score, has_partners,
                 seguradoras_count, pages_crawled, status, error_msg, crawled_at)
            VALUES
                (:base_url, :nome, :has_simulator, :simulator_score,
                 :has_contact_form, :contact_form_score, :has_partners,
                 :seguradoras_count, :pages_crawled, :status, :error_msg, :crawled_at)
            ON CONFLICT(base_url) DO UPDATE SET
                has_simulator      = excluded.has_simulator,
                simulator_score    = excluded.simulator_score,
                has_contact_form   = excluded.has_contact_form,
                contact_form_score = excluded.contact_form_score,
                has_partners       = excluded.has_partners,
                seguradoras_count  = excluded.seguradoras_count,
                pages_crawled      = excluded.pages_crawled,
                status             = excluded.status,
                error_msg          = excluded.error_msg,
                crawled_at         = excluded.crawled_at
            """,
            {**data, "crawled_at": now},
        )
        mediador_id = cur.lastrowid or _get_mediador_id(conn, data["base_url"])
    return mediador_id


def insert_page(mediador_id: int, page_data: dict, db_path: str = DB_PATH) -> None:
    now = datetime.utcnow().isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO pages
                (mediador_id, url, title, http_status, text_snippet, crawled_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                mediador_id,
                page_data.get("url"),
                page_data.get("title"),
                page_data.get("http_status"),
                page_data.get("text", "")[:500],
                now,
            ),
        )


def insert_seguradoras(
    mediador_id: int, seguradoras: dict[str, float], fonte: str = "texto",
    db_path: str = DB_PATH
) -> None:
    now = datetime.utcnow().isoformat()
    with get_conn(db_path) as conn:
        # Limpa entradas antigas para este mediador/fonte
        conn.execute(
            "DELETE FROM seguradoras_detetadas WHERE mediador_id=? AND fonte=?",
            (mediador_id, fonte),
        )
        conn.executemany(
            "INSERT INTO seguradoras_detetadas (mediador_id, seguradora, score, fonte) VALUES (?,?,?,?)",
            [(mediador_id, seg, score, fonte) for seg, score in seguradoras.items()],
        )


def insert_detection(
    mediador_id: int, tipo: str, score: float,
    evidencias: dict, page_url: str = "", db_path: str = DB_PATH
) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO detections (mediador_id, tipo, score, evidencias_json, page_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            (mediador_id, tipo, score, json.dumps(evidencias, ensure_ascii=False), page_url),
        )


def export_to_excel(db_path: str = DB_PATH, output: str = OUTPUT_EXCEL) -> None:
    """Exporta todas as tabelas para folhas de um ficheiro Excel."""
    with sqlite3.connect(db_path) as conn:
        dfs = {
            "Mediadores":    pd.read_sql("SELECT * FROM mediadores", conn),
            "Páginas":       pd.read_sql("SELECT * FROM pages", conn),
            "Seguradoras":   pd.read_sql("SELECT * FROM seguradoras_detetadas", conn),
            "Deteções":      pd.read_sql("SELECT * FROM detections", conn),
        }

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    logger.info(f"Exportado para Excel: {output}")


def _get_mediador_id(conn: sqlite3.Connection, base_url: str) -> int:
    row = conn.execute(
        "SELECT id FROM mediadores WHERE base_url=?", (base_url,)
    ).fetchone()
    return row["id"] if row else -1
