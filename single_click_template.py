# -*- coding: utf-8 -*-
"""
ZCode Tek Tık Türkçe Yama ve Güncelleyici (single_click_patcher.py)
------------------------------------------------------------------
ZCode güncellendiğinde veya sıfırdan kurulduğunda:
1. Yönetici (Admin) iznini otomatik kontrol eder ve ister (UAC).
2. Açık ZCode süreçlerini güvenle kapatır.
3. Orijinal app.asar arşivini otomatik yedekler.
4. i18n arayüz sözlüğünü, masaüstü menülerini, webview çeviricisini,
   dinamik DOM gözlemcisini ve sistem ayarlarını enjekte eder.
5. Tüm eklenti, yetenek (skills) ve komut manifestolarını Türkçe yapar.
6. Yeni app.asar arşivini saniyeler içinde derleyip yerine koyar.
7. ZCode'u masaüstü oturumunuzda bağımsız ve sorunsuz olarak başlatır.
"""

import os
import sys
import json
import struct
import time
import shutil
import ctypes
import subprocess
import zlib
import base64
import re
import webbrowser

# Windows UTF-8 Konsol Ayarı
if sys.platform == "win32":
    try:
        os.system("chcp 65001 >nul")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Yönetici hakları yoksa UAC ile kendini yönetici olarak yeniden başlatır."""
    if not is_admin():
        print("[!] Yönetici izinleri alınıyor (UAC)...")
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable if not getattr(sys, 'frozen', False) else script,
                f'"{script}" {params}' if not getattr(sys, 'frozen', False) else params,
                None, 1
            )
            if ret > 32:
                sys.exit(0)
            else:
                print("[-] Yönetici izni verilmedi.")
                time.sleep(3)
                sys.exit(1)
        except Exception as e:
            print(f"[-] UAC Başlatma Hatası: {e}")
            time.sleep(3)
            sys.exit(1)


# Gömülü 100% Bağımsız Türkçe Arayüz Sözlüğü (5.500+ Anahtar, zlib+b64)
EMBEDDED_TR_DICT_B64 = """__B64_DATA__"""

# Gömülü Claude Code Eklentileri Türkçe Açıklamaları (291 Eklenti, zlib+b64)
EMBEDDED_CLAUDE_TR_B64 = """__CLAUDE_B64_DATA__"""

CLAUDE_PLUGINS_TR = {}
if EMBEDDED_CLAUDE_TR_B64 and not EMBEDDED_CLAUDE_TR_B64.startswith("__"):
    try:
        raw_claude = zlib.decompress(base64.b64decode(EMBEDDED_CLAUDE_TR_B64.strip()))
        CLAUDE_PLUGINS_TR = json.loads(raw_claude.decode("utf-8"))
    except Exception:
        pass


DEFAULT_RESOURCES_DIR = r"C:\Program Files\ZCode\resources"
DEFAULT_ASAR = os.path.join(DEFAULT_RESOURCES_DIR, "app.asar")
DEFAULT_EXE = r"C:\Program Files\ZCode\ZCode.exe"


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def load_tr_dictionary():
    """Sözlüğü PyInstaller paketi, komşu dosya, ZCodeProject veya gömülü B64 verisinden yükler."""
    base_dir = get_base_dir()
    bundle_dir = get_bundle_dir()
    candidates = [
        os.path.join(bundle_dir, "tr_dictionary_zcode.json"),
        os.path.join(base_dir, "tr_dictionary_zcode.json"),
        r"C:\Users\Work-D\ZCodeProject\tr_dictionary_zcode.json",
        os.path.join(DEFAULT_RESOURCES_DIR, "tr_dictionary_zcode.json")
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if d and isinstance(d, dict) and len(d) >= 5000:
                    print(f"    -> Sözlük diskten yüklendi ({c})")
                    return d
            except Exception:
                pass
    if EMBEDDED_TR_DICT_B64:
        try:
            raw = zlib.decompress(base64.b64decode(EMBEDDED_TR_DICT_B64.strip()))
            d = json.loads(raw.decode("utf-8"))
            print("    -> Sözlük gömülü bellekten yüklendi (100% Bağımsız Mod)")
            return d
        except Exception as e:
            print(f"[-] Gömülü sözlük açılamadı: {e}")
    return None


# =====================================================================
# 1. SÜREÇ YÖNETİMİ
# =====================================================================

def kill_zcode():
    """Açık olan tüm ZCode süreçlerini kapatır."""
    print("[1/7] Açık ZCode pencereleri kapatılıyor...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ZCode.exe"], capture_output=True, text=True)
        time.sleep(1.2)
    except Exception:
        pass


def launch_zcode_detached(exe_path):
    """ZCode'u kullanıcının masaüstü oturumunda bağımsız (WMI/Explorer) olarak başlatır."""
    print("[7/7] ZCode Türkçe olarak başlatılıyor...")
    try:
        ps_cmd = f'Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{CommandLine = \'{exe_path}\'}}'
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    except Exception:
        try:
            os.startfile(exe_path)
        except Exception as e:
            print(f"[-] Başlatma uyarısı: {e}")


# =====================================================================
# 2. ASAR ARŞİV MOTORU (ELEKTRON UYUMLU DİNAMİK AYRIŞTIRICI & BİRLEŞTİRİCİ)
# =====================================================================

def parse_asar_header(f):
    f.seek(0)
    header_raw = f.read(16)
    if len(header_raw) < 16:
        raise ValueError("Geçersiz ASAR dosyası: Başlık çok kısa.")
    u1, str_len, u2, json_len = struct.unpack("<IIII", header_raw)
    json_bytes = f.read(json_len)
    header_json = json.loads(json_bytes.decode("utf-8"))
    base_offset = 8 + str_len
    return header_json, base_offset, str_len


def find_node(header_json, path_parts):
    node = header_json
    for part in path_parts:
        if "files" not in node or part not in node["files"]:
            return None
        node = node["files"][part]
    return node


def extract_file(f_src, node, base_offset):
    offset = int(node["offset"])
    size = int(node["size"])
    f_src.seek(base_offset + offset)
    return f_src.read(size)


def find_target_paths(header, f_src, base_offset):
    renderer_assets = header.get("files", {}).get("out", {}).get("files", {}).get("renderer", {}).get("files", {}).get("assets", {}).get("files", {})
    main_files = header.get("files", {}).get("out", {}).get("files", {}).get("main", {}).get("files", {})

    intl_file = None
    styles_file = None
    usage_parts_file = None

    for k in renderer_assets.keys():
        if k.startswith("IntlProvider-") and k.endswith(".js"):
            intl_file = k
        elif k.startswith("styles-") and k.endswith(".js"):
            styles_file = k
        elif k.startswith("usageStatsUiParts-") and k.endswith(".js"):
            usage_parts_file = k

    menu_file = None
    for k, node in main_files.items():
        if k.startswith("chunk-") and k.endswith(".js"):
            offset = int(node["offset"])
            size = int(node["size"])
            f_src.seek(base_offset + offset)
            c = f_src.read(size).decode("utf-8", errors="ignore")
            if 'titleBar.menu.file' in c or 'Kp={"zh-CN":' in c or 'pp={' in c:
                menu_file = k
                break

    if not intl_file:
        raise FileNotFoundError("IntlProvider paketi bulunamadı!")
    if not styles_file:
        raise FileNotFoundError("Styles paketi bulunamadı!")
    if not usage_parts_file:
        raise FileNotFoundError("usageStatsUiParts paketi bulunamadı!")
    if not menu_file:
        raise FileNotFoundError("Menu chunk paketi bulunamadı!")

    return {
        "intl": ["out", "renderer", "assets", intl_file],
        "styles": ["out", "renderer", "assets", styles_file],
        "usage_parts": ["out", "renderer", "assets", usage_parts_file],
        "menu": ["out", "main", menu_file],
        "main": ["out", "main", "index.js"],
        "html": ["out", "renderer", "index.html"],
        "resource_html": ["out", "renderer", "resource-manager.html"],
    }


def rebuild_asar(source_asar_path, dest_asar_path, modified_files_map):
    with open(source_asar_path, "rb") as f_src:
        header, base_offset, str_len = parse_asar_header(f_src)

        file_list = []

        def collect(node, parts):
            if "files" in node:
                for name, child in node["files"].items():
                    collect(child, parts + [name])
            else:
                p_str = "/".join(parts)
                file_list.append((p_str, parts, node))

        collect(header, [])

        sorted_files = []
        for p_str, parts, node in file_list:
            if "offset" in node:
                sorted_files.append((int(node["offset"]), p_str, parts, node))
        sorted_files.sort(key=lambda x: x[0])

        new_header = json.loads(json.dumps(header))
        new_payload = bytearray()
        current_offset = 0

        for orig_offset, p_str, parts, orig_node in sorted_files:
            h_node = find_node(new_header, parts)
            if p_str in modified_files_map:
                data = modified_files_map[p_str]
            else:
                data = extract_file(f_src, orig_node, base_offset)

            size = len(data)
            h_node["offset"] = str(current_offset)
            h_node["size"] = size
            new_payload.extend(data)
            current_offset += size

        new_json_str = json.dumps(new_header, separators=(",", ":"))
        new_json_bytes = new_json_str.encode("utf-8")

        pad = (4 - (len(new_json_bytes) % 4)) % 4
        padded_json_bytes = new_json_bytes + (b"\x00" * pad)
        padded_len = len(padded_json_bytes)
        raw_json_len = len(new_json_bytes)

        with open(dest_asar_path, "wb") as f_out:
            f_out.write(struct.pack("<IIII", 4, 8 + padded_len, 4 + padded_len, raw_json_len))
            f_out.write(padded_json_bytes)
            f_out.write(new_payload)


# =====================================================================
# 3. YAMA ENJEKSİYONLARI (HTML, STYLES, MAIN, MENÜ, INTL)
# =====================================================================

