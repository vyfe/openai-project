"""全局 pytest fixture：替换模块级单例，提供测试用 Flask app、数据库和认证客户端。"""

import configparser
import os
import tempfile

import pytest
from playhouse.sqlite_ext import SqliteExtDatabase
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Session 级 fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tmp_db_dir():
    """Session 级临时目录，存放两个 SQLite 文件。"""
    with tempfile.TemporaryDirectory(prefix="quant_test_") as d:
        yield d


@pytest.fixture(scope="session")
def test_settings(tmp_db_dir):
    """构建测试用 Settings 对象，不依赖 conf.ini 文件。"""
    from conf.settings import Settings

    conf = configparser.ConfigParser()
    # 必填 section
    for section in ("common", "log", "admin", "quant", "api", "model_filter", "runtime_log", "auth"):
        conf.add_section(section)
    conf.set("common", "users", "test_admin:test123:sk-testkey")
    conf.set("common", "test_user", "test_admin")
    conf.set("log", "sqlite3_file", os.path.join(tmp_db_dir, "test_logs.db"))
    conf.set("quant", "sqlite3_file", os.path.join(tmp_db_dir, "test_quant.db"))
    conf.set("api", "api_key", "sk-test")
    conf.set("model_filter", "exclude_keywords", "instruct")
    conf.set("admin", "enable_sql_execute", "false")
    conf.set("runtime_log", "root_dir", tmp_db_dir)
    conf.set("runtime_log", "level", "WARNING")

    return Settings(
        conf=conf,
        base_dir=tmp_db_dir,
        conf_path="",
        api_hosts=[],
        default_api_key="sk-test",
        web_host="",
        upload_dir=os.path.join(tmp_db_dir, "uploads"),
        access_token_ttl_seconds=1800,
        refresh_token_ttl_seconds=604800,
        test_user_name="test_admin",
        test_ip_default_limit=9999,
        test_exceed_msg="test limit",
        model_cache_ttl=3600,
        model_exclude_keywords=["instruct"],
        meta_refresh_hour=2,
        meta_refresh_minute=0,
        meta_refresh_on_startup=False,
        usd_to_cny_rate=7.0,
        api_param_mode="default",
        enable_sql_execute=False,
        users_raw="test_admin:test123:sk-testkey",
        quant_sqlite3_file=os.path.join(tmp_db_dir, "test_quant.db"),
        quant_bundle_dir=os.path.join(tmp_db_dir, "bundles"),
        quant_memory_dir=os.path.join(tmp_db_dir, "memory"),
        quant_schedule_log_dir=os.path.join(tmp_db_dir, "schedule_logs"),
        quant_schedule_log_retention_days=1,
        runtime_log_root_dir=tmp_db_dir,
        runtime_log_level="WARNING",
        runtime_log_plain_retention_days=1,
        runtime_log_archive_retention_days=1,
        runtime_log_compress_backups=False,
        quant_feishu_app_id="",
        quant_feishu_app_secret="",
        quant_feishu_verification_token="",
        quant_feishu_encrypt_key="",
        quant_feishu_debug_suffix="",
    )


@pytest.fixture(scope="session")
def test_db(tmp_db_dir):
    """创建两个测试用 SQLite 数据库实例。"""
    log_db = SqliteExtDatabase(
        os.path.join(tmp_db_dir, "test_logs.db"),
        pragmas={"foreign_keys": 1},
    )
    quant_db = SqliteExtDatabase(
        os.path.join(tmp_db_dir, "test_quant.db"),
        pragmas={"journal_mode": "wal", "foreign_keys": 1},
    )
    return log_db, quant_db


@pytest.fixture(scope="session", autouse=True)
def patch_singletons(test_settings, test_db):
    """替换所有模块级单例为测试实例。"""
    log_db, quant_db = test_db

    with patch("conf.settings.settings", test_settings), \
         patch("conf.runtime.runtime_state.settings", test_settings), \
         patch("model.db.db", log_db), \
         patch("quant.db.quant_db", quant_db):
        yield


