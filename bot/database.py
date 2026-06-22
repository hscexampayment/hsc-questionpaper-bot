import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")

RANKS = [
    (0,     "🥉 Bronze"),
    (100,   "🥈 Silver"),
    (500,   "🥇 Gold"),
    (1500,  "💎 Platinum"),
    (5000,  "👑 Diamond"),
]

POINTS_PER_REFERRAL = 50
POINTS_PER_JOIN = 20


def get_rank(points: int) -> str:
    rank = RANKS[0][1]
    for threshold, name in RANKS:
        if points >= threshold:
            rank = name
        else:
            break
    return rank


def next_rank_info(points: int):
    for i, (threshold, name) in enumerate(RANKS):
        if points < threshold:
            return name, threshold
    return None, None


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                points      INTEGER DEFAULT 0,
                referred_by INTEGER,
                joined_at   TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(referred_id)
            )
        """)
        conn.commit()


def get_or_create_user(user_id: int, username: str, first_name: str) -> sqlite3.Row:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        else:
            conn.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                (username, first_name, user_id),
            )
            conn.commit()
    return row


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def add_points(user_id: int, points: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET points = points + ? WHERE user_id = ?",
            (points, user_id),
        )
        conn.commit()


def register_referral(referrer_id: int, referred_id: int) -> bool:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,)
        ).fetchone()
        if existing:
            return False
        if referrer_id == referred_id:
            return False
        conn.execute(
            "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
            (referrer_id, referred_id),
        )
        conn.execute(
            "UPDATE users SET referred_by = ? WHERE user_id = ?",
            (referrer_id, referred_id),
        )
        conn.commit()
        return True


def get_referral_count(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id = ?", (user_id,)
        ).fetchone()
        return row["cnt"] if row else 0


def get_referrals(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            """SELECT u.first_name, u.username, u.points, r.created_at
               FROM referrals r
               JOIN users u ON u.user_id = r.referred_id
               WHERE r.referrer_id = ?
               ORDER BY r.created_at DESC
               LIMIT 10""",
            (user_id,),
        ).fetchall()


def get_leaderboard(limit: int = 10):
    with get_conn() as conn:
        return conn.execute(
            "SELECT user_id, first_name, username, points FROM users ORDER BY points DESC LIMIT ?",
            (limit,),
        ).fetchall()


def set_points(user_id: int, points: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET points = ? WHERE user_id = ?", (points, user_id))
        conn.commit()


def get_all_users(limit: int = 20, offset: int = 0):
    with get_conn() as conn:
        return conn.execute(
            "SELECT user_id, first_name, username, points, joined_at FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_user_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        return row["cnt"] if row else 0


def get_total_referrals() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM referrals").fetchone()
        return row["cnt"] if row else 0


def search_user(query: str):
    with get_conn() as conn:
        try:
            uid = int(query)
            return conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
        except ValueError:
            q = query.lstrip("@")
            return conn.execute(
                "SELECT * FROM users WHERE username LIKE ?", (f"%{q}%",)
            ).fetchone()


def get_all_user_ids():
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [r["user_id"] for r in rows]
