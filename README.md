# AndRain — Termux 下雨提醒并提前闹钟

这是一个小脚本，目标很简单：在手机上跑着，实时检测是否要下雨，如果有必要就提前通过系统闹钟提醒你，免得被淋湿。它为 Termux 环境做了优化，但也提供回退方案，方便在不同环境下使用。

## 特性

- 优先使用 termux-location 获取设备经纬度（适用于 Android + Termux）。
- 调用彩云天气（Caiyun）实时接口获取降水强度。
- 满足阈值条件时，通过系统命令设置闹钟（跳过 UI）提醒用户。
- 支持通过 `.env` 配置 API key、经纬度与阈值，使用简单直观。

## 适用场景

- 想在出门时，提前收到下雨提醒并准备好带伞和提前出发。
- 在 Termux 下长期运行脚本的轻量工具。

## 项目文件

- [`main.py`](main.py:1) — 主脚本，包含定位、请求、阈值判断与设置闹钟的核心逻辑。  
- [`.env.template`](.env.template:1) — 环境变量示例文件，复制并填入实际值（不要上传到公共仓库）。

## 先决条件

- Android（推荐） + Termux 
- Python 3.8+  
- requests 库：pip install requests

termux 需要安装扩展库:

```bash
pkg install termux
```

## 快速开始

1. 把仓库或脚本复制到设备上的某个目录。  
2. 复制环境模板并填写你的信息：
   - cp .env.template .env
   - 编辑 `.env`，填写 `CAIYUN_API_KEY`（以及可选的 LON、LAT、阈值）。  
3. 安装依赖：
   - pip install requests
4. 在 Termux 中运行：
   - python main.py

脚本会尝试使用 termux-location 获取经纬度；如果失败会回退到环境变量或 IP 地理定位，最终使用默认值。

## 配置说明（.env）
在项目根目录创建 `.env`（或直接通过系统环境变量设置）：
- CAIYUN_API_KEY=你的彩云天气 API Key（必填）  
- LON、LAT（可选）：经度和纬度（当 termux-location 不可用时使用）  
- LOCAL_INTENSITY_THRESHOLD（可选）：本地降水强度触发阈值（默认 0.15）  
- NEAREST_INTENSITY_THRESHOLD（可选）：最近雨带强度阈值（默认 0.10）  
- NEAREST_DISTANCE_KM（可选）：最近雨带距离阈值（默认 7 km）

示例模板见：[`.env.template`](.env.template:1)。

## 实现要点

1. 优先通过 `termux-location -j` 获取设备定位（适用于有 Termux 的设备）。  
2. 若无 termux，脚本会尝试读取 `.env` 中的 LON/LAT；如果仍无则使用 IP 地理服务回退。  
3. 使用彩云天气实时接口获取降水信息，并做安全解析以防响应格式变化。  
4. 若当前地点或附近雨带强度超过阈值，则通过 `am start -a android.intent.action.SET_ALARM ...` 设置闹钟（跳过 UI），实现即时提醒。

## 调试与常见问题

- 如果脚本没有设置闹钟，先查看日志输出（脚本使用 logging 打印信息）。  
- 若 termux-location 不存在或报错，确认是否在 Termux 环境并已安装 termux-tools。  
- `am` 命令在不同 ROM/设备上的行为可能略有不同，若不生效可以改为使用通知/音量提醒等替代方案。  
- 请确保 `.env` 中的 `CAIYUN_API_KEY` 正确且未泄露到公开仓库。

## 代码风格与检查

- 若想做静态检查，可在设备或开发机上安装 flake8/pyflakes：  
  - pip install flake8 pyflakes  
  - flake8 main.py 或 python -m pyflakes main.py

## 许可

MIT
