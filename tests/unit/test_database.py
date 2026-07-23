import sqlite3
import pytest
from rtranscoder.database import DatabaseManager

@pytest.fixture
def db_manager():
    manager = DatabaseManager(db_path=":memory:")
    manager.init_db()
    return manager


#======================================================
#Table Creation and Index Tests
#======================================================

def test_init_db_creates_table_and_index(db_manager):

    cursor = db_manager.conn.cursor()

    cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processing_queue';"
        )

    table = cursor.fetchone()
    assert table is not None

    cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_pending_jobs';"
        )

    index = cursor.fetchone()
    assert index is not None

#======================================================
#Insertion and Duplicates Validation tests
#======================================================

def test_add_video_success(db_manager):

    video_id = db_manager.add_video(
            source_path = "/media/movies/Movie.mkv",
            category = "Movie",
            labels = "High"
        )

    assert video_id is not None
    assert video_id > 0

    video = db_manager.get_video_by_id(video_id)

    assert video["source_path"] == "/media/movies/Movie.mkv"
    assert video["category"] == "Movie"
    assert video["labels"] == "High"
    assert video["status"] == "pending"

def test_add_duplicate_video_returns_none(db_manager):

    
        db_manager.add_video( source_path = "/media/movies/Movie.mkv", category = "Movie" )

        second_id = db_manager.add_video( source_path = "/media/movies/Movie.mkv", category = "Movie" )

        assert second_id is None
        
#======================================================
#Priority Ordering (High > Normal > Low) and FIFO tests
#======================================================

def test_get_next_pending_respects_priority_labels(db_manager):

    db_manager.add_video( source_path = "/media/movies/Movie_low.mkv", category = "Movie", labels = "Low" )
    db_manager.add_video( source_path = "/media/movies/Movie_high.mkv", category = "Movie", labels = "High" )
    db_manager.add_video( source_path = "/media/movies/Movie_normal.mkv", category = "Movie", labels = "Normal" )

    first = db_manager.get_next_pending()

    assert first["source_path"] == "/media/movies/Movie_high.mkv"

def test_get_next_pending_fifo_order_for_same_priority(db_manager):

    db_manager.add_video( source_path = "/media/movies/Movie_first.mkv", category = "Movie", labels = "Normal" )
    db_manager.add_video( source_path = "/media/movies/Movie_second.mkv", category = "Movie", labels = "Normal" )

    first = db_manager.get_next_pending()

    assert first["source_path"] == "/media/movies/Movie_first.mkv"

#======================================================
#Priority Ordering (High > Normal > Low) and FIFO tests
#======================================================

def test_update_status_and_error_log(db_manager):

    video_id = db_manager.add_video(
            source_path = "/media/movies/Corrupted_File.mkv",
            category = "Movie",
            labels = "High"
        )

    db_manager.update_status(video_id, status="processing")
    video = db_manager.get_video_by_id(video_id)

    assert video["status"] == "processing"

    error_msg = "FFmpeg error: Invalid stream data"
    db_manager.update_status( video_id, status="failed", error_log = error_msg )

    video = db_manager.get_video_by_id(video_id)

    assert video["status"] == "failed"
    assert video["error_log"] == error_msg
    