@pytest.fixture(scope="session")
def app(test_settings, test_db):
    """创建测试用 Flask app，注册所有 blueprint。"""
    from conf.app_factory import create_app
    from routes.public_routes import public_bp
    from routes.admin_routes import admin_bp
    from routes.quant_routes import quant_bp
    from routes.quant.strategy_routes import bp as quant_strategy_bp
    from routes.quant.im_memory_routes import bp as quant_im_memory_bp
    from routes.quant.trade_routes import bp as quant_trade_bp
    from routes.quant.data_routes import bp as quant_data_bp
    from routes.quant.scheduler_routes import bp as quant_scheduler_bp
    from routes.quant.client_routes import bp as quant_client_bp

    _app = create_app()
    _app.register_blueprint(public_bp)
    _app.register_blueprint(admin_bp)
    _app.register_blueprint(quant_bp)
    _app.register_blueprint(quant_strategy_bp)
    _app.register_blueprint(quant_im_memory_bp)
    _app.register_blueprint(quant_trade_bp)
    _app.register_blueprint(quant_data_bp)
    _app.register_blueprint(quant_scheduler_bp)
    _app.register_blueprint(quant_client_bp)
    _app.config["TESTING"] = True
    return _app


# ---------------------------------------------------------------------------
# Function 级 fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def init_tables(test_db):
    """每个测试函数前建表、测试后清表。"""
    log_db, quant_db = test_db

    from model.entities import ALL_MODELS, BaseModel
    from quant.entities import QUANT_MODELS, QuantBaseModel

    # 替换 Meta.database，Peewee 子类各自有独立的 _meta
    BaseModel._meta.database = log_db
    for model in ALL_MODELS:
        model._meta.database = log_db

    QuantBaseModel._meta.database = quant_db
    for model in QUANT_MODELS:
        model._meta.database = quant_db

    log_db.connect(reuse_if_open=True)
    quant_db.connect(reuse_if_open=True)
    log_db.create_tables(ALL_MODELS, safe=True)
    quant_db.create_tables(QUANT_MODELS, safe=True)

    yield

    quant_db.drop_tables(QUANT_MODELS, safe=True)
    log_db.drop_tables(ALL_MODELS, safe=True)


@pytest.fixture()
def seed_admin_user(test_db):
    """确保数据库中有 test_admin 用户，用于 require_admin_auth 绕过。"""
    from model.entities import User
    password_hash, salt = User.hash_password("test123")
    User.create(
        username="test_admin",
        password_hash=password_hash,
        salt=salt,
        role="admin",
        is_active=True,
    )


@pytest.fixture()
def seed_daily_bars(test_db):
    """插入测试用日线数据（30 日 × 2 标的）。"""
    from datetime import date, timedelta
    from quant.entities import QuantDailyBar

    base = date(2025, 1, 2)
    bars = []
    for offset in range(30):
        trade_date = base + timedelta(days=offset)
        for symbol, base_price in [("000001.SZ", 12.0), ("600519.SH", 1800.0)]:
            bars.append(dict(
                symbol=symbol,
                code=symbol.split(".")[0],
                exchange=symbol.split(".")[1],
                trade_date=trade_date,
                adjust_flag="qfq",
                open_price=base_price + offset * 0.1,
                high_price=base_price + offset * 0.2,
                low_price=base_price - offset * 0.05,
                close_price=base_price + offset * 0.15,
                preclose_price=base_price + max(0, offset - 1) * 0.15,
                volume=1_000_000 + offset * 10_000,
                amount=10_000_000 + offset * 100_000,
                turnover_rate=1.5 + offset * 0.05,
                pct_change=0.5 + offset * 0.1 if offset > 0 else 0,
                change=0.1,
                amplitude_pct=2.0,
                source="test",
                source_run_id="test-run",
            ))
    QuantDailyBar.insert_many(bars).execute()


class AuthClient:
    """封装 Flask test client，自动注入认证参数。"""

    def __init__(self, client, user="test_admin", password="test123"):
        self._client = client
        self.user = user
        self.password = password

    def get(self, url, **kwargs):
        params = kwargs.pop("params", {})
        params["user"] = self.user
        params["password"] = self.password
        return self._client.get(url, query_string=params, **kwargs)

    def post(self, url, **kwargs):
        json_data = kwargs.pop("json", None) or {}
        json_data["user"] = self.user
        json_data["password"] = self.password
        kwargs["json"] = json_data
        return self._client.post(url, **kwargs)


@pytest.fixture()
def auth_client(app, seed_admin_user):
    """带认证的 Flask test client。"""
    with app.test_client() as client:
        yield AuthClient(client)
