import configparser
import os
from dataclasses import dataclass
from typing import Optional


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF_PATH = os.path.join(BASE_DIR, "conf", "conf.ini")


@dataclass(frozen=True)
class Settings:
    conf: configparser.ConfigParser
    base_dir: str
    conf_path: str
    api_hosts: list[str]
    default_api_key: str
    web_host: str
    upload_dir: str
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    test_user_name: str
    test_ip_default_limit: int
    test_exceed_msg: str
    model_cache_ttl: int
    model_exclude_keywords: list[str]
    meta_refresh_hour: int
    meta_refresh_minute: int
    meta_refresh_on_startup: bool
    usd_to_cny_rate: float
    api_param_mode: str
    enable_sql_execute: bool
    users_raw: str
    quant_sqlite3_file: str
    quant_bundle_dir: str


def _get_bool(conf: configparser.ConfigParser, section: str, option: str, fallback: str = "false") -> bool:
    if not conf.has_section(section):
        return fallback.lower() in ("1", "true", "yes", "on")
    return conf.get(section, option, fallback=fallback).lower() in ("1", "true", "yes", "on")


def _get_str(conf: configparser.ConfigParser, section: str, option: str, fallback: str = "") -> str:
    if not conf.has_section(section):
        return fallback
    value = conf.get(section, option, fallback=fallback)
    return value if str(value).strip() else fallback


def load_settings(conf_path: Optional[str] = None) -> Settings:
    final_conf_path = conf_path or CONF_PATH
    conf = configparser.ConfigParser()
    conf.read(final_conf_path, encoding="utf-8")

    api_hosts = [item.strip() for item in conf.get("api", "api_host", fallback="").split(",") if item.strip()]
    exclude_keywords = [
        item.strip()
        for item in conf.get("model_filter", "exclude_keywords", fallback="instruct,realtime,audio").split(",")
        if item.strip()
    ]

    return Settings(
        conf=conf,
        base_dir=BASE_DIR,
        conf_path=final_conf_path,
        api_hosts=api_hosts,
        default_api_key=conf.get("api", "api_key", fallback=""),
        web_host=conf.get("common", "host", fallback=""),
        upload_dir=conf.get("common", "upload_dir", fallback=""),
        access_token_ttl_seconds=int(conf.get("auth", "access_token_ttl_seconds", fallback="1800")),
        refresh_token_ttl_seconds=int(conf.get("auth", "refresh_token_ttl_seconds", fallback="604800")),
        test_user_name=conf.get("common", "test_user", fallback=""),
        test_ip_default_limit=int(conf.get("common", "test_ip_default_limit", fallback="20")),
        test_exceed_msg=conf.get("common", "test_exceed_msg", fallback="请求次数已达上限"),
        model_cache_ttl=int(conf.get("model_filter", "cache_ttl", fallback="3600")),
        model_exclude_keywords=exclude_keywords,
        meta_refresh_hour=int(conf.get("model_filter", "meta_refresh_hour", fallback="2")),
        meta_refresh_minute=int(conf.get("model_filter", "meta_refresh_minute", fallback="0")),
        meta_refresh_on_startup=_get_bool(conf, "model_filter", "meta_refresh_on_startup", fallback="true"),
        usd_to_cny_rate=float(conf.get("api", "usd_to_cny_rate", fallback="2.5")),
        api_param_mode=conf.get("api", "api_param_mode", fallback="default"),
        enable_sql_execute=_get_bool(conf, "admin", "enable_sql_execute", fallback="false"),
        users_raw=conf.get("common", "users", fallback=""),
        quant_sqlite3_file=_get_str(conf, "quant", "sqlite3_file", fallback=os.path.join(BASE_DIR, "quant.db")),
        quant_bundle_dir=_get_str(conf, "quant", "bundle_dir", fallback=os.path.join(BASE_DIR, "quant_bundles")),
    )


settings = load_settings()