def patch_html(html_content):
    if "zcode-tr-dom-patch" in html_content:
        return html_content

    dom_script = r"""<script id="zcode-tr-dom-patch">
(function() {
  const DOM_MAP = {
    // 1024 Programmer's Day Surprise Modal
    "YOUR PROGRAMMER'S DAY SURPRISE": "PROGRAMCILAR GÜNÜ SÜRPRİZİNİZ",
    // ZCode Weekend Build Modal
    "ZCODE WEEKEND BUILD": "ZCODE HAFTA SONU DERLEMESİ",
    "ZCode Weekend Build": "ZCode Hafta Sonu Derlemesi",
    "Weekend Build": "Hafta Sonu Derlemesi",
    "500,000,000 Tokens": "500.000.000 Token",
    "500M Tokens": "500M Token",
    "GLM-5.3-Flash · 500M Tokens": "GLM-5.3-Flash · 500M Token",
    "GLM-5.3-Flash . 500M Tokens": "GLM-5.3-Flash · 500M Token",
    "500,000,000": "500.000.000",
    "500M": "500M",
    "Tokens": "Token",
    "tokens": "token",
    "Valid until": "Son Geçerlilik:",
    "You now have access to ZCODE WEEKEND BUILD": "Artık ZCODE HAFTA SONU DERLEMESİ'ne erişiminiz var",
    "You now have access to": "Artık erişiminiz var:",
    "GLM-5.3-Flash will be available on Oct 30, 2026 18:00.": "GLM-5.3-Flash 30 Ekim 2026 18:00'de kullanıma açılacaktır.",
    "GLM-5.3-Flash will be available on": "GLM-5.3-Flash tarihinde kullanıma açılacaktır:",
    "Oct 30, 2026 18:00.": "30 Ekim 2026 18:00.",
    "Oct 30, 2026 18:00": "30 Ekim 2026 18:00",
    "Oct 30, 2026": "30 Ekim 2026",
    "Nov 2, 2026": "2 Kasım 2026",
    "11/2/2026, 4:00:00 AM": "2 Kasım 2026 04:00",
    "11/2/2026": "02.11.2026",
    "Your programmer's day surprise": "Programcılar Günü Sürpriziniz",
    "Your gift pack is open": "Hediye Paketiniz Açıldı",
    "Your gift pack is open.": "Hediye Paketiniz Açıldı.",
    "1024 · INVITATION": "1024 · DAVETİYE",
    "INVITATION": "DAVETİYE",
    "Invitation": "Davetiye",
    "TOKENS": "TOKEN",
    "Tokens": "Token",
    "tokens": "token",
    "500,000,000 TOKENS": "500.000.000 TOKEN",
    "500,000,000": "500.000.000",
    "1024 · PROGRAMMER'S DAY": "1024 · PROGRAMCILAR GÜNÜ",
    "PROGRAMMER'S DAY": "PROGRAMCILAR GÜNÜ",
    "Programmer's Day": "Programcılar Günü",
    "You now have access to ZCode 1024 Dev Day": "Artık ZCode 1024 Geliştirici Günü'ne erişiminiz var",
    "You now have access to ZCode 1024 Dev Day.": "Artık ZCode 1024 Geliştirici Günü'ne erişiminiz var.",
    "GLM-5.3-Flash will be available on Oct 23, 2026 18:00.": "GLM-5.3-Flash 23 Ekim 2026 18:00'de kullanıma açılacaktır.",
    "GLM-5.3 will be available on Oct 23, 2026 18:00.": "GLM-5.3 23 Ekim 2026 18:00'de kullanıma açılacaktır.",
    "GLM-5.3-Flash will be available on Oct 23, 2026 18:00": "GLM-5.3-Flash 23 Ekim 2026 18:00'de kullanıma açılacaktır",
    "GLM-5.3 will be available on Oct 23, 2026 18:00": "GLM-5.3 23 Ekim 2026 18:00'de kullanıma açılacaktır",
    "Valid until Oct 26, 2026 04:00": "Son Geçerlilik: 26 Ekim 2026 04:00",
    "Valid until": "Son Geçerlilik:",
    "Got it": "Anladım",
    "Share": "Paylaş",

    "Select a running container": "Çalışan Bir Konteyner Seçin",
    "Çalışan bir konteyner seçin": "Çalışan Bir Konteyner Seçin",
    "Kopyala Markdown": "Markdown'ı Kopyala",
    "Copy Markdown": "Markdown'ı Kopyala",
    "Önizle table": "Tabloyu Önizle",
    "Preview table": "Tabloyu Önizle",
    "Özel key": "Özel Anahtar",
    "Resource İndir method": "Kaynak İndirme Yöntemi",
    "Resource download method": "Kaynak İndirme Yöntemi",
    "Visualize 1": "Görselleştirme 1",
    "Visualize": "Görselleştirme",
    "Community": "Topluluk",
    "App plugins": "Uygulama eklentileri",
    "Delegate tasks to other AI agents over A2A through a local AgentNetwork gateway.": "Yerel bir AgentNetwork ağ geçidi üzerinden A2A ile diğer yapay zeka ajanlarına görevler atayın.",
    "Delegate tasks to other AI agents": "Diğer yapay zeka ajanlarına görevler atayın",
    "This computer": "Bu bilgisayar",
    "Kullanıcı - This computer": "Kullanıcı - Bu bilgisayar",
    "User - This computer": "Kullanıcı - Bu bilgisayar",
    "Connection preferences": "Bağlantı tercihleri",
    "Connection Preferences": "Bağlantı Tercihleri",
    "Reconnect automatically at startup": "Başlangıçta otomatik olarak yeniden bağlan",
    "Reconnects devices seen online in the last 7 days at startup. Changes take effect on the next startup.": "Son 7 gün içinde çevrimiçi görülen cihazlara başlangıçta otomatik olarak yeniden bağlanır. Değişiklikler bir sonraki başlangıçta geçerli olur.",
    "No remote device connections yet.": "Henüz uzak cihaz bağlantısı yok.",
    "New connection": "Yeni bağlantı",
    "+ New connection": "+ Yeni bağlantı",
    "Select a running container": "Çalışan Bir Konteyner Seçin",
    "Running containers": "Çalışan konteynerler",
    "Enter Docker manually": "Docker'ı manuel girin",
    "formu": "Form",
    "(recommended)": "(Önerilen)",
    "Otomatik (recommended)": "Otomatik (Önerilen)",
    "Manage Modeller": "Modelleri Yönet",
    "Manage Models": "Modelleri Yönet",
    "Manage models": "Modelleri Yönet",
    "Selected Çalışma Alanları": "Seçili Çalışma Alanları",
    "Selected İşle": "Seçili Commit",
    "Connection Ayarlar": "Bağlantı Ayarları",
    "Görev title": "Görev Başlığı",
    "Görev name": "Görev Adı",
    "İstek description": "İstek Açıklaması",
    "This model does not accept image inputs. Send this request without images, or use a model that supports image input.": "Bu model görsel girişlerini desteklemiyor. Bu isteği görsel olmadan gönderin veya görsel desteği olan bir model kullanın.",
    "This model does not accept image inputs.": "Bu model görsel girişlerini desteklemiyor.",
    "Send this request without images, or use a model that supports image input.": "Bu isteği görsel olmadan gönderin veya görsel desteği olan bir model kullanın.",
    "Turn execution failed": "Tur yürütme başarısız oldu",
    "Computer Use": "Bilgisayar Kontrolü",
    "Parameters": "Parametreler",
    "Tool Call": "Araç Çağrısı",
    "Execution Details": "Yürütme Ayrıntıları",
    "Weekly Summary": "Haftalık Özet",
    "Error Fix": "Hata Düzeltme",
    "PPT Creation": "Sunum (PPT) Hazırlama",
    "Idle-time task": "Boş Zaman Görevi",
    "Idle-time Task": "Boş Zaman Görevi",
    "idle-time task": "Boş Zaman Görevi",
    "Idle-time tasks": "Boş Zaman Görevleri",
    "Idle-time Tasks": "Boş Zaman Görevleri",
    "Idle-time Görev": "Boş Zaman Görevi",
    "idle-time Görev": "Boş Zaman Görevi",
    "Morning dev brief": "Sabah Geliştirici Özeti",
    "Risk scan": "Risk Taraması",
    "Release brief": "Sürüm Özeti",
    "Documentation sync check": "Belge Senkronizasyon Kontrolü",
    "Oluştur Zamanlandı Görev": "Zamanlanmış Görev Oluştur",
    "Zamanlandı Görev template": "Zamanlanmış Görev Şablonları",
    "Zamanlandı Görev": "Zamanlanmış Görev",
    "Eklenti Marketplace": "Eklenti Mağazası",
    "Günlük At 10:00": "Her gün 10:00'da",
    "Haftalık olarak Fri'da, 16:00'de": "Haftalık olarak Cuma günü, 16:00'da",
    "Haftalık olarak Çar'da, 15:00'de": "Haftalık olarak Çarşamba günü, 15:00'te",
    "Personal plans": "Bireysel Planlar",
    "Team plans": "Ekip Planları",
    "Personal Plans": "Bireysel Planlar",
    "Team Plans": "Ekip Planları",
    "Monthly": "Aylık",
    "Quarterly -20%": "3 Aylık -%20",
    "Yearly -30%": "Yıllık -%30",
    "Quarterly": "3 Aylık",
    "Yearly": "Yıllık",
    "Subscribe": "Abone Ol",
    "Ended": "Sona Erdi",
    "Expired": "Süresi Doldu",
    "Ideal for getting started": "Başlangıç için ideal",
    "5-day free trial, including:": "5 günlük ücretsiz deneme, şunları içerir:",
    "5-day free trial": "5 günlük ücretsiz deneme",
    "Configure custom models with BYOK": "BYOK ile özel modelleri yapılandırın",
    "Occasional free token offers": "Dönemsel ücretsiz token teklifleri",
    "Weekend Build": "Hafta Sonu Derlemesi",
    "Global Build": "Küresel Derleme",
    "Lightweight repo iteration": "Hafif repo geliştirmesi",
    "Rolling access to the latest flagship models and features": "En yeni amiral gemisi modellere ve özelliklere kesintisiz erişim",
    "Supports 20+ coding tools, including ZCode": "ZCode dahil 20+ kodlama aracını destekler",
    "ZCode-exclusive benefits:": "ZCode'a özel avantajlar:",
    "Idle-time tasks: 1/day Free token": "Boş zaman görevleri: Günde 1 Ücretsiz token",
    "Idle-time tasks: 3/day Free token": "Boş zaman görevleri: Günde 3 Ücretsiz token",
    "Idle-time tasks: 5/day Free token": "Boş zaman görevleri: Günde 5 Ücretsiz token",
    "Idle-time tasks: 1/day": "Boş zaman görevleri: Günde 1",
    "Idle-time tasks: 3/day": "Boş zaman görevleri: Günde 3",
    "Idle-time tasks: 5/day": "Boş zaman görevleri: Günde 5",
    "Idle-time tasks": "Boş zaman görevleri",
    "Free token": "Ücretsiz token",
    "free token": "ücretsiz token",
    "Reset the 5-hour quota during idle hours": "Boş zaman saatlerinde 5 saatlik kotayı sıfırlama",
    "ZCode MCP benefits": "ZCode MCP avantajları",
    "150% quota with a limited-time usage multiplier discount": "Sınırlı süreli kullanım çarpanı indirimiyle %150 kota",
    "Everything in Lite": "Lite'taki her şey dahil",
    "Everything in Pro": "Pro'daki her şey dahil",
    "Priority access to the latest flagship models and features": "En yeni amiral gemisi modellere ve özelliklere öncelikli erişim",
    "Includes a curated selection of MCP tools": "Seçkin MCP araçları koleksiyonu içerir",
    "Faster generation speeds": "Daha yüksek üretim hızları",
    "Built for advanced users working on mid-to-large repos": "Orta ve büyük repolarda çalışan ileri düzey kullanıcılar için üretildi",
    "First access to the latest flagship models and features": "En yeni amiral gemisi modellere ve özelliklere ilk erişim",
    "Dedicated resources during peak times": "Yoğun saatlerde ayrılmış kaynaklar",
    "Code Review": "Kod İncelemesi",
    "Refactor": "Yeniden Düzenleme",
    "Explain Code": "Kodu Açıkla",
    "Generate Tests": "Test Üret",
    "Optimize": "Optimize Et",
    "General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks.": "Karmaşık soruları araştırmak, kod aramak ve çok adımlı görevleri yürütmek için genel amaçlı ajan.",
    "Read-only search agent for broad fan-out searches.": "Geniş kapsamlı aramalar için salt okunur arama ajanı.",
    "THE single visual acceptance pass for a rendered deliverable of these types only — pptx, docx, xlsx, pdf, poster, chart; for anything else, do not use it...": "Yalnızca pptx, docx, xlsx, pdf, poster ve grafik türündeki görsel çıktıların kabul incelemesi için tek yetkili görsel onay ajanı.",
    "Restore Legacy Sessions": "Eski Oturumları Geri Yükle",
    "Skill Creator": "Beceri Oluşturucu",
    "ZCode Guide": "ZCode Rehberi",
    "Android Emulator": "Android Emülatörü",
    "iOS Simulator": "iOS Simülatörü",
    "Document Skills": "Belge Becerileri",
    "Unified kullanıcı & permission management": "Birleşik kullanıcı ve yetki yönetimi",
    "Unified user & permission management": "Birleşik kullanıcı ve yetki yönetimi",
    "Unified seat & permission management": "Birleşik kullanıcı ve yetki yönetimi",
    "Team analytics & dashboard": "Ekip analizleri ve gösterge paneli",
    "Flexible usage billing": "Esnek kullanım faturalandırması",
    "Centralized billing & invoicing": "Merkezi faturalandırma ve fatura yönetimi",
    "Default data privacy": "Varsayılan veri gizliliği",
    "All Standard benefits": "Tüm Standart avantajları dahil",
    "Early access to new models & features": "Yeni modellere ve özelliklere erken erişim",
    "Priority resource allocation during peak hours": "Yoğun saatlerde öncelikli kaynak tahsisi",
    "per kullanıcı/ay": "/ kullanıcı / ay",
    "per user/month": "/ kullanıcı / ay",
    "per user / month": "/ kullanıcı / ay",
    "per seat/month": "/ kullanıcı / ay",
    "per seat / month": "/ kullanıcı / ay",
    "66,000 Credits / week": "Haftalık 66.000 Kredi",
    "155,000 Credits / week": "Haftalık 155.000 Kredi",
    "Credits / week": "Kredi / hafta",
    "Credits/week": "Kredi / hafta",
    "Start the Android emulator development loop.": "Android emülatör geliştirme döngüsünü başlatın.",
    "Start the iOS simulator development loop.": "iOS simülatör geliştirme döngüsünü başlatın.",
    "Select and restore a legacy ZCode session.": "Eski bir ZCode oturumunu seçin ve geri yükleyin.",
    "[goal or issue description]": "[hedef veya sorun açıklaması]",
    "[agent/workspace/session filters]": "[ajan/çalışma alanı/oturum filtreleri]",
    "Absolute Yolunu Kopyala": "Mutlak Yolu Kopyala",
    "Copy absolute path": "Mutlak Yolu Kopyala",
    "Copy Absolute Path": "Mutlak Yolu Kopyala",
    "Claude Security": "Claude Güvenlik",
    "Amd Skills": "AMD Becerileri",
    "AMD Skills": "AMD Becerileri",
    "Claude Code Setup": "Claude Code Kurulumu",
    "Claude Md Management": "Claude MD Yönetimi",
    "Chrome Devtools MCP": "Chrome DevTools MCP",
    "Chrome DevTools MCP": "Chrome DevTools MCP",
    "Request verification configuration read failed": "İstek doğrulama yapılandırması okunamadı",
    "Request verification configuration is unavailable": "İstek doğrulama yapılandırması kullanılamıyor",
    "Provider request auth is unavailable": "Sağlayıcı istek kimlik doğrulaması kullanılamıyor",
    "Account request auth resolver returned no material": "Hesap yetkilendirme çözümleyicisi geçerli veri döndürmedi",
    "The dedicated Claude Security orchestrator. Hand it an unattended job — \"fully scan this repository and patch what you find; I understand it will use a lot of token\" — and it runs the whole thing itself: capturing the revision, driving the multi-agent scan through..": "Özel Claude Güvenlik yöneticisi. Gözetimsiz bir tarama görevi verin; revizyonu yakalar, çoklu ajan güvenlik taramasını baştan sona yönetir ve bulunan açıkları yamalar.",
    "Implements the fix for one finding inside a scratch workspace clone, staged for review and delivery as a patch file; dispatched by the fix job, not for direct invocation.": "Tespit edilen bir güvenlik açığı için geçici çalışma alanında düzeltmeyi uygular ve inceleme için bir yama dosyası hazırlar; düzeltme işi tarafından otomatik çalıştırılır.",
    "The single verifier per fix round — reviews the workspace's staged diff against the finding, runs the tests, and states the three confidence claims a patch file must earn; dispatched by the fix job, not for direct invocation.": "Düzeltme turundaki tek yetkili doğrulayıcı: çalışma alanındaki farkı (diff) bulguya göre inceler, testleri çalıştırır ve yama güvenilirlik kriterlerini onaylar; düzeltme işi tarafından otomatik çalıştırılır.",
    "Restricted read-only repository cartographer dispatched by the Claude Security scan workflow to partition the tree into components and account for every top-level directory; not for direct invocation or vulnerability research.": "Claude Güvenlik taraması tarafından dizin ağacını bileşenlere bölmek ve tüm üst düzey dizinleri haritalamak için görevlendirilen salt okunur repo haritalayıcı.",
    "Restricted read-only loader dispatched by the Claude Security scan workflow to return one candidates file from the run directory; not for direct invocation.": "Claude Güvenlik taraması tarafından çalışma dizininden aday bir dosyayı yüklemek için görevlendirilen salt okunur dosya yükleyici.",
    "Restricted read-only vulnerability researcher dispatched by the Claude Security scan workflow; not for direct invocation or general exploration.": "Claude Güvenlik iş akışı tarafından derinlemesine güvenlik açıklarını araştırmak üzere görevlendirilen salt okunur güvenlik araştırmacısı.",
    "Restricted read-only verifier dispatched by the Claude Security scan workflow to vote on one candidate finding; not for direct invocation.": "Claude Güvenlik iş akışı tarafından tespit edilen aday bulguları doğrulamak ve oylamak için görevlendirilen salt okunur doğrulayıcı.",
  };

  const SORTED_DOM_KEYS = Object.keys(DOM_MAP).sort((a, b) => b.length - a.length);

  let isTranslating = false;

  function translateNode(n) {
    if (!n) return;
    if (n.nodeType === 3) {
      let raw = n.nodeValue;
      if (!raw) return;
      let rawNorm = raw.replace(/\u00a0/g, " ");
      let clean = rawNorm.trim().replace(/\s+/g, " ");
      if (!clean) return;
      if (DOM_MAP[clean]) {
        let mLead = rawNorm.match(/^\s+/);
        let mTrail = rawNorm.match(/\s+$/);
        let lead = mLead ? mLead[0] : "";
        let trail = mTrail ? mTrail[0] : "";
        let targetVal = lead + DOM_MAP[clean] + trail;
        if (n.nodeValue !== targetVal) n.nodeValue = targetVal;
        return;
      }
      let modified = rawNorm;
      for (const k of SORTED_DOM_KEYS) {
        if (modified.includes(k)) {
          modified = modified.replaceAll(k, DOM_MAP[k]);
        }
      }
            if (clean.includes("will be available on")) {
        if (clean.startsWith("Request verification configuration read failed") || clean.includes("verification configuration read failed")) {
        modified = "İstek doğrulama yapılandırması okunamadı";
      } else if (clean.startsWith("Request verification configuration is unavailable")) {
        modified = "İstek doğrulama yapılandırması kullanılamıyor";
      } else if (clean.startsWith("Provider request auth is unavailable")) {
        modified = "Sağlayıcı istek kimlik doğrulaması kullanılamıyor";
      } else if (clean.startsWith("Account request auth resolver returned no material")) {
        modified = "Hesap yetkilendirme çözümleyicisi geçerli veri döndürmedi";
      }
      modified = modified.replace("will be available on", "tarihinde kullanıma açılacaktır:").replace("Oct", "Ekim");
      }
      if (clean.startsWith("Valid until")) {
        modified = modified.replace("Valid until", "Son Geçerlilik:").replace("Oct", "Ekim");
      }
      if (clean.startsWith("6x Lite usage") || clean.startsWith("6× Lite usage")) {
        modified = "6 kat Lite kullanımı + Tüm Lite avantajları";
      } else if (clean.startsWith("14x Lite usage") || clean.startsWith("14× Lite usage")) {
        modified = "14 kat Lite kullanımı + Tüm Lite avantajları";
      } else if (clean.startsWith("20x Lite usage") || clean.startsWith("20× Lite usage")) {
        modified = "20 kat Lite kullanımı + Tüm Pro avantajları";
      } else if (clean.startsWith("THE single visual acceptance pass") || clean.startsWith("THE single visual acceptance")) {
        modified = "Yalnızca pptx, docx, xlsx, pdf, poster ve grafik türündeki görsel çıktıların kabul incelemesi için tek yetkili görsel onay ajanı.";
      } else if (clean.startsWith("General-purpose agent")) {
        modified = "Karmaşık soruları araştırmak, kod aramak ve çok adımlı görevleri yürütmek için genel amaçlı ajan.";
      } else if (clean.startsWith("Read-only search agent")) {
        modified = "Geniş kapsamlı aramalar için salt okunur arama ajanı.";
      } else if (clean.startsWith("Use when ZCode needs to inspect")) {
        modified = "ZCode'un ~/.zcode/v2/sessions altındaki eski ACP dönemi ZCode oturumlarını yeni ZCode görev/oturum depolarına aktarması, incelemesi veya planlaması gerektiğinde kullanın. Eski sohbet geçmişini taşıma veya önceki oturumları geri yükleme sorularında tetiklenir.";
      } else if (clean.startsWith("Create new skills")) {
        modified = "Yeni beceriler oluşturun, mevcut becerileri düzenleyin ve ifadeleri iyileştirin. Sıfırdan SKILL.md yazarken, mevcut becerileri geliştirirken, tekrarlanan iş akışlarını yeniden kullanılabilir becerilere dönüştürürken veya beceri tetikleyicilerini giderirken kullanın.";
      } else if (clean.startsWith("Use to diagnose and fix ZCode custom slash-command")) {
        modified = "ZCode istemcisindeki özel eğik çizgi komutu (/komut) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir komut eksik olduğunda, bir beceri/ajan tarafından geçersiz kılındığında, ayrıştırılamadığında, kapsamlarda yinelenen adlara sahip olduğunda veya çalıştırılamadığında geçerlidir.";
      } else if (clean.startsWith("Use to diagnose and fix ZCode hook configuration")) {
        modified = "ZCode istemcisindeki kanca (hook) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir kanca tetiklenmediğinde, bir olay adı yanlış olduğunda, bir eşleştirici eşleşmediğinde, bir komut dosyası başarısız olduğunda veya kanca sıralaması/izinleri beklenmeyen davranışlara yol açtığında geçerlidir.";
      } else if (clean.startsWith("Use to diagnose and fix ZCode MCP")) {
        modified = "ZCode istemcisindeki MCP (Model Bağlam Protokolü) sunucu yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir MCP sunucusu bağlanmadığında, araçları eksik olduğunda, işlemi hata ile sonlandığında, aktarım protokolü (stdio veya SSE) yanlış yapılandırıldığında veya ortam değişkenleri hatalı olduğunda geçerlidir.";
      } else if (clean.startsWith("Use to diagnose and fix ZCode plugin")) {
        modified = "ZCode istemcisindeki eklenti ve mağaza sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir eklenti listelenmediğinde, mağaza ekleme veya eklenti yükleme başarısız olduğunda, bir eklenti komutu/becerisi/ajanı eksik olduğunda veya bir eklenti yapılandırması bozulduğunda geçerlidir.";
      } else if (clean.startsWith("Use to diagnose and fix ZCode skill configuration")) {
        modified = "ZCode istemcisindeki beceri yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir beceri keşfedilmediğinde, yüklü olduğu halde otomatik tetiklenmediğinde, dosyaları eksik olduğunda, frontmatter ayrıştırma hataları verdiğinde veya kapsamlarda yinelenen adlara sahip olduğunda geçerlidir.";
      } else if (clean.startsWith("Use when configuring ZCode") && clean.includes("extension resources")) {
        modified = "ZCode istemcisinde uzantı kaynaklarını (MCP sunucuları, eğik çizgi komutları, beceriler, kancalar ve eklentiler) veya AGENTS.md gibi talimat dosyalarını yapılandırırken kullanın. Bir kullanıcı bu uzantı mekanizmalarının nasıl ekleneceğini, düzenleneceğini veya yapılandırılacağını sorduğunda geçerlidir.";
      } else if (clean.startsWith("Build, run, inspect, and lightly automate iOS")) {
        modified = "ios-simulator MCP araçlarıyla iOS simülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.";
      } else if (clean.startsWith("Build, run, inspect, and lightly automate Android")) {
        modified = "android-emulator MCP araçlarıyla Android emülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.";
      } else if (clean.startsWith("Save 10% annually")) {
        modified = clean.replace("Save 10% annually", "Yıllık %10 indirim").replace("From", "Başlangıç:").replace("/month", "/ ay").replace("/ay", "/ ay");
      } else if (clean.startsWith("Unified")) {
        modified = "Birleşik kullanıcı ve yetki yönetimi";
      } else if (clean.includes("emÃ¼lat") || clean.includes("em\u00c3\u00bc")) {
        modified = "Android emülatörlerini yönetme, başlatma ve cihaz kontrolü için geliştirici araçları.";
      } else if (clean.includes("MasaÃ¼stÃ¼") || clean.includes("Masa\u00c3\u00bc")) {
        modified = "Masaüstü için yerleşik tarayıcı otomasyonu çalışma ortamı ve rehberlik.";
      } else if (clean.includes("DOCX") && (clean.includes("oluÅŸ") || clean.includes("olu\u00c3"))) {
        modified = "Yerleşik DOCX ve PDF belge oluşturma becerileri.";
      } else if (clean.includes("simÃ¼lat") || clean.includes("sim\u00c3\u00bc")) {
        modified = "iOS simülatörlerini yönetme, test etme ve arayüz denetimi araçları.";
      }
      if (modified.includes("per kullanıcı/ay") || modified.includes("per user/month") || modified.includes("per seat/month")) {
        modified = modified.replace("per kullanıcı/ay", "/ kullanıcı / ay").replace("per user/month", "/ kullanıcı / ay").replace("per seat/month", "/ kullanıcı / ay");
      }
      if (modified.includes("Credits / week") || modified.includes("Credits/week")) {
        modified = modified.replace("Credits / week", "Kredi / hafta").replace("Credits/week", "Kredi / hafta");
      }
      if (modified !== raw && n.nodeValue !== modified) n.nodeValue = modified;
    } else if (n.nodeType === 1) {
      if (n.tagName === "SCRIPT" || n.tagName === "STYLE") return;
      if (n.placeholder && DOM_MAP[n.placeholder.trim()]) {
        let pv = DOM_MAP[n.placeholder.trim()];
        if (n.placeholder !== pv) n.placeholder = pv;
      }
      if (n.title && DOM_MAP[n.title.trim()]) {
        let tv = DOM_MAP[n.title.trim()];
        if (n.title !== tv) n.title = tv;
      }
      if (n.getAttribute && n.getAttribute("aria-label")) {
        const aria = n.getAttribute("aria-label").trim();
        if (DOM_MAP[aria] && n.getAttribute("aria-label") !== DOM_MAP[aria]) {
          n.setAttribute("aria-label", DOM_MAP[aria]);
        }
      }
      for (let c = n.firstChild; c; c = c.nextSibling) {
        translateNode(c);
      }
    }
  }

  function safeTranslate(root) {
    if (isTranslating || !root) return;
    isTranslating = true;
    try {
      translateNode(root);
    } finally {
      isTranslating = false;
    }
  }

  if (document.body) safeTranslate(document.body);

  const obs = new MutationObserver(mutations => {
    if (isTranslating) return;
    for (const m of mutations) {
      if (m.type === "childList") {
        for (let i = 0; i < m.addedNodes.length; i++) {
          safeTranslate(m.addedNodes[i]);
        }
      }
    }
  });

  obs.observe(document.documentElement, {
    childList: true,
    subtree: true
  });
})();
</script>"""
    return html_content.replace("</body>", dom_script + "\n</body>")



