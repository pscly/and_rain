"""安卓手机调用然后通过 termux 运行，判断是否下雨, 下雨就搞个提前的闹钟

使用方法:
  在 Termux 中运行: python main.py
  可在项目根目录放置 .env 文件，示例见 .env.template（脚本会读取 .env 并将变量注入环境）
功能:
  - 优先使用 termux-location 获取经纬度
  - 若无法获取位置信息, 会尝试从环境变量/ .env 或 IP 地理位置服务回退
  - API token 从环境变量 CAIYUN_API_KEY 或 .env 中读取
依赖:
  - requests
"""

import os
import json
import time
import logging
import subprocess
from typing import Optional, Dict, Any, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 默认配置（会被环境变量覆盖）
DEFAULT_API_KEY = "xxxxx"
DEFAULT_LON = 104.547
DEFAULT_LAT = 30.3352
CAIYUN_URL_TEMPLATE = "https://api.caiyunapp.com/v2.6/{key}/{lon},{lat}/realtime"

DEFAULT_LOCAL_INTENSITY_THRESHOLD = 0.15
DEFAULT_NEAREST_INTENSITY_THRESHOLD = 0.10
DEFAULT_NEAREST_DISTANCE_KM = 7


def load_dotenv(path: str = ".env") -> None:
    """简单读取 .env 文件的 KEY=VALUE 并放入 os.environ（如果对应变量尚未设置）"""
    if not os.path.exists(path):
        logging.debug(".env 文件不存在: %s", path)
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        logging.exception("加载 .env 时出现错误")


def get_location() -> Tuple[float, float]:
    """优先使用 termux-location 获取经纬度；失败后尝试环境变量；再降级到 IP 地理位置服务；最终使用默认值"""
    # 1) termux-location -j
    try:
        logging.info("尝试通过 termux-location 获取定位（适用于 Termux）")
        proc = subprocess.run(["termux-location", "-j"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout:
            try:
                j = json.loads(proc.stdout)
                lat = float(j.get("latitude") or j.get("lat") or 0)
                lon = float(j.get("longitude") or j.get("lon") or 0)
                if lat and lon:
                    logging.info("从 termux-location 获取到定位: %s,%s", lon, lat)
                    return lon, lat
            except Exception:
                logging.exception("解析 termux-location 输出失败")
    except FileNotFoundError:
        logging.debug("termux-location 不存在")
    except Exception:
        logging.exception("调用 termux-location 失败")

    # 2) 环境变量
    try:
        lon_env = os.getenv("LON")
        lat_env = os.getenv("LAT")
        if lon_env and lat_env:
            lon = float(lon_env)
            lat = float(lat_env)
            logging.info("从环境变量获取定位: %s,%s", lon, lat)
            return lon, lat
    except Exception:
        logging.exception("解析环境变量经纬度失败")

    # 3) IP 地理位置服务回退
    try:
        logging.info("使用 IP 地理位置服务回退获取定位")
        r = requests.get("https://ipapi.co/json/", timeout=5)
        if r.status_code == 200:
            j = r.json()
            lat = float(j.get("latitude") or j.get("lat") or 0)
            lon = float(j.get("longitude") or j.get("lon") or 0)
            if lat and lon:
                logging.info("从 IP 服务获取到定位: %s,%s", lon, lat)
                return lon, lat
    except Exception:
        logging.exception("调用 IP 地理位置服务失败")

    # 4) 最后退回到默认
    logging.warning("使用默认经纬度")
    return DEFAULT_LON, DEFAULT_LAT


def set_alarm_ahead(minutes: int = 1) -> None:
    """在安卓上通过 am 命令设置闹钟，提前 minutes 分钟"""
    future_ts = time.time() + minutes * 60
    ft = time.localtime(future_ts)
    h = ft.tm_hour
    m = ft.tm_min
    cmd = (
        "am start -a android.intent.action.SET_ALARM "
        "--ez android.intent.extra.alarm.SKIP_UI true "
        "--ei android.intent.extra.alarm.HOUR %d "
        "--ei android.intent.extra.alarm.MINUTES %d"
    ) % (h, m)
    logging.info("设置闹钟，时间 %02d:%02d (提前 %d 分钟)", h, m, minutes)
    try:
        os.system(cmd)
    except Exception:
        logging.exception("执行设置闹钟命令失败")


def get_weather(lon: float, lat: float, api_key: str, retries: int = 3, backoff: float = 1.0) -> Optional[Dict[str, Any]]:
    url = CAIYUN_URL_TEMPLATE.format(key=api_key, lon=lon, lat=lat)
    for attempt in range(1, retries + 1):
        try:
            logging.info("请求天气数据: %s (尝试 %d/%d)", url, attempt, retries)
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                logging.warning("非 200 响应: %s", resp.status_code)
            else:
                return resp.json()
        except requests.RequestException:
            logging.exception("请求天气 API 失败")
        time.sleep(backoff * attempt)
    return None


def safe_get_precipitation(data: Dict[str, Any]) -> Dict[str, float]:
    """从 API 响应中安全提取下雨相关数据，返回 dict 包含 local_intensity, nearest_distance, nearest_intensity"""
    try:
        pr = data["result"]["realtime"]["precipitation"]
        local_intensity = float(pr.get("local", {}).get("intensity", 0.0))
        nearest = pr.get("nearest", {})
        nearest_distance = float(nearest.get("distance", float("inf")))
        nearest_intensity = float(nearest.get("intensity", 0.0))
        return {
            "local_intensity": local_intensity,
            "nearest_distance": nearest_distance,
            "nearest_intensity": nearest_intensity,
        }
    except Exception:
        logging.exception("解析天气数据失败")
        return {"local_intensity": 0.0, "nearest_distance": float("inf"), "nearest_intensity": 0.0}


def main():
    # 读取 .env（如果存在）
    load_dotenv(".env")

    api_key = os.getenv("CAIYUN_API_KEY", DEFAULT_API_KEY)
    try:
        local_threshold = float(os.getenv("LOCAL_INTENSITY_THRESHOLD", DEFAULT_LOCAL_INTENSITY_THRESHOLD))
        nearest_threshold = float(os.getenv("NEAREST_INTENSITY_THRESHOLD", DEFAULT_NEAREST_INTENSITY_THRESHOLD))
        nearest_km = float(os.getenv("NEAREST_DISTANCE_KM", DEFAULT_NEAREST_DISTANCE_KM))
    except Exception:
        logging.exception("解析阈值失败，使用默认值")
        local_threshold = DEFAULT_LOCAL_INTENSITY_THRESHOLD
        nearest_threshold = DEFAULT_NEAREST_INTENSITY_THRESHOLD
        nearest_km = DEFAULT_NEAREST_DISTANCE_KM

    lon, lat = get_location()

    data = get_weather(lon=lon, lat=lat, api_key=api_key, retries=5)
    if not data:
        logging.error("未能获取天气数据，退出")
        return
    p = safe_get_precipitation(data)
    logging.info("当前位置下雨强度 local=%s, 最近距离=%s km, 最近强度=%s", p["local_intensity"], p["nearest_distance"], p["nearest_intensity"])
    # 判断条件
    if p["local_intensity"] > local_threshold:
        logging.info("本地下雨强度超过阈值，设置闹钟")
        set_alarm_ahead(1)
        return
    if p["nearest_intensity"] > nearest_threshold and p["nearest_distance"] < nearest_km:
        logging.info("附近下雨带靠近且强度超过阈值，设置闹钟")
        set_alarm_ahead(1)
        return
    logging.info("未满足设置闹钟的条件")


if __name__ == "__main__":
    main()