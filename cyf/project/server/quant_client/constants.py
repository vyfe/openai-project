SUPPORTED_DATASET = "a_share_daily_bars_v1"
DEFAULT_TASK_TYPE = "fetch_a_share_daily_bars"

# 分时数据集 / task_type（首期仅 5m）
SUPPORTED_DATASETS = {
    "a_share_daily_bars_v1",
    "a_share_5min_bars_v1",
}
TASK_TYPE_BY_FREQUENCY = {
    "1d": "fetch_a_share_daily_bars",
    "5m": "fetch_a_share_minute_bars",
}
DATASET_BY_FREQUENCY = {
    "1d": "a_share_daily_bars_v1",
    "5m": "a_share_5min_bars_v1",
}
SUPPORTED_FREQUENCIES = set(TASK_TYPE_BY_FREQUENCY.keys())
SUPPORTED_TASK_TYPES = set(TASK_TYPE_BY_FREQUENCY.values())