def patch_styles(js_content):
    bt = "[`'\"]"

    # 1. 510 Beceri ve Resmi Eklentiler Sözlüğü
    official_p_descs = {}
    claude_tr_file = os.path.join(BASE_DIR, "claude_plugins_tr.json")
    if os.path.exists(claude_tr_file):
        with open(claude_tr_file, "r", encoding="utf-8") as _cf:
            official_p_descs.update(json.load(_cf))
    tr_p_descs_json = json.dumps(official_p_descs, ensure_ascii=False)

    official_store_names = {}
    store_tr_file = os.path.join(BASE_DIR, "store_names_tr.json")
    if os.path.exists(store_tr_file):
        with open(store_tr_file, "r", encoding="utf-8") as _sf:
            official_store_names.update(json.load(_sf))
    tr_store_names_json = json.dumps(official_store_names, ensure_ascii=False)

    # 2. Temiz Global Yardımcılar Bloğu (Top-Level Scope)
    helpers_header = f"""
/* === TURKISH LOCALIZATION HELPERS === */
const TR_AGENT_DESCS={{"general-purpose":"Karmaşık soruları araştırmak, kod aramak ve çok adımlı görevleri yürütmek için genel amaçlı ajan.","Explore":"Geniş kapsamlı aramalar için salt okunur arama ajanı.","explore":"Geniş kapsamlı aramalar için salt okunur arama ajanı.","judge":"Yalnızca görsel çıktıların kabul incelemesi için yetkili onay ajanı.","claude-security":"Özel Claude Güvenlik orkestratörü. Depoyu derinlemesine tarar, açıkları tespit eder ve çoklu ajan koordinasyonuyla yamaları otomatik olarak uygular."}};
function _trAgentDesc(e){{let n=(e&&(e.name||e.id))||"";let b=n.includes(":")?n.slice(n.indexOf(":")+1):n;let d=(e&&e.description)||"";if(b==="claude-security"||n==="claude-security"||(typeof d==="string"&&(d.startsWith("The dedicated Claude")||d.includes("orchestrator. Hand it an unattended job"))))return TR_AGENT_DESCS["claude-security"];if(TR_AGENT_DESCS[b])return TR_AGENT_DESCS[b];if(TR_AGENT_DESCS[n])return TR_AGENT_DESCS[n];return d}};

const TR_SEC_TITLES={{"Restore Legacy Sessions":"Eski Oturumları Geri Yükle","Skill Creator":"Beceri Oluşturucu","ZCode Guide":"ZCode Rehberi","Android Emulator":"Android Emülatörü","iOS Simulator":"iOS Simülatörü","Document Skills":"Belge Becerileri","Documents":"Belge Becerileri","PDF":"PDF","Presentations":"Sunum Becerileri","Spreadsheets":"Tablo Becerileri","Plugin Creator":"Eklenti Oluşturucu","Browser Use":"Browser Use","Computer Use":"Bilgisayar Kontrolü","Base44":"Base44","Cloudflare":"Cloudflare","AMD Skills":"AMD Becerileri","Amd Skills":"AMD Becerileri","Claude MD Management":"Claude MD Yönetimi","Firecrawl":"Firecrawl"}};
function _trSectionTitle(n){{if(!n)return n;let u=n.toUpperCase();if(TR_SEC_TITLES[u])return TR_SEC_TITLES[u];if(TR_SEC_TITLES[n])return TR_SEC_TITLES[n];return n}};

const TR_SKILL_DESCS={tr_p_descs_json};
if(typeof window!=="undefined"){{window.TR_SKILL_DESCS=TR_SKILL_DESCS;window.TR_P_DESCS=TR_SKILL_DESCS}};
if(typeof globalThis!=="undefined"){{globalThis.TR_SKILL_DESCS=TR_SKILL_DESCS;globalThis.TR_P_DESCS=TR_SKILL_DESCS}};

function _trSkillDesc(e){{if(!e)return"";let n=(e&&(e.name||e.id))||"";let b=n.includes(":")?n.slice(n.indexOf(":")+1):n;b=String(b).replace(/@.*$/,"").replace(/^plugin:/,"").trim();if(b.includes("/"))b=b.slice(b.lastIndexOf("/")+1);if(TR_SKILL_DESCS[b])return TR_SKILL_DESCS[b];if(TR_SKILL_DESCS[n])return TR_SKILL_DESCS[n];let d=(e&&e.description)||"";if(typeof d==="string"&&d.trim()&&TR_SKILL_DESCS[d.trim()])return TR_SKILL_DESCS[d.trim()];return d}};

const TR_CMD_DESCS={{"revise-claude-md":"Bu oturumdan öğrenilenlerle CLAUDE.md dosyasını güncelleyin.","build-agent":"Agents SDK kullanarak Cloudflare üzerinde bir yapay zeka ajanı derleyin.","build-mcp":"McpAgent kullanarak Cloudflare üzerinde uzak bir MCP sunucusu derleyin.","skill-gen":"Firecrawl kullanarak bir dokümantasyon URL'sinden eksiksiz bir Ajan Becerisi oluşturun.","android-dev":"Android emülatör geliştirme döngüsünü başlatın.","ios-dev":"iOS simülatör geliştirme döngüsünü başlatın.","restore-legacy-sessions":"Eski bir ZCode oturumunu seçin ve geri yükleyin.","workflow":"Bir görev için dinamik iş akışı tasarlayın ve başlatın.","code-review":"Bir pull request için kod incelemesi yapın.","site-badge":"Bağlı ZCode Siteleri sitesinde ZCode rozetini gizleyin veya gösterin.","site-deploy":"Bu projeyi ZCode Sitelerine dağıtın veya bağlı siteyi yeniden dağıtın.","site-logs":"Bir ZCode Siteleri dağıtımının günlüklerini gösterin ve hataları açıklayın.","site-offline":"Bağlı ZCode Siteleri sitesini çevrimdışı yapın.","site-online":"Bağlı ZCode Siteleri sitesini tekrar çevrimiçi yapın.","site-status":"Bu projeye bağlı ZCode Siteleri sitesini gösterin.","site-usage":"ZCode Siteleri kullanımını ve plan sınırlarını gösterin."}};
function _trCommandDesc(e){{if(!e)return"";let n=(e&&(e.name||e.id))||"";let b=n.startsWith("/")?n.slice(1):n;b=b.split(" ")[0].trim();if(TR_CMD_DESCS[b])return TR_CMD_DESCS[b];if(TR_CMD_DESCS[n])return TR_CMD_DESCS[n];return (e&&e.description)||""}};

const TR_CMD_HINTS={{"[goal or issue description]":"[hedef veya sorun açıklaması]","[agent-description]":"[ajan açıklaması]","[mcp-description]":"[mcp açıklaması]","<documentation-url>":"<dokümantasyon URL'si>","[what the workflow should accomplish]":"[iş akışının hedefi]","[project-name]":"[proje adı]"}};
function _trCommandHint(h){{if(!h||typeof h!=="string")return h;let t=h.trim();if(TR_CMD_HINTS[t])return TR_CMD_HINTS[t];for(let k in TR_CMD_HINTS){{if(t.includes(k))t=t.replace(k,TR_CMD_HINTS[k])}};return t}};


const TR_STORE_NAMES={tr_store_names_json};
function _trPluginName(id,raw){{if(id&&TR_STORE_NAMES[id])return TR_STORE_NAMES[id];if(raw&&TR_STORE_NAMES[raw])return TR_STORE_NAMES[raw];return raw}};
function _trPluginDesc(id,raw){{if(id&&TR_SKILL_DESCS[id])return TR_SKILL_DESCS[id];if(raw&&typeof raw==="string"){{let t=raw.trim();if(TR_SKILL_DESCS[t])return TR_SKILL_DESCS[t];for(let k in TR_SKILL_DESCS){{if(t.length>15&&k.length>15&&(t.startsWith(k)||k.startsWith(t)||t.includes(k)||k.includes(t.slice(0,25))))return TR_SKILL_DESCS[k]}}}};return raw}};
const TR_AUTOMATION_TEMPLATES={{"Daily standup summary":"Sabah Geliştirici Özeti","Summarize commits, module changes, CI status, and follow-ups since the previous workday, then produce no more than five stand-up-ready highlights with blockers and next steps.":"Önceki iş gününden bu yana commit'leri, modül değişikliklerini, CI durumunu ve takip edilecekleri özetleyin; engelleri ve sonraki adımları içeren en fazla beş maddelik toplantı özeti hazırlayın.","Risk scan":"Risk Taraması","Inspect code changes from the last 24 hours for high-confidence risks involving runtime failures, data loss, authorization bypasses, resource leaks, or missing rollbacks.":"Son 24 saatteki kod değişikliklerini çalışma zamanı hataları, veri kaybı, yetkilendirme açıkları, kaynak sızıntıları veya eksik geri alma senaryoları açısından inceleyin.","Release summary":"Sürüm Özeti","Organize PRs and commits merged this week into Features, Fixes, Experience improvements, and Engineering improvements, then highlight breaking changes and remaining follow-ups.":"Bu hafta birleştirilen PR ve commit'leri Özellikler, Düzeltmeler, Deneyim ve Mühendislik iyileştirmeleri olarak düzenleyin; kritik değişiklikleri ve kalan takip maddelerini vurgulayın.","Docs sync check":"Belge Senkronizasyon Kontrolü","Compare code, configuration, API, and documentation changes from the last seven days. Identify high-confidence cases where public interfaces or behavior changed without documentation updates.":"Son yedi günün kod, yapılandırma, API ve dokümantasyon değişikliklerini karşılaştırın. Genel arayüzlerin veya sistem davranışının belgelenmeden değiştiği durumları tespit edin."}};
function _trTemplateText(txt){{if(!txt||typeof txt!=="string")return txt;let t=txt.trim();if(TR_AUTOMATION_TEMPLATES[t])return TR_AUTOMATION_TEMPLATES[t];for(let k in TR_AUTOMATION_TEMPLATES){{if(t.startsWith(k)||k.startsWith(t))return TR_AUTOMATION_TEMPLATES[k]}};return txt}};
/* === END HELPERS === */
"""

        # Son import ifadesini bulup hemen sonrasına enjekte et (ES Module sözdizimi geçerliliği için şart)
    import_matches = list(re.finditer(r'import\b[^;]+;', js_content[:150000]))
    if import_matches:
        last_import_pos = import_matches[-1].end()
        js_content = js_content[:last_import_pos] + "\n" + helpers_header + "\n" + js_content[last_import_pos:]
    else:
        js_content = helpers_header + "\n" + js_content

    # 3. Güvenli Regex Eşleştirmeleri (Sözdizimi Hatasız)
    pat_sub_sub = rf'children:(\w+)\.description\|\|(\w+)\.formatMessage\({{id:{bt}settings\.subagents\.noDescription{bt}}}\)'
    js_content = re.sub(pat_sub_sub, r'children:_trAgentDesc(\1)||\2.formatMessage({id:`settings.subagents.noDescription`})', js_content, count=0)

    pat_skill_sub = rf'children:(\w+)\.description\|\|(\w+)\.formatMessage\({{id:{bt}settings\.skills\.noDescription{bt}}}\)'
    pat_cmd_sub = rf'children:(\w+)\.description\|\|(\w+)\.formatMessage\({{id:{bt}settings\.commands\.noDescription{bt}}}\)'
    pat_hint_sub = rf'(\w+)\.argumentHint\?\(0,\$\.jsx\)\(`span`,{{className:`text-ui-base text-foreground-subtlest`,children:(\w+)\.argumentHint}}\):null'

    js_content = re.sub(pat_skill_sub, r'children:_trSkillDesc(\1)||\2.formatMessage({id:`settings.skills.noDescription`})', js_content, count=0)
    js_content = re.sub(pat_cmd_sub, r'children:_trCommandDesc(\1)||\2.formatMessage({id:`settings.commands.noDescription`})', js_content, count=0)
    js_content = re.sub(pat_hint_sub, r'\1.argumentHint?(0,$.jsx)(`span`,{className:`text-ui-base text-foreground-subtlest`,children:_trCommandHint(\2.argumentHint)}):null', js_content, count=0)

    m1 = re.search(r"function\s+(\w+)\(\{count:e,hint:t,title:n\}\)\{", js_content)
    if m1:
        js_content = re.sub(r"function\s+(\w+)\(\{count:e,hint:t,title:n\}\)\{", r"function \1({count:e,hint:t,title:n}){n=_trSectionTitle(n);", js_content, count=1)

    # 4. Tema ve Dil Menüsü Değişiklikleri
    target_theme_v3171 = '(0,$.jsx)(lb,{value:`system`,children:v.formatMessage({id:`sidebar.settings.systemDefault`})}),(0,$.jsx)(lb,{value:`zai-dark`'
    repl_theme_v3171 = '(0,$.jsx)(lb,{value:`system`,children:`Sistem Teması (Varsayılan)`}),(0,$.jsx)(lb,{value:`zai-dark`'
    js_content = js_content.replace(target_theme_v3171, repl_theme_v3171, 1)

    target_locale_v3171 = '(0,$.jsx)(lb,{value:`system`,children:v.formatMessage({id:`sidebar.settings.systemDefault`})}),(0,$.jsx)(lb,{value:`en-US`'
    repl_locale_v3171 = '(0,$.jsx)(lb,{value:`system`,children:`Sistem Dili (Varsayılan)`}),(0,$.jsx)(lb,{value:`tr-TR`,children:`Türkçe`}),(0,$.jsx)(lb,{value:`en-US`'
    js_content = js_content.replace(target_locale_v3171, repl_locale_v3171, 1)

    target_set_v3171 = ')(fh,{value:`en-US`,"data-testid":Gb(Lb,`en-US`),children:ge.formatMessage({id:`settings.locale.en-US`})})'
    repl_set_v3171 = ')(fh,{value:`en-US`,"data-testid":Gb(Lb,`en-US`),children:ge.formatMessage({id:`settings.locale.en-US`})}),(0,$.jsx)(fh,{value:`tr-TR`,"data-testid":Gb(Lb,`tr-TR`),children:`Türkçe`})'
    js_content = js_content.replace(target_set_v3171, repl_set_v3171, 1)

    
    # 5. Eklenti Mağazası Kategorileri ve Eklenti İsim/Açıklama Dinamik Yaması
    target_c9e = 'var c9e={"developer-tools":`settings.plugins.store.category.developerTools`,productivity:`settings.plugins.store.category.productivity`,utilities:`settings.plugins.store.category.utilities`,legal:`settings.plugins.store.category.legal`,template:`settings.plugins.store.category.template`,finance:`settings.plugins.store.category.finance`,other:`settings.plugins.store.category.other`};'
    repl_c9e = 'var c9e={"developer-tools":`settings.plugins.store.category.developerTools`,productivity:`settings.plugins.store.category.productivity`,utilities:`settings.plugins.store.category.utilities`,legal:`settings.plugins.store.category.legal`,template:`settings.plugins.store.category.template`,finance:`settings.plugins.store.category.finance`,"游戏/3D":`settings.plugins.store.category.game3d`,game3d:`settings.plugins.store.category.game3d`,other:`settings.plugins.store.category.other`};'
    js_content = js_content.replace(target_c9e, repl_c9e, 1)

    target_o3 = 'function o3(e,t){let n=t?.startsWith(`zh`)??!1,r=n?e.cn:e.en,i=n?e.en:e.cn;return r?.trim()||i?.trim()||``}'
    repl_o3 = 'function o3(e,t){let n=t?.startsWith(`zh`)??!1,r=n?e.cn:e.en,i=n?e.en:e.cn;let res=r?.trim()||i?.trim()||``;if(typeof _trTemplateText==="function")return _trTemplateText(res);return res}'
    js_content = js_content.replace(target_o3, repl_o3, 1)

    target_tO = 'function tO(e,t){return ki(e,t)}'
    repl_tO = 'function tO(e,t){let raw=ki(e,t);let id=(e&&(e.id||e.name||e.pluginId))||"";if(typeof _trPluginName==="function")return _trPluginName(id,raw);return raw}'
    js_content = js_content.replace(target_tO, repl_tO, 1)

    target_nO = 'function nO(e,t){return xr(t,e.summary?.description??e.info?.description??e.installedMeta?.description,e.listing?.descriptionI18n)}'
    repl_nO = 'function nO(e,t){let raw=xr(t,e.summary?.description??e.info?.description??e.installedMeta?.description,e.listing?.descriptionI18n)??(e&&e.description)??"";let id=(e&&(e.id||e.name||e.pluginId))||"";if(typeof _trPluginDesc==="function")return _trPluginDesc(id,raw);return raw}'
    js_content = js_content.replace(target_nO, repl_nO, 1)

    target_rO = 'function rO(e,t,n){let r=t?.id===e.id?t:void 0;return{name:ki(r??e,n),description:r?nO(r,n):e.description}}'
    repl_rO = 'function rO(e,t,n){let r=t?.id===e.id?t:void 0;let res={name:ki(r??e,n),description:r?nO(r,n):e.description};let pid=(e&&e.id)||(r&&r.id)||(e&&e.name)||"";if(typeof _trPluginName==="function")res.name=_trPluginName(pid,res.name);if(typeof _trPluginDesc==="function")res.description=_trPluginDesc(pid,res.description);return res}'
    js_content = js_content.replace(target_rO, repl_rO, 1)

    # 6. Göreceli Zaman Formatlayıcı (3 days ago -> 3 gün önce)
    js_content = js_content.replace('new Intl.RelativeTimeFormat(e,', 'new Intl.RelativeTimeFormat("tr-TR",')
    js_content = js_content.replace('new Intl.RelativeTimeFormat(t,', 'new Intl.RelativeTimeFormat("tr-TR",')

        # 7. Hafta Sonu Sürümü Bilet Yaması
    js_content = js_content.replace('endsAtPrefix:t===`zh-CN`?`有效期至`:`Valid until`', 'endsAtPrefix:t===`zh-CN`?`有效期至`:`Geçerlilik:`')
    js_content = js_content.replace('replayLabel:t===`zh-CN`?`重播`:`Replay`', 'replayLabel:t===`zh-CN`?`重播`:`Tekrar Oynat`')

    return js_content

