import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "frodo_app.db"
)

class AppDatabase:
    """
    Универсальный слой базы данных приложения Frodo.
    По умолчанию использует SQLite (server/data/frodo_app.db).
    Обеспечивает изоляцию подключений, поддержку внешних ключей и WAL-режим.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Контекстный менеджер безопасного подключения к БД."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """Создает таблицы и индексы в базе данных, если они отсутствуют."""
        with self.connection() as conn:
            conn.executescript("""
                -- Таблица пользователей
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    moodle_user_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT,
                    role TEXT NOT NULL CHECK(role IN ('student', 'instructor')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Таблица лабораторных работ
                CREATE TABLE IF NOT EXISTS labs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    order_num INTEGER UNIQUE NOT NULL
                );

                -- Таблица прогресса студентов по лабораторным работам
                CREATE TABLE IF NOT EXISTS student_lab_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    lab_id INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
                    status TEXT NOT NULL CHECK(status IN ('not_started', 'in_progress', 'passed')) DEFAULT 'not_started',
                    grade REAL DEFAULT 0.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, lab_id)
                );

                -- История диалогов
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    lab_id INTEGER REFERENCES labs(id) ON DELETE SET NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mode TEXT CHECK(mode IN ('socratic', 'master')) DEFAULT 'socratic',
                    citations TEXT,
                    score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Неотвеченные запросы (Gap Analysis для преподавателей)
                CREATE TABLE IF NOT EXISTS unanswered_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    question TEXT NOT NULL,
                    score REAL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Индексы для оптимизации выборок
                CREATE INDEX IF NOT EXISTS idx_users_moodle_id ON users(moodle_user_id);
                CREATE INDEX IF NOT EXISTS idx_progress_user ON student_lab_progress(user_id);
                CREATE INDEX IF NOT EXISTS idx_progress_lab ON student_lab_progress(lab_id);
                CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_unanswered_created ON unanswered_queries(created_at DESC);
            """)

    def seed_db(self):
        """
        Инициализирует базовые лабораторные работы и демонстрационных пользователей,
        если база данных пустая.
        """
        with self.connection() as conn:
            # 1. Лабораторные работы
            default_labs = [
                (1, "Лаба 1: Базовые структуры данных и типы", "Списки, кортежи, словари, множества, операции и методы коллекций в Python.", 1),
                (2, "Лаба 2: Операторы и выражения", "Условные ветвления (if/elif/else), циклы (for/while), операторы сравнения и списковые включения.", 2),
                (3, "Лаба 3: Обработка исключений и файлы", "Конструкции try/except/finally, пользовательские исключения, менеджеры контекста with, работа с файлами.", 3)
            ]
            for lab_id, title, desc, order_num in default_labs:
                conn.execute("""
                    INSERT OR IGNORE INTO labs (id, title, description, order_num)
                    VALUES (?, ?, ?, ?)
                """, (lab_id, title, desc, order_num))

            # 2. Пользователи: student_42 и instructor_1
            conn.execute("""
                INSERT OR IGNORE INTO users (moodle_user_id, name, email, role)
                VALUES (?, ?, ?, ?)
            """, ("student_42", "Алексей Иванов", "student_42@university.edu", "student"))

            conn.execute("""
                INSERT OR IGNORE INTO users (moodle_user_id, name, email, role)
                VALUES (?, ?, ?, ?)
            """, ("instructor_1", "Проф. Смирнов А.В.", "prof_smirnov@university.edu", "instructor"))

            # 3. Инициализируем прогресс для student_42
            user_row = conn.execute("SELECT id FROM users WHERE moodle_user_id = ?", ("student_42",)).fetchone()
            if user_row:
                s_id = user_row["id"]
                conn.execute("""
                    INSERT OR IGNORE INTO student_lab_progress (user_id, lab_id, status, grade)
                    VALUES (?, ?, ?, ?)
                """, (s_id, 1, "passed", 100.0))
                conn.execute("""
                    INSERT OR IGNORE INTO student_lab_progress (user_id, lab_id, status, grade)
                    VALUES (?, ?, ?, ?)
                """, (s_id, 2, "in_progress", 45.0))
                conn.execute("""
                    INSERT OR IGNORE INTO student_lab_progress (user_id, lab_id, status, grade)
                    VALUES (?, ?, ?, ?)
                """, (s_id, 3, "not_started", 0.0))

    # ------------------ Пользователи ------------------

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_user_by_moodle_id(self, moodle_user_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE moodle_user_id = ?", (moodle_user_id,)).fetchone()
            return dict(row) if row else None

    def create_or_update_user(self, moodle_user_id: str, name: str, email: Optional[str] = None, role: str = "student") -> Dict[str, Any]:
        """Создает или обновляет данные пользователя по moodle_user_id."""
        with self.connection() as conn:
            existing = conn.execute("SELECT id, role FROM users WHERE moodle_user_id = ?", (moodle_user_id,)).fetchone()
            if existing:
                conn.execute("""
                    UPDATE users
                    SET name = ?, email = COALESCE(?, email), role = ?
                    WHERE id = ?
                """, (name, email, role, existing["id"]))
                user_id = existing["id"]
            else:
                cursor = conn.execute("""
                    INSERT INTO users (moodle_user_id, name, email, role)
                    VALUES (?, ?, ?, ?)
                """, (moodle_user_id, name, email, role))
                user_id = cursor.lastrowid

            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(user)

    def list_students(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM users WHERE role = 'student' ORDER BY name ASC").fetchall()
            return [dict(r) for r in rows]

    # ------------------ Лабораторные работы ------------------

    def get_all_labs(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM labs ORDER BY order_num ASC").fetchall()
            return [dict(r) for r in rows]

    def get_lab_by_id(self, lab_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
            return dict(row) if row else None

    def ensure_student_progress_records(self, user_id: int):
        """Гарантирует наличие записей в student_lab_progress для всех лаб у студента."""
        with self.connection() as conn:
            labs = conn.execute("SELECT id FROM labs").fetchall()
            for lab in labs:
                conn.execute("""
                    INSERT OR IGNORE INTO student_lab_progress (user_id, lab_id, status, grade)
                    VALUES (?, ?, 'not_started', 0.0)
                """, (user_id, lab["id"]))

    # ------------------ Прогресс студентов ------------------

    def get_student_progress(self, user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список всех лабораторных работ с текущим прогрессом студента."""
        self.ensure_student_progress_records(user_id)
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT 
                    l.id AS lab_id,
                    l.title,
                    l.description,
                    l.order_num,
                    COALESCE(p.status, 'not_started') AS status,
                    COALESCE(p.grade, 0.0) AS grade,
                    p.updated_at
                FROM labs l
                LEFT JOIN student_lab_progress p 
                    ON l.id = p.lab_id AND p.user_id = ?
                ORDER BY l.order_num ASC
            """, (user_id,)).fetchall()

            res = []
            for r in rows:
                item = dict(r)
                # Доступ к режиму Master открывается только если лаба сдана (status == 'passed')
                item["can_master_mode"] = (item["status"] == "passed")
                res.append(item)
            return res

    def get_student_lab_status(self, user_id: int, lab_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute("""
                SELECT * FROM student_lab_progress
                WHERE user_id = ? AND lab_id = ?
            """, (user_id, lab_id)).fetchone()
            return dict(row) if row else None

    def update_student_lab_progress(self, user_id: int, lab_id: int, status: str, grade: Optional[float] = None) -> Dict[str, Any]:
        """Обновляет статус и оценку студента по конкретной лабораторной работе."""
        with self.connection() as conn:
            existing = conn.execute("""
                SELECT id, grade FROM student_lab_progress
                WHERE user_id = ? AND lab_id = ?
            """, (user_id, lab_id)).fetchone()

            target_grade = grade if grade is not None else (existing["grade"] if existing else 0.0)

            if existing:
                conn.execute("""
                    UPDATE student_lab_progress
                    SET status = ?, grade = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, target_grade, existing["id"]))
            else:
                conn.execute("""
                    INSERT INTO student_lab_progress (user_id, lab_id, status, grade, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, lab_id, status, target_grade))

            updated = conn.execute("""
                SELECT 
                    l.id AS lab_id,
                    l.title,
                    l.description,
                    l.order_num,
                    p.status,
                    p.grade,
                    p.updated_at
                FROM student_lab_progress p
                JOIN labs l ON l.id = p.lab_id
                WHERE p.user_id = ? AND p.lab_id = ?
            """, (user_id, lab_id)).fetchone()
            
            res = dict(updated)
            res["can_master_mode"] = (res["status"] == "passed")
            return res

    def get_all_students_progress_matrix(self) -> List[Dict[str, Any]]:
        """Формирует сводную матрицу успеваемости для панели преподавателя."""
        students = self.list_students()
        labs = self.get_all_labs()

        with self.connection() as conn:
            matrix = []
            for student in students:
                s_id = student["id"]
                self.ensure_student_progress_records(s_id)
                progress_rows = conn.execute("""
                    SELECT 
                        l.id AS lab_id,
                        l.title,
                        l.description,
                        l.order_num,
                        COALESCE(p.status, 'not_started') AS status,
                        COALESCE(p.grade, 0.0) AS grade,
                        p.updated_at
                    FROM labs l
                    LEFT JOIN student_lab_progress p 
                        ON l.id = p.lab_id AND p.user_id = ?
                    ORDER BY l.order_num ASC
                """, (s_id,)).fetchall()

                student_labs = []
                for pr in progress_rows:
                    item = dict(pr)
                    item["can_master_mode"] = (item["status"] == "passed")
                    student_labs.append(item)

                matrix.append({
                    "student": student,
                    "labs": student_labs
                })
            return matrix

    # ------------------ Чат и сообщения ------------------

    def add_chat_message(
        self,
        user_id: Optional[int],
        role: str,
        content: str,
        lab_id: Optional[int] = None,
        mode: str = "socratic",
        citations: Optional[str] = None,
        score: Optional[float] = None
    ) -> Dict[str, Any]:
        with self.connection() as conn:
            cursor = conn.execute("""
                INSERT INTO chat_messages (user_id, lab_id, role, content, mode, citations, score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, lab_id, role, content, mode, citations, score))
            msg_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (msg_id,)).fetchone()
            return dict(row)

    def get_chat_history(self, user_id: int, lab_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            if lab_id is not None:
                rows = conn.execute("""
                    SELECT * FROM chat_messages 
                    WHERE user_id = ? AND lab_id = ?
                    ORDER BY id ASC LIMIT ?
                """, (user_id, lab_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM chat_messages 
                    WHERE user_id = ?
                    ORDER BY id ASC LIMIT ?
                """, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]

    # ------------------ Неотвеченные вопросы (Gap Analysis) ------------------

    def add_unanswered_query(
        self,
        question: str,
        user_id: Optional[int] = None,
        score: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        with self.connection() as conn:
            cursor = conn.execute("""
                INSERT INTO unanswered_queries (user_id, question, score, reason)
                VALUES (?, ?, ?, ?)
            """, (user_id, question, score, reason))
            q_id = cursor.lastrowid
            row = conn.execute("""
                SELECT uq.*, u.name AS user_name
                FROM unanswered_queries uq
                LEFT JOIN users u ON u.id = uq.user_id
                WHERE uq.id = ?
            """, (q_id,)).fetchone()
            return dict(row)

    def get_unanswered_queries(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT 
                    uq.id,
                    uq.user_id,
                    u.name AS user_name,
                    uq.question,
                    uq.score,
                    uq.reason,
                    uq.created_at
                FROM unanswered_queries uq
                LEFT JOIN users u ON u.id = uq.user_id
                ORDER BY uq.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            return [dict(r) for r in rows]

# Глобальный экземпляр базы данных по умолчанию
db = AppDatabase()
