# -*- coding: utf-8 -*-
import json
import math
import io
import sys
import requests
from PIL import Image, ImageDraw, ImageFont
import xml.etree.ElementTree as ET
import re
import os
import urllib.parse
from math import log, tan, pi, cos, sinh, atan, floor

# ===== 自動偵測路徑（跨平台 + PyInstaller 支援） =====
import sys as _sys
if getattr(_sys, 'frozen', False):
    _BASE_DIR = _sys._MEIPASS
    _WRITE_DIR = os.path.dirname(os.path.abspath(_sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _WRITE_DIR = _BASE_DIR

MAP_DIR = os.environ.get('MAP_DIR') or _BASE_DIR

KML_CANDIDATES = [
    os.path.join(MAP_DIR, "data", "11410總.kml"),
    os.path.join(MAP_DIR, "11410總.kml"),
]
KML_PATH = None
for p in KML_CANDIDATES:
    if os.path.exists(p):
        KML_PATH = p
        break
if KML_PATH is None:
    KML_PATH = KML_CANDIDATES[0]

CACHE_PATH = os.path.join(_WRITE_DIR, "hydrants_cache.json")
OUTPUT_IMG_DEFAULT = os.path.join(_WRITE_DIR, "map_output.png")

# ===== 字型自動偵測 =====
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]
FONT_PATH = None
for fp in FONT_CANDIDATES:
    if os.path.exists(fp):
        FONT_PATH = fp
        break
if FONT_PATH is None:
    FONT_PATH = FONT_CANDIDATES[0]

# ===== 1. 載入消防栓資料 =====
def load_hydrants():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    tree = ET.parse(KML_PATH)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    placemarks = root.findall('.//kml:Placemark', ns)
    hydrants = []
    
    for pm in placemarks:
        name_el = pm.find('kml:name', ns)
        name = name_el.text.strip() if name_el is not None and name_el.text else ''
        coords_el = pm.find('.//kml:coordinates', ns)
        if coords_el is None or not coords_el.text:
            continue
        parts = coords_el.text.strip().split(',')
        if len(parts) < 2:
            continue
        lng = float(parts[0])
        lat = float(parts[1])
        desc_el = pm.find('kml:description', ns)
        desc = desc_el.text if desc_el is not None and desc_el.text else ''
        
        info = {'name': name, 'lat': lat, 'lng': lng}
        if desc:
            m = re.search(r'消防栓編號:\s*([^<\s]+)', desc)
            if m: info['id'] = m.group(1)
            m = re.search(r'自訂編號:\s*([^<\s]+)', desc)
            if m: info['custom_id'] = m.group(1)
            m = re.search(r'種類:\s*(\S+?)<br>', desc)
            if not m: m = re.search(r'種類:\s*(\S+)', desc)
            if m: info['type'] = m.group(1).replace('<br>消防栓蓋:', '').strip()
        hydrants.append(info)
    
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(hydrants, f, ensure_ascii=False)
    return hydrants

# ===== 2. 地址定位 =====
def geocode_arcgis(address):
    url = f"https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&singleLine={urllib.parse.quote(address)}&countryCode=TWN&maxLocations=1&outFields=*"
    try:
        r = requests.get(url, timeout=8)
        data = r.json()
        candidates = data.get('candidates', [])
        if candidates:
            loc = candidates[0]
            lat = loc['location']['y']
            lng = loc['location']['x']
            label = loc['attributes'].get('LongLabel', '')
            score = loc['score']
            return lat, lng, label, score
    except:
        pass
    return None, None, None, 0

def geocode_nominatim(address):
    strategies = [
        address,
        re.sub(r'[之\-]\d+號', '號', address) if re.search(r'[之\-]\d+號', address) else None,
    ]
    m = re.search(r'(\d+)號', address)
    if m:
        num = int(m.group(1))
        strategies.append(address.replace(f"{num}號", f"{num+2}號"))
        strategies.append(address.replace(f"{num}號", f"{num-2}號"))
    
    headers = {'User-Agent': 'FireHydrantBot/1.0'}
    for addr in strategies:
        if not addr: continue
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={requests.utils.quote(addr)}&countrycodes=tw&limit=1"
            resp = requests.get(url, headers=headers, timeout=5)
            data = resp.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon']), data[0].get('display_name',''), 80
        except:
            continue
    return None, None, None, 0

def geocode_address(address):
    lat, lng, label, score = geocode_arcgis(address)
    if lat and score >= 80:
        return lat, lng, f"ArcGIS ({label})"
    lat2, lng2, label2, _ = geocode_nominatim(address)
    if lat2:
        return lat2, lng2, f"Nominatim"
    m = re.search(r'(.+?[路街大道])(\d+)號', address)
    if m:
        simple = f"{m.group(1)}號"
        lat3, lng3, label3, _ = geocode_arcgis(simple)
        if lat3:
            return lat3, lng3, f"ArcGIS 退階 ({simple})"
    return None, None, None

# ===== 3. Haversine 距離計算 =====
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ===== 4. 地圖圖磚 =====
def composite_map(center_lat, center_lng, zoom, width=900, height=750):
    def to_tile(lat, lng, z):
        n = 2.0 ** z
        x = (lng + 180.0) / 360.0 * n
        y = (1.0 - log(tan(lat * pi / 180.0) + 1.0 / cos(lat * pi / 180.0)) / pi) / 2.0 * n
        return x, y
    
    tile_size = 256
    cx_f, cy_f = to_tile(center_lat, center_lng, zoom)
    num_x = width // tile_size + 3
    num_y = height // tile_size + 3
    start_x = floor(cx_f) - num_x // 2
    start_y = floor(cy_f) - num_y // 2
    
    img = Image.new('RGB', (num_x * tile_size, num_y * tile_size), (240, 240, 240))
    
    for dx in range(num_x):
        for dy in range(num_y):
            tx = start_x + dx
            ty = start_y + dy
            url = f"https://tile.openstreetmap.org/{zoom}/{tx}/{ty}.png"
            try:
                resp = requests.get(url, headers={'User-Agent': 'FireHydrantMap/1.0'}, timeout=5)
                if resp.status_code == 200:
                    tile = Image.open(io.BytesIO(resp.content))
                    img.paste(tile, (dx * tile_size, dy * tile_size))
            except:
                d = ImageDraw.Draw(img)
                d.rectangle([dx*tile_size, dy*tile_size, (dx+1)*tile_size, (dy+1)*tile_size], 
                           fill=(230, 230, 230), outline=(200, 200, 200))
    
    px = int((cx_f - start_x) * tile_size)
    py = int((cy_f - start_y) * tile_size)
    
    x1 = max(0, px - width // 2)
    y1 = max(0, py - height // 2)
    x2 = min(img.width, x1 + width)
    y2 = min(img.height, y1 + height)
    
    if x2 > img.width: x1 = img.width - width
    if y2 > img.height: y1 = img.height - height
    if x1 < 0: x1 = 0
    if y1 < 0: y1 = 0
    
    return img.crop((x1, y1, x1+width, y1+height))

def latlng_to_pixel(lat, lng, center_lat, center_lng, zoom):
    def f(lat, lng):
        n = 2.0 ** zoom
        x = (lng + 180.0) / 360.0 * n
        y = (1.0 - log(tan(lat * pi / 180.0) + 1.0 / cos(lat * pi / 180.0)) / pi) / 2.0 * n
        return x, y
    cx, cy = f(center_lat, center_lng)
    tx, ty = f(lat, lng)
    return int((tx - cx) * 256), int((ty - cy) * 256)

# ===== 5. 核心繪圖（共用） =====
def _draw_map_core(center_lat, center_lng, label, hydrants, output_path, trucks=None):
    """核心繪圖：給定中心座標、標籤、消防栓資料，可選多台消防車標記
    trucks: [{'lat': x, 'lng': y, 'label': '大里91'}, ...] or None"""
    print(f"📍 中心: {center_lat:.6f}, {center_lng:.6f} ({label})")
    print(f"📊 共 {len(hydrants)} 個消防栓")
    if trucks:
        print(f"🚒 消防車: {', '.join(t['label'] for t in trucks)}")
    
    # 計算距離，只取最近 100 支消防栓
    distances = []
    for h in hydrants:
        d = haversine(center_lat, center_lng, h['lat'], h['lng'])
        distances.append({**h, 'distance': d})
    distances.sort(key=lambda x: x['distance'])
    nearby = distances[:100]  # 只畫最近 100 支
    top5 = nearby[:5]
    
    # 決定 zoom（考慮所有消防車位置）
    max_dist = max([h['distance'] for h in top5])
    if trucks:
        for t in trucks:
            td = haversine(center_lat, center_lng, t['lat'], t['lng'])
            max_dist = max(max_dist, td)
    
    if max_dist < 150: zoom = 17
    elif max_dist < 350: zoom = 16
    elif max_dist < 700: zoom = 15
    elif max_dist < 1500: zoom = 14
    elif max_dist < 3000: zoom = 13
    else: zoom = 12
    
    print(f"🗺️ Zoom: {zoom}, 最近: {round(top5[0]['distance'])}m, 最遠: {round(top5[4]['distance'])}m")
    
    W, H = 900, 750
    map_img = composite_map(center_lat, center_lng, zoom, W, H)
    draw = ImageDraw.Draw(map_img)
    
    # 字型
    try:
        font_tiny = ImageFont.truetype(FONT_PATH, 14)
        font_small = ImageFont.truetype(FONT_PATH, 17)
        font_med = ImageFont.truetype(FONT_PATH, 21)
        font_large = ImageFont.truetype(FONT_PATH, 34)
        font_title = ImageFont.truetype(FONT_PATH, 24)
    except:
        font_tiny = font_small = font_med = font_large = font_title = ImageFont.load_default()
    
    # 先畫普通消防栓（小點，第 6~100 名）
    top5_set = {id(h) for h in top5}
    for h in nearby:
        if id(h) in top5_set:
            continue
        dx, dy = latlng_to_pixel(h['lat'], h['lng'], center_lat, center_lng, zoom)
        px, py = W//2 + dx, H//2 + dy
        if 0 <= px <= W and 0 <= py <= H:
            dot_r = 4
            draw.ellipse([px-dot_r, py-dot_r, px+dot_r, py+dot_r], fill='#e74c3c', outline='#ffffff')
    
    # 畫 top5 標記
    number_symbols = ['1', '2', '3', '4', '5']
    try:
        font_marker = ImageFont.truetype(FONT_PATH, 32)
    except:
        font_marker = font_large
    for i, h in enumerate(top5):
        dx, dy = latlng_to_pixel(h['lat'], h['lng'], center_lat, center_lng, zoom)
        px, py = W//2 + dx, H//2 + dy
        if not (0 <= px <= W and 0 <= py <= H):
            continue
        text = number_symbols[i]
        bbox = draw.textbbox((0, 0), text, font=font_marker)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((px - tw/2, py - th/2 - 1), text, fill='#e74c3c', font=font_marker)
    
    # ===== 消防車標記（多台） =====
    if trucks:
        try:
            font_truck = ImageFont.truetype(FONT_PATH, 18)
        except:
            font_truck = font_med
        
        for truck in trucks:
            tdx, tdy = latlng_to_pixel(truck['lat'], truck['lng'], center_lat, center_lng, zoom)
            tx, ty = W//2 + tdx, H//2 + tdy
            
            if not (0 <= tx <= W and 0 <= ty <= H):
                continue
            
            # 畫車身（紅色矩形）
            bw, bh = 36, 20
            x1, y1 = tx - bw//2, ty - bh//2
            x2, y2 = tx + bw//2, ty + bh//2
            draw.rounded_rectangle([x1, y1, x2, y2], radius=5, fill='#e74c3c', outline='#c0392b', width=2)
            
            # 車窗
            win_x1, win_y1 = tx - bw//2 + 4, ty - bh//2 + 3
            win_x2, win_y2 = tx - 2, ty + bh//2 - 3
            draw.rounded_rectangle([win_x1, win_y1, win_x2, win_y2], radius=2, fill='#f5b7b1')
            win2_x1, win2_y1 = tx + 2, ty - bh//2 + 3
            win2_x2, win2_y2 = tx + bw//2 - 4, ty + bh//2 - 3
            draw.rounded_rectangle([win2_x1, win2_y1, win2_x2, win2_y2], radius=2, fill='#f5b7b1')
            
            # 輪子
            wheel_r = 6
            draw.ellipse([tx - 10 - wheel_r, ty + bh//2 - wheel_r, tx - 10 + wheel_r, ty + bh//2 + wheel_r],
                        fill='#222', outline='#555')
            draw.ellipse([tx + 10 - wheel_r, ty + bh//2 - wheel_r, tx + 10 + wheel_r, ty + bh//2 + wheel_r],
                        fill='#222', outline='#555')
            
            # 標籤
            truck_text = f"🚒{truck['label']}"
            tbbox = draw.textbbox((0, 0), truck_text, font=font_truck)
            ttw = tbbox[2] - tbbox[0]
            pad = 4
            draw.rectangle([tx - ttw//2 - pad, y1 - 28, tx + ttw//2 + pad, y1 - 4],
                          fill=(0, 0, 0, 180))
            draw.text((tx - ttw//2, y1 - 26), truck_text, fill='#ff4444', font=font_truck)
    
    # 中心點標記（紅色星星）
    fx, fy = W//2, H//2
    import math as m
    star_r = 16
    points = []
    for i in range(10):
        angle = m.radians(-90 + i * 36)
        r2 = star_r if i % 2 == 0 else star_r * 0.4
        points.append((fx + r2 * m.cos(angle), fy + r2 * m.sin(angle)))
    draw.polygon(points, fill='#e74c3c', outline='#ffffff', width=1)
    
    # ===== 頂部資訊欄 =====
    title_text = '🔥 消防水源地圖'
    if trucks:
        truck_names = ','.join(t['label'] for t in trucks)
        title_text += f'  |  🚒 {truck_names}'
    
    draw.rectangle([0, 0, W, 52], fill=(0, 0, 0, 200))
    draw.text((12, 6), title_text, fill='#e74c3c', font=font_title)
    draw.text((12, 30), f'位置: {label}', fill='#bbb', font=font_tiny)
    draw.text((W-170, 12), f'縮放: Z{zoom}', fill='#777', font=font_tiny)
    draw.text((W-170, 30), f'顯示: {len(nearby)}支', fill='#777', font=font_tiny)
    
    # 存檔
    map_img.save(output_path, 'PNG')
    filesize = os.path.getsize(output_path) // 1024
    print(f"✅ 地圖已儲存: {output_path} ({filesize}KB)")
    
    # 導航連結
    nav_items = []
    for i, h in enumerate(top5):
        dist_m = round(h['distance'])
        dist_str = f"{dist_m}m" if dist_m < 1000 else f"{dist_m/1000:.1f}km"
        h_id = h.get('id', '') or '無編號'
        dest = f"{h['lat']},{h['lng']}"
        nav_url = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=driving"
        nav_items.append((i+1, h_id, dist_str, nav_url))
    
    print("---NAV_START---")
    for i, h_id, dist_str, nav_url in nav_items:
        print(f"NAV|{i}|{h_id}|{dist_str}|@@{nav_url}@@")
    print("---NAV_END---")
    
    return output_path, nav_items

# ===== 6. 公開 API =====
def draw_map(address, output_path=None):
    """地址查詢：輸入地址 → 地圖 + 5個最近消防栓"""
    if output_path is None:
        output_path = OUTPUT_IMG_DEFAULT
    
    print(f"🔍 查詢地址: {address}")
    hydrants = load_hydrants()
    
    result = geocode_address(address)
    if result[0] is None:
        print("❌ 找不到此地址")
        return None
    
    lat, lng, strategy = result
    print(f"✅ 定位成功 ({strategy})")
    return _draw_map_core(lat, lng, address, hydrants, output_path)

def draw_map_with_trucks(center_lat, center_lng, label, trucks, output_path=None):
    """多消防車地圖：固定中心 + 多台消防車標記 → 地圖 + 導航
    trucks: [{'lat': x, 'lng': y, 'label': '大里91'}, ...]"""
    if output_path is None:
        output_path = OUTPUT_IMG_DEFAULT
    
    hydrants = load_hydrants()
    return _draw_map_core(center_lat, center_lng, label, hydrants, output_path, trucks=trucks)

def draw_map_location(lat, lng, label, output_path=None, truck_label=None):
    """單車位置查詢（向後相容）"""
    if output_path is None:
        output_path = OUTPUT_IMG_DEFAULT
    
    hydrants = load_hydrants()
    trucks = [{'lat': lat, 'lng': lng, 'label': truck_label}] if truck_label else None
    return _draw_map_core(lat, lng, label, hydrants, output_path, trucks=trucks)

# ===== 7. 互動式 HTML 地圖 =====
HTML_OUTPUT_DEFAULT = os.path.join(_WRITE_DIR, "map_interactive.html")

# ===== Leaflet 內嵌快取（避免 CDN 依賴，手機 file:// 也能開） =====
_LEAFLET_CSS = None
_LEAFLET_JS = None

def _get_leaflet_assets():
    """載入 Leaflet CSS/JS，優先本地快取，無則下載"""
    global _LEAFLET_CSS, _LEAFLET_JS
    if _LEAFLET_CSS and _LEAFLET_JS:
        return _LEAFLET_CSS, _LEAFLET_JS
    
    css_path = os.path.join(_WRITE_DIR, "leaflet_css.txt")
    js_path = os.path.join(_WRITE_DIR, "leaflet_js.txt")
    
    # 嘗試讀取本地快取
    if os.path.exists(css_path) and os.path.exists(js_path):
        with open(css_path, 'r', encoding='utf-8') as f:
            _LEAFLET_CSS = f.read()
        with open(js_path, 'r', encoding='utf-8') as f:
            _LEAFLET_JS = f.read()
        return _LEAFLET_CSS, _LEAFLET_JS
    
    # 從 CDN 下載並快取
    try:
        import requests as _req
        _LEAFLET_CSS = _req.get('https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css', timeout=10).text
        _LEAFLET_JS = _req.get('https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js', timeout=10).text
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(_LEAFLET_CSS)
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write(_LEAFLET_JS)
    except:
        _LEAFLET_CSS = ''
        _LEAFLET_JS = ''
    
    return _LEAFLET_CSS, _LEAFLET_JS

def generate_interactive_map(center_lat, center_lng, label, trucks=None, output_path=None):
    """產生 Leaflet 互動式地圖 HTML（內嵌 Leaflet，手機 file:// 可開啟）"""
    if output_path is None:
        output_path = HTML_OUTPUT_DEFAULT
    
    hydrants = load_hydrants()
    leaflet_css, leaflet_js = _get_leaflet_assets()
    
    # 計算最近 5 個消防栓（從 100 支中取前 5）
    distances = []
    for h in hydrants:
        d = haversine(center_lat, center_lng, h['lat'], h['lng'])
        distances.append({**h, 'distance': d})
    distances.sort(key=lambda x: x['distance'])
    top5 = distances[:5]
    nearby_100 = distances[:100]
    
    # 收集所有需要顯示的座標（只用於 bounds，前5+所有消防車+中心）
    all_points = [(center_lat, center_lng)]
    if trucks:
        for t in trucks:
            all_points.append((t['lat'], t['lng']))
    for h in top5:
        all_points.append((h['lat'], h['lng']))
    
    # 建立消防栓 marker JS：前5個編號，第6~100個小圓點
    hydrant_js = []
    for i, h in enumerate(nearby_100):
        dist_m = round(h['distance'])
        dist_str = f"{dist_m}m" if dist_m < 1000 else f"{dist_m/1000:.1f}km"
        h_id = h.get('id', '') or '無編號'
        h_type = h.get('type', '')
        dest = f"{h['lat']},{h['lng']}"
        nav_url = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=driving"
        
        if i < 5:
            # 前5個：編號標記
            hydrant_js.append(f"""        var h{i} = L.circleMarker([{h['lat']}, {h['lng']}], {{
            radius: 12, fillColor: '#e74c3c', color: '#fff', weight: 2, fillOpacity: 0.9
        }}).addTo(map);
        h{i}.bindPopup('<b>消防栓 #{i+1}</b><br>編號: {h_id}<br>種類: {h_type}<br>距離: {dist_str}<br><a href="{nav_url}" target="_blank">🗺️ Google 導航</a>');
        L.marker([{h['lat']}, {h['lng']}], {{
            icon: L.divIcon({{className: 'hydrant-label', html: '<span>{i+1}</span>', iconSize: [24,24], iconAnchor: [12,12]}})
        }}).addTo(map);""")
        else:
            # 第6~100個：小圓點
            hydrant_js.append(f"""        L.circleMarker([{h['lat']}, {h['lng']}], {{
            radius: 5, fillColor: '#e74c3c', color: '#fff', weight: 1, fillOpacity: 0.7
        }}).addTo(map).bindPopup('<b>消防栓</b><br>編號: {h_id}<br>種類: {h_type}<br>距離: {dist_str}<br><a href="{nav_url}" target="_blank">🗺️ Google 導航</a>');""")
    
    # 建立消防車 marker JS
    truck_js = []
    if trucks:
        for t in trucks:
            tlabel = t['label'].replace("'", "\\'")
            truck_js.append(f"""        L.marker([{t['lat']}, {t['lng']}], {{
            icon: L.divIcon({{className: 'truck-marker', html: '<div class="truck-icon">🚒</div><div class="truck-label">{tlabel}</div>', iconSize: [70,50], iconAnchor: [35,45]}})
        }}).addTo(map).bindPopup('<b>🚒 {tlabel}</b><br>座標: {t["lat"]:.5f}, {t["lng"]:.5f}');""")
    
    center_label = label.replace("'", "\\'")
    bounds_js = ",\n".join(f"        [{lat}, {lng}]" for lat, lng in all_points)
    
    html = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0, user-scalable=yes">
<title>消防水源地圖</title>
<style>
LEAFLET_CSS_PLACEHOLDER
</style>
<style>
    html, body { margin: 0; padding: 0; height: 100%; width: 100%; }
    #map { height: 100%; width: 100%; }
    .hydrant-label span {
        display: flex; align-items: center; justify-content: center;
        background: #e74c3c; color: #fff; font-weight: bold;
        font-size: 14px; width: 24px; height: 24px;
        border-radius: 50%; border: 2px solid #fff;
        font-family: Arial, sans-serif;
    }
    .truck-marker { text-align: center; }
    .truck-icon { font-size: 32px; line-height: 1; }
    .truck-label {
        background: rgba(0,0,0,0.75); color: #ff4444;
        font-size: 12px; font-weight: bold; padding: 2px 6px;
        border-radius: 4px; white-space: nowrap;
        font-family: Arial, sans-serif;
    }
    .legend {
        position: absolute; bottom: 30px; left: 10px; z-index: 1000;
        background: rgba(0,0,0,0.75); color: #fff; padding: 10px 14px;
        border-radius: 8px; font-size: 13px; font-family: Arial, sans-serif;
        line-height: 1.8;
    }
    .legend span { display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
    .leaflet-popup-content { font-size: 14px; font-family: Arial, sans-serif; }
</style>
</head>
<body>
<div id="map"></div>
<div class="legend">
    <div><span style="background:#e74c3c;border:2px solid #fff;"></span> 消防栓</div>
    <div style="text-align:center;">🚒 消防車</div>
    <div style="text-align:center;">⭐ 火災地點</div>
</div>
<script>
LEAFLET_JS_PLACEHOLDER
</script>
<script>
    var map = L.map('map', {
        zoomControl: true,
        attributionControl: false
    }).setView([CENTER_LAT, CENTER_LNG], 16);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19
    }).addTo(map);
    
    var fireIcon = L.divIcon({
        className: 'fire-marker',
        html: '<div style="font-size:32px;text-align:center;">⭐</div>',
        iconSize: [40, 40],
        iconAnchor: [20, 20]
    });
    L.marker([CENTER_LAT, CENTER_LNG], {icon: fireIcon}).addTo(map)
     .bindPopup('<b>🔥 火災地點</b><br>CENTER_LABEL');
    
HYDRANT_JS
    
TRUCK_JS
    
    var bounds = L.latLngBounds([
BOUNDS_JS
    ]);
    map.fitBounds(bounds.pad(0.15));
    map.setMinZoom(12);
</script>
</body>
</html>"""
    
    # 填入動態內容
    html = html.replace('LEAFLET_CSS_PLACEHOLDER', leaflet_css)
    html = html.replace('LEAFLET_JS_PLACEHOLDER', leaflet_js)
    html = html.replace('CENTER_LAT', str(center_lat))
    html = html.replace('CENTER_LNG', str(center_lng))
    html = html.replace('CENTER_LABEL', center_label)
    html = html.replace('HYDRANT_JS', '\n'.join(hydrant_js))
    html = html.replace('TRUCK_JS', '\n'.join(truck_js))
    html = html.replace('BOUNDS_JS', bounds_js)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ 互動地圖已儲存: {output_path}")
    return output_path, top5

# ===== 主程式 =====
if __name__ == '__main__':
    if len(sys.argv) > 1:
        addr = ' '.join(sys.argv[1:])
        draw_map(addr)
    else:
        print("用法: python3 map_bot.py <地址>")