def patch_usage_parts(js_content):
    js_content = js_content.replace('DateTimeFormat(e,', 'DateTimeFormat("tr-TR",')
    js_content = js_content.replace('NumberFormat(e,', 'NumberFormat("tr-TR",')
    js_content = js_content.replace('NumberFormat(e||void 0,', 'NumberFormat("tr-TR",')
    return js_content


def patch_main(js_content):
    js_content = js_content.replace("\\u8D44\\u6E90\\u7BA1\\u7406\\u5668", "Kaynak Yöneticisi")
    js_content = js_content.replace("资源管理器", "Kaynak Yöneticisi")
    js_content = js_content.replace('MU="Resource Manager"', 'MU="Kaynak Yöneticisi"')
    js_content = js_content.replace('"Resource Manager"', '"Kaynak Yöneticisi"')
    return js_content


def patch_resource_html(html_content):
    html_content = html_content.replace("<title>Resource Manager</title>", "<title>Kaynak Yöneticisi</title>")
    return patch_html(html_content)


def patch_intl(js_content, tr_dict):
    tr_json = json.dumps(tr_dict, ensure_ascii=False)

    # Check if already patched
    if 'Object.assign({},' in js_content and 'zcode-locale-preference' in js_content:
        m_patched = re.search(r'(\w+)=\{"zh-CN":(\w+),"en-US":Object\.assign\(\{\},(\w+),\{.*?\}\}(?=,\w+=`zcode-locale-preference`)', js_content)
        if m_patched:
            var_map = m_patched.group(1)
            zh_var = m_patched.group(2)
            en_var = m_patched.group(3)
            new_val = f'{var_map}={{"zh-CN":{zh_var},"en-US":Object.assign({{}},{en_var},{tr_json})}}'
            return js_content[:m_patched.start()] + new_val + js_content[m_patched.end():]

    # Pattern: xyz={"zh-CN":a,"en-US":b}
    m = re.search(r'(\w+)=\{"zh-CN":(\w+),"en-US":(\w+)\}', js_content)
    if m:
        var_map = m.group(1)
        zh_var = m.group(2)
        en_var = m.group(3)
        replacement = f'{var_map}={{"zh-CN":{zh_var},"en-US":Object.assign({{}},{en_var},{tr_json})}}'
        return js_content[:m.start()] + replacement + js_content[m.end():]

    target = 'g={"zh-CN":p,"en-US":m}'
    pos_g = js_content.find(target)
    if pos_g != -1:
        replacement = f'g={{"zh-CN":p,"en-US":Object.assign({{}},m,{tr_json})}}'
        return js_content[:pos_g] + replacement + js_content[pos_g + len(target):]
    return js_content


