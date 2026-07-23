import logging
import sqlite3

logger = logging.getLogger(__name__)

class DatabaseManager:

    def __init__(self, db_path: str = "rtranscoder.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        
        self.conn.row_factory = sqlite3.Row



    def init_db(self) -> None:

        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                labels TEXT DEFAULT 'Normal',
                status TEXT DEFAULT 'pending',
                retries INTEGER DEFAULT 0,
                error_log TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pending_jobs
            ON processing_queue(status, created_at);
        """)

        self.conn.commit()
        logger.info("[DB] Database and indexes initialized successfully.")



    def add_video(self, source_path: str, category: str = "Movie", labels: str = "Normal") -> int | None:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO processing_queue (source_path, category, labels)
                VALUES (?, ?, ?)
                """,
                (source_path, category, labels)
            )
            self.conn.commit()
            logger.info(f"[DB] Video added to queue (ID: {cursor.lastrowid}): {source_path}")
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"[DB] Video already exists in queue, ignoring: {source_path}")
            return None



    def get_video_by_id(self, video_id: int) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM processing_queue WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None



    def get_next_pending(self) -> dict | None:
        query = """
            SELECT * FROM processing_queue
            WHERE status = 'pending'
            ORDER BY
                CASE
                    WHEN labels LIKE '%High%' THEN 1
                    WHEN labels LIKE '%Normal%' THEN 2
                    WHEN labels LIKE '%Low%' THEN 3
                    ELSE 2
                END ASC,
                created_at ASC
            LIMIT 1;
        """
        cursor = self.conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        return dict(row) if row else None



    def update_status(self, video_id: int, status: str, error_log: str | None = None) -> bool:
        cursor = self.conn.cursor()
        
        if error_log:
            cursor.execute(
                """
                UPDATE processing_queue
                SET status = ?, error_log = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, error_log, video_id)
            )
        else:
            cursor.execute(
                """
                UPDATE processing_queue
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, video_id)
            )
            
        self.conn.commit()
        return cursor.rowcount > 0



    def close(self) -> None:
        self.conn.close()
