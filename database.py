"""
database.py
------------
Responsável por criar e ligar à base de dados SQLite.
Zero configuração: basta correr a aplicação e o ficheiro .db é criado sozinho.
"""

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "archivly.db")


def get_db():
    """Abre uma ligação à base de dados. Cada pedido usa a sua própria ligação."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # permite aceder às colunas pelo nome
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Cria as tabelas se ainda não existirem. Chamado uma vez ao arrancar a app."""
    conn = get_db()
    cursor = conn.cursor()

    # Tabela de utilizadores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabela de ficheiros enviados pelo utilizador
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            file_type TEXT NOT NULL,       -- imagem, video, audio, documento
            mime_type TEXT,
            size_bytes INTEGER,
            r2_key TEXT NOT NULL,          -- caminho do ficheiro original no R2
            r2_url TEXT NOT NULL,          -- URL público do ficheiro original
            thumbnail_r2_key TEXT,         -- caminho da miniatura no R2 (se existir)
            thumbnail_url TEXT,            -- URL público da miniatura
            site_id INTEGER,               -- a que site pertence (pode ser NULL até publicar)
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (site_id) REFERENCES sites (id)
        )
    """)

    # Tabela de sites publicados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            site_name TEXT NOT NULL,       -- nome escolhido pelo utilizador
            repo_name TEXT NOT NULL,       -- nome do repositório no GitHub
            site_url TEXT,                 -- URL final do GitHub Pages
            status TEXT DEFAULT 'a_processar', -- a_processar, publicado, erro
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()