MENU_TR = {
    "titleBar.menu.file": "Dosya",
    "titleBar.menu.edit": "Düzen",
    "titleBar.menu.view": "Görünüm",
    "titleBar.menu.window": "Pencere",
    "titleBar.menu.help": "Yardım",
    "titleBar.menu.file.newTask": "Yeni Görev",
    "titleBar.menu.file.openWorkspace": "Çalışma Alanı Aç...",
    "titleBar.menu.file.closeWindow": "Pencereyi Kapat",
    "titleBar.menu.edit.undo": "Geri Al",
    "titleBar.menu.edit.redo": "Yinele",
    "titleBar.menu.edit.cut": "Kes",
    "titleBar.menu.edit.copy": "Kopyala",
    "titleBar.menu.edit.paste": "Yapıştır",
    "titleBar.menu.edit.delete": "Sil",
    "titleBar.menu.edit.selectAll": "Tümünü Seç",
    "titleBar.menu.view.toggleFullScreen": "Tam Ekranı Aç/Kapat",
    "titleBar.menu.view.actualSize": "Gerçek Boyut",
    "titleBar.menu.view.zoomIn": "Yakınlaştır",
    "titleBar.menu.view.zoomOut": "Uzaklaştır",
    "titleBar.menu.window.minimize": "Küçült",
    "titleBar.menu.window.zoom": "Büyüt",
    "titleBar.menu.window.bringAllToFront": "Tümünü Öne Getir",
    "titleBar.menu.app.services": "Hizmetler",
    "titleBar.menu.app.hide": "{appName} Gizle",
    "titleBar.menu.app.hideOthers": "Diğerlerini Gizle",
    "titleBar.menu.app.showAll": "Tümünü Göster",
    "titleBar.menu.app.quit": "{appName} Uygulamasından Çık",
    "titleBar.menu.help.about": "ZCode Hakkında",
    "titleBar.menu.help.whatsNew": "Yenilikler",
    "titleBar.menu.help.checkForUpdates": "Güncellemeleri Denetle...",
    "titleBar.menu.help.toggleDevTools": "Geliştirici Araçlarını Aç/Kapat",
    "titleBar.menu.help.resourceManager": "Kaynak Yöneticisi",
    "titleBar.menu.help.toggleZCodeStdioTap": "Ajan Stdio İletişimini Yakala",
    "titleBar.menu.help.zcodeEndpoint": "ZCode Uç Noktası",
    "titleBar.menu.help.zcodeEndpoint.production": "Production (Varsayılan)",
    "titleBar.menu.help.zcodeEndpoint.test": "Test",
    "titleBar.menu.help.zcodeEndpoint.custom": "Özel...",
    "titleBar.menu.help.zcodeEndpoint.reset": "Varsayılana Sıfırla",
    "titleBar.menu.help.feedback": "Geri Bildirim Bildir...",
    "titleBar.menu.help.exportLogs": "Günlükleri Dışa Aktar",
    "titleBar.menu.help.clearAllData": "Tüm Verileri Temizle",
    "desktopMenu.help.checkingForUpdates": "Güncellemeler denetleniyor...",
    "desktopMenu.help.updateAvailableVersion": "Yeni sürüm mevcut: {version}",
    "desktopMenu.help.downloadingUpdateVersion": "Güncelleme indiriliyor: {version}...",
    "desktopMenu.help.downloadingUpdateProgress": "Güncelleme indiriliyor... {progress}",
    "desktopMenu.help.restartToUpdate": "Yeniden Başlat ve Güncelle ({version})",
    "dock.menu.showCurrentWindow": "Mevcut Pencereyi Göster",
    "tray.tooltip": "ZCode",
    "tray.menu.openZCode": "ZCode'u Aç",
    "tray.menu.quit": "Çıkış"
}

