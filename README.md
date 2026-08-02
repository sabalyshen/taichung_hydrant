# 🔥 消防水源地圖 Telegram Bot

消防人員火災現場即時消防栓查詢與車輛管理系統。透過 Telegram Bot，指揮官、駕駛或是大隊幕僚輸入地址即可取得附近 100 支消防栓地圖，各車人員傳送位置後一鍵標註所有車輛。(目前適用臺中的地址去搜索，若其他縣市要使用要修改文字處理的模組)
消防栓定位可以由水源系統下載的.csv檔再轉為kml檔，轉檔前請參考下方格式。
---

## 🚀 快速開始

### 1. 安裝依賴
```bash
pip install python-telegram-bot pillow requests
```

### 2. 設定 Bot Token
編輯 `main.py` 或 `utils.py`，將 `BOT_TOKEN` 換成你的 Bot Token（透過 [@BotFather](https://t.me/BotFather) 取得）。

### 3. 啟動
```bash
cd modular/
python main.py
```

### 4. 群組設定
將 Bot 加入群組後，在 BotFather 執行 `/setprivacy` → Disable，Bot 才能讀取群組訊息。

---

## 📋 功能說明

| 步驟 | 操作 | Bot 回應 |
|---|---|---|
| 1 | 傳送地址 | 產生地圖（PNG + HTML）+ 最近 5 支消防栓導航連結 |
| 2 | 傳送位置＋車輛編號 | 記錄車輛（同一個人的位置和編號配對） |
| 3 | `/car` | 將所有車輛標註到地圖上（不清空清單） |
| 4 | 再傳新車輛 → `/car` | 更新地圖 |
| 5 | 傳送新地址 | 詢問是否替換（y/n） |

### 指令

| 指令 | 功能 |
|---|---|
| `/start` | 顯示說明 |
| `/car` | 標註所有車輛到地圖（PNG + HTML） |
| `/save` | 另存 HTML（時間戳記檔名） |
| `/load` | 列出最近 10 筆已存地圖 |
| `/1` ~ `/10` | 取得指定已存地圖 |
| `/cancel` | 清除地址與車輛清單 |

---

## 📁 專案結構（模組化）

```
modular/
├── main.py                  ← 主程式入口
├── utils.py                 ← 共用工具（地址辨識、Token）
├── state_manager.py         ← 群組狀態管理（chat_data + JSON 持久化）
├── handlers/
│   ├── __init__.py
│   ├── commands.py           ← 指令處理（/start /cancel /car /save /load /N）
│   ├── messages.py           ← 文字訊息處理（地址、確認對話、車輛記錄）
│   └── locations.py          ← 位置訊息處理
├── map_bot.py                ← 地圖引擎（載入 KML、定位、繪圖、互動 HTML）
├── data/
│   └── 11410總.kml           ← 消防栓資料（20,763 筆）
├── leaflet_css.txt           ← Leaflet CSS 內嵌快取
├── leaflet_js.txt            ← Leaflet JS 內嵌快取
├── chat_states/              ← 群組狀態持久化目錄（自動產生）
└── saved_maps/               ← /save 另存目錄（自動產生）
```

### 快速糾錯指南

| 錯誤現象 | 查哪個模組 |
|---|---|
| Bot 無回應 | `main.py` → Token / 網路 |
| 不認得地址 | `utils.py` → `is_address()` |
| `/car` 說沒地址 | `state_manager.py` → `load_state()` |
| 消防車沒標上 | `handlers/locations.py` → 位置+編號配對 |
| HTML 空白 | `map_bot.py` → `_get_leaflet_assets()` |
| 定位錯誤 | `map_bot.py` → `geocode_address()` |
| 重複訊息 | `handlers/messages.py` → `is_bot` 過濾 |

---

## 🗺️ KML 資料格式

`data/11410總.kml` 為消防栓資料來源，由 CSV 轉換而成。

### CSV 欄位
```
消防栓編號,單位名稱,種類,區鄉鎮市名稱,消防栓位置,經度,緯度,水公司單位名稱
```

### KML 結構（轉換後）
```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>消防栓</name>
    <Placemark>
      <name>4479</name>                          <!-- 消防栓編號 -->
      <description><![CDATA[
        消防栓編號: 4479<br>
        自訂編號: <br>
        單位名稱: 大里分隊<br>
        種類: 地下<br>
        區鄉鎮市名稱: 大里區<br>
        消防栓位置: 國光路二段299號前<br>
        經度: 120.6803083<br>
        緯度: 24.10726247<br>
        水公司單位名稱: 大里服務所
      ]]></description>
      <ExtendedData>
        <Data name="消防栓編號"><value>4479</value></Data>
        <Data name="單位名稱"><value>大里分隊</value></Data>
        <Data name="種類"><value>地下</value></Data>
        <Data name="區鄉鎮市名稱"><value>大里區</value></Data>
        <Data name="消防栓位置"><value>國光路二段299號前</value></Data>
        <Data name="經度"><value>120.6803083</value></Data>
        <Data name="緯度"><value>24.10726247</value></Data>
        <Data name="水公司單位名稱"><value>大里服務所</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>120.6803083,24.10726247,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
```

### 更新消防栓資料

1. 將新的 CSV 放到 `kml/` 目錄
2. 執行轉換腳本：
   ```bash
   python csv_to_kml.py
   ```
3. 將產生的 `11410總.kml` 複製到 `modular/data/`
4. 刪除 `hydrants_cache.json` 強制重建快取

---

## 📦 打包成 exe

```bash
pyinstaller --onefile --console --name "消防水源地圖Bot" \
  --add-data "data/11410總.kml;data" \
  --add-data "leaflet_css.txt;." \
  --add-data "leaflet_js.txt;." \
  --hidden-import telegram --hidden-import telegram.ext \
  --hidden-import PIL --hidden-import PIL.Image \
  --hidden-import PIL.ImageDraw --hidden-import PIL.ImageFont \
  --hidden-import requests --hidden-import xml.etree.ElementTree \
  main.py
```

產出 `dist/消防水源地圖Bot.exe`（約 28MB），複製到任何 Windows 電腦即可運行。

---

## 🔧 技術棧

- **Python 3.11+**
- **python-telegram-bot** — Telegram Bot API
- **Pillow (PIL)** — 靜態地圖繪製
- **Leaflet.js** — 互動式 HTML 地圖（完全內嵌，無外部 CDN 依賴）
- **OpenStreetMap** — 地圖圖磚
- **ArcGIS Geocoder** — 台灣地址定位

---

## 📄 授權

本專案為消防單位內部使用，未開放商業授權。
