# 🔥 Fire Hydrant Map Telegram Bot

Real-time fire hydrant query and vehicle management system for firefighting operations. The commander sends an address to get a map of the 100 nearest hydrants. Crew members send their GPS location and vehicle ID, then one command places all vehicles on the map.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install python-telegram-bot pillow requests
```

### 2. Configure Bot Token
Edit `main.py` or `utils.py` and replace `BOT_TOKEN` with your token from [@BotFather](https://t.me/BotFather).

### 3. Launch
```bash
cd modular/
python main.py
```

### 4. Group Setup
Add the bot to a group, then run `/setprivacy` → **Disable** in BotFather so the bot can read all messages.

---

## 📋 Features

| Step | Action | Bot Response |
|---|---|---|
| 1 | Send an address | Generates map (PNG + HTML) + directions to 5 nearest hydrants |
| 2 | Send location + vehicle ID | Records vehicle (location and ID paired to same user) |
| 3 | `/car` | Renders all vehicles onto the map (list preserved) |
| 4 | Add more vehicles → `/car` | Updates the map |
| 5 | Send a new address | Confirms before replacing (y/n) |

### Commands

| Command | Description |
|---|---|
| `/start` | Show help |
| `/car` | Generate map with all recorded vehicles (PNG + HTML) |
| `/save` | Save HTML with timestamp filename |
| `/load` | List last 10 saved maps |
| `/1` – `/10` | Retrieve a specific saved map |
| `/cancel` | Clear address and vehicle list |

---

## 📁 Project Structure (Modular)

```
modular/
├── main.py                  ← Entry point
├── utils.py                 ← Utilities (address detection, Token)
├── state_manager.py         ← Chat state management (chat_data + JSON persistence)
├── handlers/
│   ├── __init__.py
│   ├── commands.py           ← Command handlers (/start /cancel /car /save /load /N)
│   ├── messages.py           ← Text message handlers (address, confirmations, vehicle recording)
│   └── locations.py          ← Location message handler
├── map_bot.py                ← Map engine (KML loading, geocoding, drawing, interactive HTML)
├── data/
│   └── 11410總.kml           ← Hydrant dataset (20,763 records)
├── leaflet_css.txt           ← Leaflet CSS cache (inlined)
├── leaflet_js.txt            ← Leaflet JS cache (inlined)
├── chat_states/              ← Persistent chat state (auto-created)
└── saved_maps/               ← /save output directory (auto-created)
```

### Quick Debugging Guide

| Symptom | Module to Check |
|---|---|
| Bot not responding | `main.py` → Token / network |
| Address not recognized | `utils.py` → `is_address()` |
| `/car` says no address | `state_manager.py` → `load_state()` |
| Vehicle not on map | `handlers/locations.py` → location+label pairing |
| HTML shows blank | `map_bot.py` → `_get_leaflet_assets()` |
| Wrong map location | `map_bot.py` → `geocode_address()` |
| Duplicate messages | `handlers/messages.py` → `is_bot` filter |

---

## 🗺️ KML Data Format

`data/11410總.kml` is the hydrant dataset, converted from CSV.

### CSV Columns
```
消防栓編號 (Hydrant ID), 單位名稱 (Station), 種類 (Type), 區鄉鎮市名稱 (District),
消防栓位置 (Location), 經度 (Longitude), 緯度 (Latitude), 水公司單位名稱 (Water Company)
```

### KML Structure (After Conversion)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Fire Hydrants</name>
    <Placemark>
      <name>4479</name>                          <!-- Hydrant ID -->
      <description><![CDATA[
        消防栓編號: 4479<br>                    <!-- Hydrant ID -->
        自訂編號: <br>                          <!-- Custom ID (optional) -->
        單位名稱: 大里分隊<br>                  <!-- Fire Station -->
        種類: 地下<br>                          <!-- Type: 地上(above) / 地下(below) -->
        區鄉鎮市名稱: 大里區<br>                <!-- District -->
        消防栓位置: 國光路二段299號前<br>      <!-- Street address -->
        經度: 120.6803083<br>                    <!-- Longitude -->
        緯度: 24.10726247<br>                    <!-- Latitude -->
        水公司單位名稱: 大里服務所              <!-- Water utility -->
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

### Updating Hydrant Data

1. Place new CSV in the `kml/` directory
2. Run conversion script:
   ```bash
   python csv_to_kml.py
   ```
3. Copy generated `11410總.kml` to `modular/data/`
4. Delete `hydrants_cache.json` to force cache rebuild

---

## 📦 Build Executable

```bash
pyinstaller --onefile --console --name "FireHydrantBot" \
  --add-data "data/11410總.kml;data" \
  --add-data "leaflet_css.txt;." \
  --add-data "leaflet_js.txt;." \
  --hidden-import telegram --hidden-import telegram.ext \
  --hidden-import PIL --hidden-import PIL.Image \
  --hidden-import PIL.ImageDraw --hidden-import PIL.ImageFont \
  --hidden-import requests --hidden-import xml.etree.ElementTree \
  main.py
```

Output: `dist/FireHydrantBot.exe` (~28MB). Copy to any Windows PC and run.

---

## 🔧 Tech Stack

- **Python 3.11+**
- **python-telegram-bot** — Telegram Bot API
- **Pillow (PIL)** — Static map rendering
- **Leaflet.js** — Interactive HTML map (fully inlined, no CDN dependency)
- **OpenStreetMap** — Map tiles
- **ArcGIS Geocoder** — Taiwan address geocoding

---

## 📄 License

This project is for internal fire department use. Not open for commercial licensing.