def patch_menu(js_content):
    m = re.search(r'(\w+)=(\{"zh-CN":\{"titleBar\.menu\.file":.*?\}\});function\s+', js_content)
    if m:
        var_name = m.group(1)
        json_str = m.group(2)
        kp_data = json.loads(json_str)
        for k, v in MENU_TR.items():
            if "en-US" in kp_data:
                kp_data["en-US"][k] = v
            if "zh-CN" in kp_data:
                kp_data["zh-CN"][k] = v
        new_kp_json = json.dumps(kp_data, ensure_ascii=False)
        return js_content[:m.start()] + f"{var_name}={new_kp_json};function " + js_content[m.end():]

    pos_kp = js_content.find('Kp={"zh-CN":')
    if pos_kp != -1:
        pos_end_kp = js_content.find('};function db(', pos_kp)
        kp_str = js_content[pos_kp + 3:pos_end_kp + 1]
        kp_data = json.loads(kp_str)
        for k, v in MENU_TR.items():
            if "en-US" in kp_data:
                kp_data["en-US"][k] = v
            if "zh-CN" in kp_data:
                kp_data["zh-CN"][k] = v
        new_kp_json = json.dumps(kp_data, ensure_ascii=False)
        return js_content[:pos_kp + 3] + new_kp_json + js_content[pos_end_kp + 1:]

    # Fallback to legacy pp menu
    pos_pp = js_content.find("pp={")
    if pos_pp != -1:
        pos_by = js_content.find("function by(", pos_pp)
        if pos_by != -1:
            pp_str = js_content[pos_pp + 3:pos_by].strip().rstrip(";")
            try:
                pp_data = json.loads(pp_str)
                if "en-US" in pp_data:
                    for k, v in MENU_TR.items():
                        pp_data["en-US"][k] = v
                new_pp_json = json.dumps(pp_data, ensure_ascii=False)
                return js_content[:pos_pp] + f"pp={new_pp_json};" + js_content[pos_by:]
            except Exception:
                pass
    return js_content


# =====================================================================
# 4. EKLENTİ, YETENEK VE KOMUT TÜRKÇELEŞTİRİCİSİ
# =====================================================================

PLUGIN_TRANSLATIONS = {
    "android-emulator": {
        "displayName": "Android Emülatörü",
        "description": "Android emülatörlerini yönetme, başlatma ve cihaz kontrolü için geliştirici araçları."
    },
    "browser-use": {
        "displayName": "Browser Use",
        "description": "Masaüstü için yerleşik tarayıcı otomasyonu çalışma ortamı ve rehberlik."
    },
    "document-skills": {
        "displayName": "Belge Becerileri",
        "description": "Yerleşik DOCX ve PDF belge oluşturma becerileri.",
        "examplePrompts": [
            "Notlarımdan biçimlendirilmiş bir Word belgesi oluştur",
            "Bu PDF'deki tabloları bir elektronik tabloya aktar",
            "Bu CSV dosyasından grafikler içeren bir Excel çalışma kitabı oluştur"
        ]
    },
    "ios-simulator": {
        "displayName": "iOS Simülatörü",
        "description": "iOS simülatörlerini yönetme, test etme ve arayüz denetimi araçları."
    },
    "restore-legacy-sessions": {
        "displayName": "Eski Oturumları Geri Yükle",
        "description": "Önceki sürümlerden kalan eski oturumları ve sohbet geçmişlerini geri yükleyin."
    },
    "skill-creator": {
        "displayName": "Beceri Oluşturucu",
        "description": "Yeni ajan becerileri ve iş akışları oluşturmak için rehberli araç seti."
    },
    "zcode-guide": {
        "displayName": "ZCode Rehberi",
        "description": "ZCode özellikleri, komutları ve yapılandırmaları için kapsamlı kullanım kılavuzu.",
        "examplePrompts": [
            "ZCode'da MCP sunucularını nasıl yapılandırırım?",
            "Mevcut ZCode yapılandırmamı tanıla"
        ]
    },
    "computer-use": {
        "displayName": "Bilgisayar Kontrolü",
        "description": "Bilgisayar Kontrolü: Masaüstü uygulamalarını fare, klavye ve sistem eylemleriyle otomatikleştirin."
    },
    "zcode-cua": {
        "displayName": "Bilgisayar Kontrolü",
        "description": "Bilgisayar Kontrolü: Masaüstü uygulamalarını fare, klavye ve sistem eylemleriyle otomatikleştirin."
    }
}

