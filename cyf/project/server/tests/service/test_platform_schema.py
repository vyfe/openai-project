"""平台 SQLite 的存量库补列：音乐表新增列后旧库也能继续用。"""
import pytest

pytestmark = pytest.mark.service


def test_music_table_gains_cover_columns(test_db):
    log_db, _ = test_db
    from model.db import ensure_schema
    from model.entities import ModelMeta, User

    log_db.execute_sql("DROP TABLE IF EXISTS music_track")
    log_db.execute_sql("CREATE TABLE music_track (id TEXT PRIMARY KEY, scope TEXT, title TEXT, status TEXT)")
    ensure_schema(User, ModelMeta)
    columns = {col.name for col in log_db.get_columns("music_track")}
    assert {"cover_feature_id", "reference_duration"} <= columns
    assert {"id", "scope", "title", "status"} <= columns