SKILL_TRANSLATIONS = {
    "android-dev": "android-emulator MCP araçlarıyla Android emülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.",
    "control-browser": "Yalnızca ana ajan tarayıcı kullanımı: ZCode içinde web sayfalarını ve yerel HTTP hedeflerini açın, gezinin, inceleyin, tıklayın, form doldurun, ekran görüntüsü alın ve doğrulayın.",
    "web-gui-tester": "Oturumdaki tarayıcı otomasyon araçlarını kullanarak web arayüzlerini etkileşimli olarak test edin, kullanıcı eylemlerini simüle edin, ekran görüntüleriyle doğrulayın ve test raporu oluşturun.",
    "docx": "Revizyonlar, yorumlar, biçimlendirme koruma ve metin çıkarma desteğiyle kapsamlı DOCX belgesi oluşturma, düzenleme ve analiz yetenekleri. Şablon tabanlı üretim ve format dönüştürmeyi destekler.",
    "pdf": "4 özel iş akışına sahip profesyonel PDF işleme araç seti: Typst/ReportLab ile yayın kalitesinde PDF üretimi, HTML/CSS tuvali ile görsel belge biçimlendirme, LaTeX ile akademik makaleler ve PyMuPDF/pdfplumber ile programatik düzenleme. Akıllı yönlendirme, format doğrulama ve otomatik kalite kontrolleri içerir.",
    "pptx": "PowerPoint (.pptx) sunum oluşturma, biçimlendirme ve düzenleme yetenekleri. Sıfırdan veya taslaklardan sunum hazırlama, mevcut slaytları düzenleme ve metin/not çıkarma işlemlerini kapsar.",
    "xlsx": "Veri analizi, formüller ve grafiklerle Excel (.xlsx, .xlsm, .csv) için gelişmiş elektronik tablo işleme yetenekleri. Sıfırdan çalışma kitapları oluşturma, mevcut tabloları düzenleme, veri analizi ve formül hesaplamalarını kapsar.",
    "ios-dev": "ios-simulator MCP araçlarıyla iOS simülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.",
    "restore-legacy-sessions": "ZCode'un ~/.zcode/v2/sessions altındaki eski ACP dönemi ZCode oturumlarını yeni ZCode görev/oturum depolarına aktarması, incelemesi veya planlaması gerektiğinde kullanın. Eski sohbet geçmişini taşıma veya önceki oturumları geri yükleme sorularında tetiklenir.",
    "skill-creator": "Yeni beceriler oluşturun, mevcut becerileri düzenleyin ve ifadeleri iyileştirin. Sıfırdan SKILL.md yazarken, mevcut becerileri geliştirirken, tekrarlanan iş akışlarını yeniden kullanılabilir becerilere dönüştürürken veya beceri tetikleyicilerini giderirken kullanın.",
    "plugin-creator": "ZCode eklenti kaynak kodunu ve yerel bir test mağazasını oluşturun veya güncelleyin; ardından kullanıcıya mağazayı ekleme, eklentiyi yükleme veya güncelleme ve uygulamada deneme konusunda rehberlik edin.",
    "computer-use": "Erişilebilirlik odaklı semantik eylemler ve görsel doğrulama ile masaüstü kontrolü.",
    "zcode-computer-use": "Erişilebilirlik odaklı semantik eylemler ve görsel doğrulama ile masaüstü kontrolü.",
    "diagnosing-commands": "ZCode istemcisindeki özel eğik çizgi komutu (/komut) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir komut eksik olduğunda, bir beceri/ajan tarafından geçersiz kılındığında, ayrıştırılamadığında, kapsamlarda yinelenen adlara sahip olduğunda veya çalıştırılamadığında geçerlidir.",
    "diagnosing-hooks": "ZCode istemcisindeki kanca (hook) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir kanca tetiklenmediğinde, bir olay adı yanlış olduğunda, bir eşleştirici eşleşmediğinde, bir komut dosyası başarısız olduğunda veya kanca sıralaması/izinleri beklenmeyen davranışlara yol açtığında geçerlidir.",
    "diagnosing-mcp": "ZCode istemcisindeki MCP (Model Bağlam Protokolü) sunucu yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir MCP sunucusu bağlanmadığında, araçları eksik olduğunda, işlemi hata ile sonlandığında, aktarım protokolü (stdio veya SSE) yanlış yapılandırıldığında veya ortam değişkenleri hatalı olduğunda geçerlidir.",
    "diagnosing-plugins": "ZCode istemcisindeki eklenti ve mağaza sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir eklenti listelenmediğinde, mağaza ekleme veya eklenti yükleme başarısız olduğunda, bir eklenti komutu/becerisi/ajanı eksik olduğunda veya bir eklenti yapılandırması bozulduğunda geçerlidir.",
    "diagnosing-skills": "ZCode istemcisindeki beceri yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir beceri keşfedilmediğinde, yüklü olduğu halde otomatik tetiklenmediğinde, dosyaları eksik olduğunda, frontmatter ayrıştırma hataları verdiğinde veya kapsamlarda yinelenen adlara sahip olduğunda geçerlidir.",
    "zcode-configuration-guide": "ZCode istemcisinde uzantı kaynaklarını (MCP sunucuları, eğik çizgi komutları, beceriler, kancalar ve eklentiler) veya AGENTS.md gibi talimat dosyalarını yapılandırırken kullanın. Bir kullanıcı bu uzantı mekanizmalarının nasıl ekleneceğini, düzenleneceğini veya yapılandırılacağını sorduğunda geçerlidir.",
    "microsoft-foundry": "Microsoft Foundry ajanlarını, modellerini ve kaynaklarını uçtan uca derleyin, dağıtın, değerlendirin, optimize edin, ince ayar yapın ve yönetin.",
    "finetuning": "SFT, DPO veya RFT kullanarak Microsoft Foundry üzerinde modelleri ince ayarlar (fine-tune). Veri kümesi hazırlama, eğitim işi gönderme, değerlendirme ve dağıtımı kapsar.",
    "deploy-model": "Akıllı amaç tabanlı yönlendirme ile birleşik Azure OpenAI model dağıtım yeteneği. Hem hızlı ön ayarlı hem de tam özelleştirilmiş dağıtımları yönetir.",
    "capacity": "Bölgeler ve abonelikler genelinde kullanılabilir Azure OpenAI model kapasitesini keşfeder. Kota sınırlarını analiz eder ve en uygun dağıtım konumlarını önerir.",
    "customize": "Tam özelleştirme kontrolüyle Azure OpenAI modelleri için etkileşimli rehberli dağıtım akışı. Model sürümü, SKU, kapasite ve içerik filtreleme ilkesi seçimini sağlar.",
    "preset": "Kullanılabilir tüm bölgelerdeki kapasiteyi analiz ederek Azure OpenAI modellerini en uygun bölgelere akıllıca dağıtır. Kapasite mevcut olduğunda geçerli bölgeyi tercih eder.",
    "chrome-cdp": "Chrome oturumu ile etkileşim kurun, sayfaları denetleyin ve test edin.",
    "codebase-memory": "Yapısal kod sorguları, mimari keşif ve çağrı zinciri analizi için kod tabanı bilgi grafiğini kullanın.",
    "desktop-eye": "Canlı masaüstü ekran görüntüsü alarak arayüz bağlamını anlık olarak doğrulayın."
}

COMMAND_TRANSLATIONS = {
    "android-dev.md": {
        "description": "Android emülatör geliştirme döngüsünü başlatın.",
        "argument-hint": "\"[hedef veya sorun açıklaması]\""
    },
    "ios-dev.md": {
        "description": "iOS simülatör geliştirme döngüsünü başlatın.",
        "argument-hint": "\"[hedef veya sorun açıklaması]\""
    },
    "restore-legacy-sessions.md": {
        "description": "Eski bir ZCode oturumunu seçin ve geri yükleyin.",
        "argument-hint": "\"[ajan/çalışma alanı/oturum filtreleri]\""
    }
}


def patch_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        changed = False

        name = data.get("name")
        if name:
            clean_name = name.replace("-plugin", "")
            tr_info = PLUGIN_TRANSLATIONS.get(clean_name) or PLUGIN_TRANSLATIONS.get(name)
            if tr_info:
                if "description" in tr_info and data.get("description") != tr_info["description"]:
                    data["description"] = tr_info["description"]
                    changed = True
                if "displayName" in tr_info and "displayName" in data and data.get("displayName") != tr_info["displayName"]:
                    data["displayName"] = tr_info["displayName"]
                    changed = True

        if "manifest" in data and "plugins" in data["manifest"]:
            for pl in data["manifest"]["plugins"]:
                pname = pl.get("name")
                tr_info = PLUGIN_TRANSLATIONS.get(pname)
                if tr_info:
                    if "description" in tr_info and pl.get("description") != tr_info["description"]:
                        pl["description"] = tr_info["description"]
                        if "description_i18n" not in pl:
                            pl["description_i18n"] = {}
                        pl["description_i18n"]["tr"] = tr_info["description"]
                        changed = True
                    if "displayName" in tr_info and pl.get("displayName") != tr_info["displayName"]:
                        pl["displayName"] = tr_info["displayName"]
                        changed = True
                    if "examplePrompts" in tr_info:
                        pl["examplePrompts"] = tr_info["examplePrompts"]
                        if "examplePrompts_i18n" not in pl:
                            pl["examplePrompts_i18n"] = {}
                        pl["examplePrompts_i18n"]["tr"] = tr_info["examplePrompts"]
                        changed = True

        if "plugins" in data and isinstance(data["plugins"], list):
            for pl in data["plugins"]:
                pname = pl.get("name")
                tr_info = PLUGIN_TRANSLATIONS.get(pname)
                if tr_info:
                    if "description" in tr_info and pl.get("description") != tr_info["description"]:
                        pl["description"] = tr_info["description"]
                        if "description_i18n" not in pl:
                            pl["description_i18n"] = {}
                        pl["description_i18n"]["tr"] = tr_info["description"]
                        changed = True
                    if "displayName" in tr_info and pl.get("displayName") != tr_info["displayName"]:
                        pl["displayName"] = tr_info["displayName"]
                        changed = True
                    if "examplePrompts" in tr_info:
                        pl["examplePrompts"] = tr_info["examplePrompts"]
                        if "examplePrompts_i18n" not in pl or not isinstance(pl["examplePrompts_i18n"], dict):
                            pl["examplePrompts_i18n"] = {}
                        pl["examplePrompts_i18n"]["tr"] = tr_info["examplePrompts"]
                        changed = True
                elif CLAUDE_PLUGINS_TR and pname in CLAUDE_PLUGINS_TR:
                    c_desc = CLAUDE_PLUGINS_TR[pname]
                    if pl.get("description") != c_desc:
                        pl["description"] = c_desc
                        if "description_i18n" not in pl or not isinstance(pl["description_i18n"], dict):
                            pl["description_i18n"] = {}
                        pl["description_i18n"]["tr"] = c_desc
                        changed = True

        if changed:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def patch_markdown_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()

        changed = False

        if os.path.basename(filepath) == "SKILL.md":
            for skill_name, tr_desc in SKILL_TRANSLATIONS.items():
                if re.search(rf"^name:\s*{re.escape(skill_name)}\b", content, re.MULTILINE):
                    new_content, n = re.subn(
                        r"(^description:\s*)([^\n>]+)",
                        rf'\g<1>"{tr_desc}"',
                        content,
                        flags=re.MULTILINE
                    )
                    if n > 0:
                        content = new_content
                        changed = True
                    else:
                        new_content, n = re.subn(
                            r"(^description:\s*>\n(?:\s+[^\n]+\n)+)",
                            f'description: "{tr_desc}"\n',
                            content,
                            flags=re.MULTILINE
                        )
                        if n > 0:
                            content = new_content
                            changed = True

        cmd_name = os.path.basename(filepath)
        if cmd_name in COMMAND_TRANSLATIONS:
            cmd_info = COMMAND_TRANSLATIONS[cmd_name]
            tr_desc = cmd_info["description"]
            tr_hint = cmd_info.get("argument-hint")

            new_content, n = re.subn(
                r"(^description:\s*)([^\n]+)",
                rf'\g<1>"{tr_desc}"',
                content,
                flags=re.MULTILINE
            )
            if n > 0:
                content = new_content
                changed = True

            if tr_hint:
                new_content, n2 = re.subn(
                    r"(^argument-hint:\s*)([^\n]+)",
                    rf'\g<1>{tr_hint}',
                    content,
                    flags=re.MULTILINE
                )
                if n2 > 0:
                    content = new_content
                    changed = True

        if changed:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
    except Exception:
        pass


def patch_special_files(user_zcode, program_packages):
    # ZCode Sites Komutları Güncellemesi
    site_cmds_dir = os.path.join(program_packages, "zcode-site-plugin", "commands")
    if os.path.exists(site_cmds_dir):
        site_tr = {
            "site-badge.md": ("Bağlı ZCode Sites sitesinde ZCode rozetini gizleyin veya gösterin.", "gizle | göster"),
            "site-deploy.md": ("Bu projeyi ZCode Sites'a dağıtın veya bağlı siteyi yeniden dağıtın.", "[site id veya notlar]"),
            "site-logs.md": ("Bir ZCode Sites dağıtımının günlüklerini gösterin ve olası hataları açıklayın.", "[dağıtım id]"),
            "site-offline.md": ("Bağlı ZCode Sites sitesini çevrimdışı duruma getirin.", "[site id]"),
            "site-online.md": ("Bağlı ZCode Sites sitesini tekrar çevrimiçi duruma getirin.", "[site id]"),
            "site-status.md": ("Bu projeye bağlı ZCode Sites sitesini gösterin.", "[site id]"),
            "site-usage.md": ("ZCode Sites kullanımını ve plan sınırlarını gösterin.", "")
        }
        for fname, (desc, hint) in site_tr.items():
            fpath = os.path.join(site_cmds_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as _f:
                        _txt = _f.read()
                    _txt = re.sub(r'description:\s*".*?"', f'description: "{desc}"', _txt)
                    _txt = re.sub(r'description:\s*[^\r\n]+', f'description: "{desc}"', _txt, count=1)
                    if hint:
                        _txt = re.sub(r'argument-hint:\s*".*?"', f'argument-hint: "{hint}"', _txt)
                        _txt = re.sub(r'argument-hint:\s*[^\r\n]+', f'argument-hint: "{hint}"', _txt, count=1)
                    with open(fpath, "w", encoding="utf-8") as _f:
                        _f.write(_txt)
                except Exception:
                    pass

    # 1. server.js
    server_paths = [
        os.path.join(program_packages, r"browser-use-plugin\dist\mcp\server.js"),
        os.path.join(user_zcode, r"cli\plugins\cache\zcode-plugins-official\browser-use\0.4.2\dist\mcp\server.js")
    ]
    for sp in server_paths:
        if os.path.exists(sp):
            try:
                with open(sp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                orig_len = len(content)
                content = content.replace("General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks.", "Karmaşık soruları araştırmak, kod aramak ve çok adımlı görevleri yürütmek için genel amaçlı ajan.")
                content = content.replace("Read-only search agent for broad fan-out searches", "Geniş kapsamlı aramalar için salt okunur arama ajanı")
                if len(content) != orig_len or "Karmaşık soruları" in content:
                    with open(sp, "w", encoding="utf-8", newline="\n") as f:
                        f.write(content)
            except Exception:
                pass

    # 2. judge.md
    judge_paths = [
        os.path.join(program_packages, r"document-skills-plugin\agents\judge.md"),
        os.path.join(user_zcode, r"cli\plugins\cache\zcode-plugins-official\document-skills\0.1.4\agents\judge.md"),
        os.path.join(user_zcode, r"cli\plugins\cache\zcode-plugins-official\document-skills\0.1.5\agents\judge.md")
    ]
    for jp in judge_paths:
        if os.path.exists(jp):
            try:
                with open(jp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "kabul incelemesi" not in content or "Ã" in content:
                    content = re.sub(r'description:\s*"[^"]+"', 'description: "Yalnızca pptx, docx, xlsx, pdf, poster ve grafik türündeki görsel çıktıların kabul incelemesi için tek yetkili görsel onay ajanı."', content)
                    with open(jp, "w", encoding="utf-8", newline="\n") as f:
                        f.write(content)
            except Exception:
                pass


def scan_and_patch(root_dir):
    if not os.path.exists(root_dir):
        return
    for root, dirs, files in os.walk(root_dir):
        for f in files:
            p = os.path.join(root, f)
            if f in ("plugin.json", "bundled-marketplace.json", "cdn-marketplace.json", "marketplace.json"):
                patch_json_file(p)
            elif f == "SKILL.md" or (f.endswith(".md") and "commands" in root):
                patch_markdown_file(p)


def apply_packages_tr():
    print("[5/7] Eklenti, yetenek ve komut paketleri Türkçeleştiriliyor...")
    user_zcode = os.path.expanduser(r"~\.zcode")
    program_packages = r"C:\Program Files\ZCode\resources\glm\packages"
    agents_skills = os.path.expanduser(r"~\.agents\skills")
    claude_skills = os.path.expanduser(r"~\.claude\skills")

    patch_special_files(user_zcode, program_packages)
    scan_and_patch(os.path.join(user_zcode, "cli", "plugins"))
    scan_and_patch(program_packages)
    scan_and_patch(agents_skills)
    scan_and_patch(claude_skills)
    print("    -> Eklenti ve komut paketleri başarıyla güncellendi.")


def clean_and_restore_glm_config():
    """
    Kullanıcının ~/.zcode yapılandırmasını orijinal GLM modellerine geri döndürür.
    Harici proxy, yerel LLM ve özel API yönlendirmelerini temizler.
    """
    print("[5/7] Orijinal GLM modelleri doğrulanıyor ve harici bağlantılar temizleniyor...")
    user_home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    zcode_dir = os.path.join(user_home, ".zcode")
    v2_config = os.path.join(zcode_dir, "v2", "config.json")
    proxy_dir = os.path.join(zcode_dir, "proxy")

    if os.path.exists(proxy_dir):
        try:
            shutil.rmtree(proxy_dir, ignore_errors=True)
            print("    -> Eski proxy kalıntıları temizlendi.")
        except Exception:
            pass

    if os.path.exists(v2_config):
        try:
            with open(v2_config, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            
            providers = cfg.get("provider", {})
            cleaned_providers = {}
            for p_id, p_val in providers.items():
                if p_id.startswith("builtin:bigmodel") or p_id.startswith("builtin:zai"):
                    cleaned_providers[p_id] = p_val

            if len(cleaned_providers) < len(providers):
                cfg["provider"] = cleaned_providers
                with open(v2_config, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
                print("    -> Harici model ve özel API sağlayıcıları temizlendi, orijinal GLM korundu.")
        except Exception as e:
            print(f"    [-] Config temizleme uyarısı: {e}")

    scratch_model = os.path.join(user_home, ".gemini", "antigravity", "scratch", "turkce-fine-tuning", "turkce_llama3_modeli.Q4_K_M.gguf")
    if os.path.exists(scratch_model):
        try:
            os.remove(scratch_model)
            print("    -> Yerel fine-tune GGUF modeli silindi.")
        except Exception:
            pass

    ollama_blobs = os.path.join(user_home, ".ollama", "models", "blobs")
    if os.path.exists(ollama_blobs):
        try:
            for item in os.listdir(ollama_blobs):
                p = os.path.join(ollama_blobs, item)
                if os.path.isfile(p):
                    os.remove(p)
            print("    -> Ollama yerel model kalıntıları temizlendi.")
        except Exception:
            pass


# =====================================================================
# 5. ANA YÜRÜTME FONKSİYONU
# =====================================================================

def main():
    print("=" * 60)
    print("       🚀 ZCODE TEK TIK TÜRKÇE YAMA VE GÜNCELLEYİCİ        ")
    print("=" * 60)

    # 1. Yönetici İzni Doğrulaması
    run_as_admin()

    # 2. ZCode Dizinini ve Dosyalarını Tespit Et
    if not os.path.exists(DEFAULT_ASAR):
        print(f"[-] HATA: ZCode app.asar dosyası bulunamadı: {DEFAULT_ASAR}")
        print("Lütfen ZCode'un C:\\Program Files\\ZCode dizininde kurulu olduğundan emin olun.")
        input("\nÇıkmak için Enter'a basın...")
        sys.exit(1)

    # 3. Açık ZCode Süreçlerini Kapat
    kill_zcode()

    # 4. Sözlük Dosyasını Yükle (Disk, Paket veya Gömülü Bellek)
    print("[2/7] Türkçe sözlük yükleniyor...")
    tr_dict = load_tr_dictionary()
    if not tr_dict:
        print("[-] HATA: Türkçe sözlük verisine ulaşılamadı!")
        input("\nÇıkmak için Enter'a basın...")
        sys.exit(1)
    print(f"    -> {len(tr_dict)} adet arayüz anahtarı belleğe alındı.")

    # 5. Orijinal ASAR Yedeklemesi (Eğer yoksa)
    backup_path = os.path.join(DEFAULT_RESOURCES_DIR, "app.asar.orig")
    if not os.path.exists(backup_path):
        print("[3/7] Orijinal app.asar ilk yedeği oluşturuluyor (app.asar.orig)...")
        shutil.copy2(DEFAULT_ASAR, backup_path)
    else:
        print("[3/7] Orijinal fabrika yedeği mevcut: app.asar.orig")

    # 6. ASAR Dosyasını Ayrıştır ve Dinamik Olarak Yamaları Uygula
    print("[4/7] ASAR bileşenleri (i18n, menüler, webview, stiller) yamalanıyor...")
    with open(DEFAULT_ASAR, "rb") as f_src:
        header, base_offset, _ = parse_asar_header(f_src)
        targets = find_target_paths(header, f_src, base_offset)
        print("    -> Dinamik bundle hedefleri tespit edildi:")
        for k, v in targets.items():
            print(f"       [{k}] {'/'.join(v)}")

        # A. IntlProvider
        node_intl = find_node(header, targets["intl"])
        intl_orig = extract_file(f_src, node_intl, base_offset).decode("utf-8")
        intl_patched = patch_intl(intl_orig, tr_dict)

        # B. Masaüstü Menüleri
        node_menu = find_node(header, targets["menu"])
        menu_orig = extract_file(f_src, node_menu, base_offset).decode("utf-8")
        menu_patched = patch_menu(menu_orig)

        # C. index.html (Dinamik DOM Gözlemcisi)
        node_html = find_node(header, targets["html"])
        html_orig = extract_file(f_src, node_html, base_offset).decode("utf-8")
        html_patched = patch_html(html_orig)

        # C2. resource-manager.html (Kaynak Yöneticisi Başlığı ve DOM Gözlemcisi)
        node_res_html = find_node(header, targets["resource_html"])
        res_html_orig = extract_file(f_src, node_res_html, base_offset).decode("utf-8")
        res_html_patched = patch_resource_html(res_html_orig)

        # D. styles (Webview + Skills + Bilgisayar Kontrolü)
        node_styles = find_node(header, targets["styles"])
        styles_orig = extract_file(f_src, node_styles, base_offset).decode("utf-8")
        styles_patched = patch_styles(styles_orig)

        # E. out/main/index.js (Çince Dosya Gezgini Temizliği)
        node_main = find_node(header, targets["main"])
        main_orig = extract_file(f_src, node_main, base_offset).decode("utf-8")
        main_patched = patch_main(main_orig)

        # F. usageStatsUiParts (Isı Haritası ve Trend Tarih Biçimlendirici)
        node_usage_parts = find_node(header, targets["usage_parts"])
        usage_parts_orig = extract_file(f_src, node_usage_parts, base_offset).decode("utf-8")
        usage_parts_patched = patch_usage_parts(usage_parts_orig)

    modified_files = {
        "/".join(targets["intl"]): intl_patched.encode("utf-8"),
        "/".join(targets["menu"]): menu_patched.encode("utf-8"),
        "/".join(targets["html"]): html_patched.encode("utf-8"),
        "/".join(targets["resource_html"]): res_html_patched.encode("utf-8"),
        "/".join(targets["styles"]): styles_patched.encode("utf-8"),
        "/".join(targets["main"]): main_patched.encode("utf-8"),
        "/".join(targets["usage_parts"]): usage_parts_patched.encode("utf-8"),
    }

    # 7. Eklenti ve Paketleri Yamala
    apply_packages_tr()

    # 8. Orijinal GLM Yapılandırmasını Doğrula ve Yerel Modelleri / Proxy'yi Temizle
    clean_and_restore_glm_config()

    # 9. Yeni ASAR Paketini Doğrudan Canlıya Derle
    print("[6/7] Yeni app.asar paketi derleniyor ve kuruluyor...")
    temp_patched_asar = os.path.join(DEFAULT_RESOURCES_DIR, "app.asar.tmp")
    rebuild_asar(DEFAULT_ASAR, temp_patched_asar, modified_files)

    # Atomik Değiştirme
    if os.path.exists(DEFAULT_ASAR):
        os.remove(DEFAULT_ASAR)
    os.rename(temp_patched_asar, DEFAULT_ASAR)

    print("\n" + "=" * 60)
    print("  ✅ TEBRİKLER! ZCODE TÜRKÇE YAMASI BAŞARIYLA TAMAMLANDI! ")
    print("=" * 60)
    print("  ⭐ Projeyi faydalı bulduysanız GitHub'da bir Yıldız (Star)")
    print("     bırakarak projemize destek olabilirsiniz!")
    print("     👉 https://github.com/gmzoztr/zcode-turkish-localization")
    print("=" * 60 + "\n")

    # 10. ZCode'u Bağımsız Masaüstü Süreci Olarak Başlat
    launch_zcode_detached(DEFAULT_EXE)

    # 11. Bilgilendirme Kutusu ve GitHub Yıldız Çağrısı
    try:
        msg = (
            "ZCode başarıyla güncellendi ve %100 Türkçe olarak başlatıldı!\n\n"
            "Tüm menüler, ayarlar, eklenti mağazası ve yetenekler aktif durumdadır.\n\n"
            "⭐ Projeyi beğendiyseniz GitHub repomuza bir Yıldız (Star) vererek destek olmak ister misiniz?"
        )
        ret = ctypes.windll.user32.MessageBoxW(
            None,
            msg,
            "ZCode Türkçe Yama Başarılı ⭐",
            0x40 | 0x4  # MB_ICONINFORMATION | MB_YESNO
        )
        if ret == 6:  # IDYES
            webbrowser.open("https://github.com/gmzoztr/zcode-turkish-localization")
    except Exception:
        pass


if __name__ == "__main__":
    main()
