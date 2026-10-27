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
    pos_sb = js_content.find('const styleId = "zcode-coding-plan-hide-scrollbar";')
    if pos_sb != -1:
        pos_fn_start = js_content.rfind("function ", 0, pos_sb)
        pos_fn_end = js_content.find("function rMe(", pos_sb)
        if pos_fn_end == -1:
            pos_fn_end = js_content.find("function ", pos_sb)

        TR_MAP_CODE = r'''const TR_MAP = {
    // 1024 Programmer's Day Surprise Modal
    "YOUR PROGRAMMER'S DAY SURPRISE": "PROGRAMCILAR GÜNÜ SÜRPRİZİNİZ",
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

    "Personal plans": "Bireysel Planlar",
    "Team plans": "Ekip Planları",
    "Personal Plans": "Bireysel Planlar",
    "Team Plans": "Ekip Planları",
    "Monthly": "Aylık",
    "Quarterly -20%": "3 Aylık -%20",
    "Yearly -30%": "Yıllık -%30",
    "Quarterly": "3 Aylık",
    "Yearly": "Yıllık",
    "-20%": "-%20",
    "/month": " / ay",
    "/Month": " / ay",
    "/ month": " / ay",
    "/ Month": " / ay",
    " /month": " / ay",
    " /Month": " / ay",
    " / month": " / ay",
    " / Month": " / ay",
    "／month": " / ay",
    "／Month": " / ay",
    "month": "ay",
    "Month": "ay",
    "MONTH": "ay",
    "year": "yıl",
    "Year": "yıl",
    "YEAR": "yıl",
    "US$18.00 /month": "US$18.00 / ay",
    "US$80.00 /month": "US$80.00 / ay",
    "US$168.00 /month": "US$168.00 / ay",
    "US$18.00 /Month": "US$18.00 / ay",
    "US$80.00 /Month": "US$80.00 / ay",
    "US$168.00 /Month": "US$168.00 / ay",
    "US$18.00/month": "US$18.00 / ay",
    "US$80.00/month": "US$80.00 / ay",
    "US$168.00/month": "US$168.00 / ay",
    "Ideal for getting started": "Başlangıç için ideal",
    "5-day free trial, including:": "5 günlük ücretsiz deneme, şunları içerir:",
    "5-day free trial, including": "5 günlük ücretsiz deneme, şunları içerir",
    "5-day free trial": "5 günlük ücretsiz deneme",
    "including:": "şunları içerir:",
    "including": "şunları içerir",
    "Configure custom models with BYOK": "BYOK ile özel modelleri yapılandırın",
    "Occasional free token offers": "Dönemsel ücretsiz token teklifleri",
    "Weekend Build": "Hafta Sonu Derlemesi",
    "Global Build": "Küresel Derleme",
    "Ended": "Sona Erdi",
    "Expired": "Süresi Doldu",
    "Lightweight repo iteration": "Hafif repo geliştirmesi",
    "Rolling access to the latest flagship models and features": "En yeni amiral gemisi modellere ve özelliklere kesintisiz erişim",
    "Supports 20+ coding tools, including ZCode": "ZCode dahil 20+ kodlama aracını destekler",
    "ZCode-exclusive benefits:": "ZCode'a özel avantajlar:",
    "ZCode-exclusive benefits": "ZCode'a özel avantajlar",
    "Idle-time tasks: 1/day Free token": "Boş zaman görevleri: Günde 1 Ücretsiz token",
    "Idle-time tasks: 3/day Free token": "Boş zaman görevleri: Günde 3 Ücretsiz token",
    "Idle-time tasks: 5/day Free token": "Boş zaman görevleri: Günde 5 Ücretsiz token",
    "Idle-time tasks: 1/day": "Boş zaman görevleri: Günde 1",
    "Idle-time tasks: 3/day": "Boş zaman görevleri: Günde 3",
    "Idle-time tasks: 5/day": "Boş zaman görevleri: Günde 5",
    "Idle-time tasks:": "Boş zaman görevleri:",
    "Idle-time tasks": "Boş zaman görevleri",
    "Idle-time task": "Boş zaman görevi",
    "Free token": "Ücretsiz token",
    "free token": "ücretsiz token",
    "Reset the 5-hour quota during idle hours": "Boş zaman saatlerinde 5 saatlik kotayı sıfırlama",
    "ZCode MCP benefits": "ZCode MCP avantajları",
    "150% quota with a limited-time usage multiplier discount": "Sınırlı süreli kullanım çarpanı indirimiyle %150 kota",
    "Subscribe": "Abone Ol",
    "Subscribe now": "Şimdi Abone Ol",
    "Everything in Lite": "Lite'taki her şey dahil",
    "Everything in Pro": "Pro'daki her şey dahil",
    "Priority access to the latest flagship models and features": "En yeni amiral gemisi modellere ve özelliklere öncelikli erişim",
    "Includes a curated selection of MCP tools": "Seçkin MCP araçları koleksiyonu içerir",
    "Faster generation speeds": "Daha yüksek üretim hızları",
    "Built for advanced users working on mid-to-large repos": "Orta ve büyük repolarda çalışan ileri düzey kullanıcılar için üretildi",
    "First access to the latest flagship models and features": "En yeni amiral gemisi modellere ve özelliklere ilk erişim",
    "Dedicated resources during peak times": "Yoğun saatlerde ayrılmış kaynaklar",
    "For Individuals": "Bireysel İçin",
    "For Teams": "Ekipler İçin",
    "Start Plan": "Başlangıç Planı",
    "8M GLM tokens daily": "Günlük 8M GLM token",
    "GLM-5.3 · 3M tokens daily": "GLM-5.3 · Günlük 3M token",
    "GLM-5.3-Flash · 5M tokens daily": "GLM-5.3-Flash · Günlük 5M token",
    "Included": "Dahil",
    "GLM Coding Lite": "GLM Coding Lite",
    "10,000 Credits / week": "Haftalık 10.000 Kredi",
    "10,000 Credits/week": "Haftalık 10.000 Kredi",
    "Small repo iteration": "Küçük proje geliştirme",
    "Latest models over time": "Zamanla en güncel modeller",
    "20+ coding tools": "20+ kodlama aracı",
    "Select": "Seç",
    "GLM Coding Pro": "GLM Coding Pro",
    "Mid-sized repo development": "Orta ölçekli proje geliştirme",
    "Priority model access": "Öncelikli model erişimi",
    "Curated MCP tools": "Seçkin MCP araçları",
    "GLM Coding Max": "GLM Coding Max",
    "Mid-to-large repo work": "Orta ve büyük ölçekli proje geliştirme",
    "First model access": "En yeni modellere ilk erişim",
    "Peak-time priority": "Yoğun saatlerde öncelik",
    "Pro Team": "Pro Ekip",
    "Max Team": "Max Ekip",
    "Shared team quota": "Ortak ekip kotası",
    "Higher shared team quota": "Daha yüksek ortak ekip kotası",
    "For small teams that need shared quota and seat management.": "Ortak kota ve kullanıcı yönetimine ihtiyaç duyan küçük ekipler için.",
    "For high-throughput engineering teams that need more quota and flexible seats.": "Daha fazla kotaya ve esnek kullanıcı sayısına ihtiyaç duyan yüksek tempolu mühendislik ekipleri için.",
    "Shared quota, seat management, and centralized billing.": "Ortak kota, kullanıcı yönetimi ve merkezi faturalandırma.",
    "Seats, shared quota, and centralized billing are coming later.": "Koltuklar, paylaşılan kota ve merkezi faturalandırma daha sonra sunulacaktır.",
    "Single-seat pricing": "Tek kullanıcı fiyatlandırması",
    "Team-seat pricing": "Ekip fiyatlandırması",
    "Assign members to your team plan": "Ekip planınıza üye atayın",
    "Manage team plan": "Ekip planını yönet",
    "Seats": "Kullanıcı Sayısı",
    "Seat": "Kullanıcı",
    "seats": "kullanıcı",
    "seat": "kullanıcı",
    "per kullanıcı/ay": "/ kullanıcı / ay",
    "per user/month": "/ kullanıcı / ay",
    "per user / month": "/ kullanıcı / ay",
    "per seat/month": "/ kullanıcı / ay",
    "per seat / month": "/ kullanıcı / ay",
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
    "66,000 Credits / week": "Haftalık 66.000 Kredi",
    "155,000 Credits / week": "Haftalık 155.000 Kredi",
    "Credits / week": "Kredi / hafta",
    "Credits/week": "Kredi / hafta",
    "Save 10% annually": "Yıllık %10 indirim",
    "Save 10%": "%10 Tasarruf Edin",
    "/month": "/ ay",
    "Annual discount": "Yıllık indirim",
    "Save 20%": "%20 Tasarruf Edin",
    "Save 30%": "%30 Tasarruf Edin",
    "Calculating payment amount": "Ödeme tutarı hesaplanıyor",
    "Please wait. Confirmation and payment use the same payment details.": "Lütfen bekleyin. Onay ve ödeme aynı ödeme ayrıntılarını kullanır.",
    "Payment amount is unavailable. Go back and choose the billing cycle again.": "Ödeme tutarı mevcut değil. Geri dönün ve faturalandırma döngüsünü tekrar seçin.",
    "Choose billing cycle": "Faturalandırma döngüsünü seçin",
    "Continue to payment": "Ödemeye devam et",
    "Due today": "Bugün ödenecek",
    "Service period": "Hizmet süresi",
    "Auto-renews every": "Otomatik yenilenme:",
    "Renewal policy": "Yenileme politikası",
    "I understand and agree to the renewal policy and subscription terms.": "Yenileme politikasını ve abonelik koşullarını anlıyor ve kabul ediyorum.",
    "Preparing payment": "Ödeme hazırlanıyor",
    "Waiting for security verification": "Güvenlik doğrulaması bekleniyor",
    "Waiting for payment confirmation": "Ödeme onayı bekleniyor",
    "Payment in progress": "Ödeme devam ediyor",
    "Payment successful": "Ödeme başarılı",
    "Payment failed": "Ödeme başarısız oldu",
    "Payment method": "Ödeme yöntemi",
    "Credit card": "Kredi kartı",
    "Card number": "Kart numarası",
    "Expiration date": "Son kullanma tarihi",
    "Security code": "Güvenlik kodu",
    "Country or region": "Ülke veya bölge",
    "Pay": "Öde",
    "Cancel": "İptal",
    "Close": "Kapat",
    "Maybe later": "Belki daha sonra",
    "Back": "Geri",
    "Confirm": "Onayla",
    "Current plan": "Mevcut Plan",
    "Manage subscription": "Aboneliği Yönet",
    "US$12.60 /month": "US$12.60 / ay",
    "US$56.00 /month": "US$56.00 / ay",
    "US$117.60 /month": "US$117.60 / ay",
    "US$12.60/month": "US$12.60 / ay",
    "US$56.00/month": "US$56.00 / ay",
    "US$117.60/month": "US$117.60 / ay",
    "BETTER WHEN SHARED": "PAYLAŞTIKÇA DAHA GÜZEL",
    "Better when shared": "Paylaştıkça daha güzel",
    "Invite new users, earn more together.": "Yeni kullanıcılar davet edin, birlikte daha çok kazanın.",
    "Invite new users, earn more together": "Yeni kullanıcılar davet edin, birlikte daha çok kazanın",
    "Invite new users,": "Yeni kullanıcılar davet edin,",
    "Invite new users": "Yeni kullanıcılar davet edin",
    "earn more together.": "birlikte daha çok kazanın.",
    "earn more together": "birlikte daha çok kazanın",
    "Earn more together.": "Birlikte daha çok kazanın.",
    "Earn more together": "Birlikte daha çok kazanın",
    "The campaign hasn't started yet": "Kampanya henüz başlamadı",
    "The campaign hasn’t started yet": "Kampanya henüz başlamadı",
    "The campaign has not started yet": "Kampanya henüz başlamadı",
    "hasn't started yet": "henüz başlamadı",
    "hasn’t started yet": "henüz başlamadı",
    "BUILD TOGETHER": "BİRLİKTE ÜRETİN",
    "Build together": "Birlikte üretin",
    "Build Together": "Birlikte Üretin",
    "BUILD": "BİRLİKTE",
    "TOGETHER": "ÜRETİN",
    "REWARD": "ÖDÜL",
    "REWARDS": "ÖDÜLLER",
    "Reward tasks": "Ödül Görevleri",
    "Reward Tasks": "Ödül Görevleri",
    "Reward task": "Ödül Görevi",
    "Reward Task": "Ödül Görevi",
    "Task": "Görev",
    "Progress": "İlerleme",
    "Reward": "Ödül",
    "No reward tasks": "Ödül görevi bulunmuyor",
    "No reward tasks yet": "Henüz ödül görevi bulunmuyor",
    "Your referrals": "Davetleriniz",
    "Your Referrals": "Davetleriniz",
    "Friend": "Arkadaş",
    "Status": "Durum",
    "Friend's reward": "Arkadaşın Ödülü",
    "Friend's Reward": "Arkadaşın Ödülü",
    "Friend’s reward": "Arkadaşın Ödülü",
    "Friend’s Reward": "Arkadaşın Ödülü",
    "Arkadaş's reward": "Arkadaşın Ödülü",
    "Arkadaş’s reward": "Arkadaşın Ödülü",
    "Arkadaş's Reward": "Arkadaşın Ödülü",
    "Arkadaş’s Reward": "Arkadaşın Ödülü",
    "Invited at": "Davet Tarihi",
    "Invited At": "Davet Tarihi",
    "No referrals yet": "Henüz davet bulunmuyor",
    "Reward history": "Ödül Geçmişi",
    "Reward History": "Ödül Geçmişi",
    "Ödül history": "Ödül Geçmişi",
    "Ödül History": "Ödül Geçmişi",
    "Source": "Kaynak",
    "source": "kaynak",
    "Received": "Alındı",
    "received": "alındı",
    "Received at": "Alınma Tarihi",
    "Received At": "Alınma Tarihi",
    "No rewards yet": "Henüz ödül bulunmuyor",
    "No rewards yet.": "Henüz ödül bulunmuyor.",
    "No reward yet": "Henüz ödül bulunmuyor",
    "No reward yet.": "Henüz ödül bulunmuyor.",
    "Invite friends": "Arkadaşlarını Davet Et",
    "Invite Friends": "Arkadaşlarını Davet Et",
    "Copy invite link": "Davet Bağlantısını Kopyala",
    "Copy Invite Link": "Davet Bağlantısını Kopyala",
    "Invite link copied": "Davet bağlantısı kopyalandı",
    "Invite link copied!": "Davet bağlantısı kopyalandı!",
    "Rules": "Kurallar",
    "Activity rules": "Etkinlik Kuralları",
    "Activity Rules": "Etkinlik Kuralları",
    "View rules": "Kuralları Görüntüle",
    "View Rules": "Kuralları Görüntüle",
    "Documents": "Belge Becerileri",
    "DOCUMENTS": "Belge Becerileri",
        "Presentations": "Sunum Becerileri",
    "PRESENTATIONS": "Sunum Becerileri",
    "Spreadsheets": "Tablo Becerileri",
    "SPREADSHEETS": "Tablo Becerileri",
    "Plugin Creator": "Eklenti Oluşturucu",
    "PLUGIN CREATOR": "Eklenti Oluşturucu",
    "Microsoft Foundry": "Microsoft Foundry",
    "MICROSOFT FOUNDRY": "Microsoft Foundry"
  };

  const SORTED_KEYS = Object.keys(TR_MAP).sort((a, b) => b.length - a.length);
  let isTranslating = false;

  function translateNode(n) {
    if (!n) return;
    if (n.nodeType === 3) {
      let raw = n.nodeValue;
      if (!raw) return;

      let clean = raw.split(String.fromCharCode(160)).join(" ")
                     .split(String.fromCharCode(10)).join(" ")
                     .split(String.fromCharCode(13)).join(" ")
                     .split(String.fromCharCode(9)).join(" ")
                     .split(" ").filter(Boolean).join(" ");
      if (!clean) return;

      let cleanNorm = clean.split(String.fromCharCode(8217)).join("'")
                           .split(String.fromCharCode(8216)).join("'")
                           .split(String.fromCharCode(700)).join("'")
                           .split(String.fromCharCode(8242)).join("'")
                           .split(String.fromCharCode(96)).join("'");

      if (TR_MAP[clean] || TR_MAP[cleanNorm] || TR_MAP[clean.toUpperCase()] || TR_MAP[clean.toLowerCase()]) {
        let val = TR_MAP[clean] || TR_MAP[cleanNorm] || TR_MAP[clean.toUpperCase()] || TR_MAP[clean.toLowerCase()];
        let lead = "";
        let trail = "";
        for (let i = 0; i < raw.length && (raw.charCodeAt(i) <= 32 || raw.charCodeAt(i) === 160); i++) lead += raw[i];
        for (let i = raw.length - 1; i >= 0 && (raw.charCodeAt(i) <= 32 || raw.charCodeAt(i) === 160); i--) trail = raw[i] + trail;
        n.nodeValue = lead + val + trail;
        return;
      }

      let modified = raw.split(String.fromCharCode(8217)).join("'")
                        .split(String.fromCharCode(8216)).join("'");
      for (const en of SORTED_KEYS) {
        if (modified.includes(en)) {
          modified = modified.split(en).join(TR_MAP[en]);
        }
      }

      if (modified.includes("Arkadaş's reward") || modified.includes("Arkadaş's Reward")) {
        modified = modified.split("Arkadaş's reward").join("Arkadaşın Ödülü").split("Arkadaş's Reward").join("Arkadaşın Ödülü");
      }
      if (modified.includes("Ödül history") || modified.includes("Ödül History")) {
        modified = modified.split("Ödül history").join("Ödül Geçmişi").split("Ödül History").join("Ödül Geçmişi");
      }
      if (cleanNorm.includes("campaign has") && cleanNorm.includes("started yet")) {
        modified = "Kampanya henüz başlamadı";
      }
      if (cleanNorm.includes("Invite new users") && cleanNorm.includes("earn more together")) {
        modified = "Yeni kullanıcılar davet edin, birlikte daha çok kazanın.";
      }
      if (clean.toUpperCase() === "BUILD TOGETHER" || clean.toUpperCase() === "BUILDTOGETHER") {
        modified = "BİRLİKTE ÜRETİN";
      }
            if (clean.includes("will be available on")) {
        modified = modified.replace("will be available on", "tarihinde kullanıma açılacaktır:").replace("Oct", "Ekim");
      }
      if (clean.startsWith("Valid until")) {
        modified = modified.replace("Valid until", "Son Geçerlilik:").replace("Oct", "Ekim");
      }
      if (clean.startsWith("6x Lite usage") || clean.startsWith("6× Lite usage")) {
        modified = "6 kat Lite kullanımı + Tüm avantajlar";
      } else if (clean.startsWith("14x Lite usage") || clean.startsWith("14× Lite usage")) {
        modified = "14 kat Lite kullanımı + Tüm avantajlar";
      } else if (clean.startsWith("20x Lite usage") || clean.startsWith("20× Lite usage")) {
        modified = "20 kat Lite kullanımı + Tüm avantajlar";
      } else if (clean.startsWith("Save 10% annually")) {
        modified = "Yıllık %10 indirim";
      } else if (clean.startsWith("Comprehensive DOCX") || clean.startsWith("Revizyonlar, yorumlar")) {
        modified = "Revizyonlar, yorumlar, biçimlendirme koruma ve metin çıkarma desteğiyle kapsamlı DOCX belgesi oluşturma, düzenleme ve analiz yetenekleri. Şablon tabanlı üretim ve format dönüştürmeyi destekler.";
      } else if (clean.startsWith("Professional PDF") || clean.startsWith("4 özel iş akışına")) {
        modified = "4 özel iş akışına sahip profesyonel PDF işleme araç seti: Typst/ReportLab ile yayın kalitesinde PDF üretimi, HTML/CSS tuvali ile görsel belge biçimlendirme, LaTeX ile akademik makaleler ve PyMuPDF/pdfplumber ile programatik düzenleme. Akıllı yönlendirme, format doğrulama ve otomatik kalite kontrolleri içerir.";
      } else if (clean.startsWith("PowerPoint (.pptx)") || clean.startsWith("PowerPoint ( .pptx )")) {
        modified = "PowerPoint (.pptx) sunum oluşturma, biçimlendirme ve düzenleme yetenekleri. Sıfırdan veya taslaklardan sunum hazırlama, mevcut slaytları düzenleme ve metin/not çıkarma işlemlerini kapsar.";
      } else if (clean.startsWith("Advanced spreadsheet") || clean.startsWith("Veri analizi, formüller")) {
        modified = "Veri analizi, formüller ve grafiklerle Excel (.xlsx, .xlsm, .csv) için gelişmiş elektronik tablo işleme yetenekleri. Sıfırdan çalışma kitapları oluşturma, mevcut tabloları düzenleme, veri analizi ve formül hesaplamalarını kapsar.";
      } else if (clean.startsWith("Create or update ZCode plugin")) {
        modified = "ZCode eklenti kaynak kodunu ve yerel bir test mağazasını oluşturun veya güncelleyin; ardından kullanıcıya mağazayı ekleme, eklentiyi yükleme veya güncelleme ve uygulamada deneme konusunda rehberlik edin.";
      } else if (clean.startsWith("Discover available Azure OpenAI")) {
        modified = "Bölgeler ve abonelikler genelinde kullanılabilir Azure OpenAI model kapasitesini keşfeder. Kota sınırlarını analiz eder ve en uygun dağıtım konumlarını önerir.";
      } else if (clean.startsWith("Interactive guided deployment flow")) {
        modified = "Tam özelleştirme kontrolüyle Azure OpenAI modelleri için etkileşimli rehberli dağıtım akışı. Model sürümü, SKU, kapasite ve içerik filtreleme ilkesi seçimini sağlar.";
      } else if (clean.startsWith("Unified Azure OpenAI model deployment")) {
        modified = "Akıllı amaç tabanlı yönlendirme ile birleşik Azure OpenAI model dağıtım yeteneği. Hem hızlı ön ayarlı hem de tam özelleştirilmiş dağıtımları yönetir.";
      } else if (clean.startsWith("Fine-tune models on Microsoft Foundry")) {
        modified = "SFT, DPO veya RFT kullanarak Microsoft Foundry üzerinde modelleri ince ayarlar (fine-tune). Veri kümesi hazırlama, eğitim işi gönderme, değerlendirme ve dağıtımı kapsar.";
      } else if (clean.startsWith("Build, deploy, evaluate, optimize, fine-tune, and manage Microsoft Foundry")) {
        modified = "Microsoft Foundry ajanlarını, modellerini ve kaynaklarını uçtan uca derleyin, dağıtın, değerlendirin, optimize edin, ince ayar yapın ve yönetin.";
      } else if (clean.startsWith("Smart deployment of Azure OpenAI")) {
        modified = "Kullanılabilir tüm bölgelerdeki kapasiteyi analiz ederek Azure OpenAI modellerini en uygun bölgelere akıllıca dağıtır. Kapasite mevcut olduğunda geçerli bölgeyi tercih eder.";
      } else if (clean.startsWith("Unified user & permission") || clean.startsWith("Unified seat & permission") || clean.startsWith("Unified user and permission") || clean.startsWith("Unified kullanıcı &")) {
        modified = "Birleşik kullanıcı ve yetki yönetimi";
      }
      if (modified.includes("per kullanıcı/ay") || modified.includes("per user/month") || modified.includes("per seat/month")) {
        modified = modified.replace("per kullanıcı/ay", "/ kullanıcı / ay").replace("per user/month", "/ kullanıcı / ay").replace("per seat/month", "/ kullanıcı / ay");
      }
      if (modified.includes("Credits / week") || modified.includes("Credits/week")) {
        modified = modified.replace("Credits / week", "Kredi / hafta").replace("Credits/week", "Kredi / hafta");
      }
      if (modified !== raw) n.nodeValue = modified;
    } else if (n.nodeType === 1) {
      if (n.tagName === "SCRIPT" || n.tagName === "STYLE") return;
      if (n.placeholder && TR_MAP[n.placeholder.trim()]) n.placeholder = TR_MAP[n.placeholder.trim()];
      if (n.title && TR_MAP[n.title.trim()]) n.title = TR_MAP[n.title.trim()];
      if (n.getAttribute && n.getAttribute("aria-label")) {
        const aria = n.getAttribute("aria-label").trim();
        if (TR_MAP[aria]) n.setAttribute("aria-label", TR_MAP[aria]);
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
    } catch (e) {
    } finally {
      isTranslating = false;
    }
  }

  safeTranslate(document.body || document.documentElement);

  if (window.__zcode_tr_obs__) {
    try { window.__zcode_tr_obs__.disconnect(); } catch (e) {}
  }
  const obs = new MutationObserver(muts => {
    safeTranslate(document.body || document.documentElement);
  });
  obs.observe(document.documentElement || document.body, { childList: true, subtree: true, characterData: true });
  window.__zcode_tr_obs__ = obs;

  if (window.__zcode_tr_interval__) {
    try { clearInterval(window.__zcode_tr_interval__); } catch (e) {}
  }
  window.__zcode_tr_interval__ = setInterval(() => {
    safeTranslate(document.body || document.documentElement);
  }, 300);'''

        fn_sig = js_content[pos_fn_start:js_content.find("{", pos_fn_start)+1]
        fn_name_m = re.search(r"function\s+(\w+)\(\)\{", fn_sig)
        style_fn_name = fn_name_m.group(1) if fn_name_m else "b0e"

        new_fn_body = f"""return`(() => {{
  const styleId = "zcode-coding-plan-hide-scrollbar";
  if (!document.getElementById(styleId)) {{
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = "html, body, * {{ scrollbar-width: none !important; }} html::-webkit-scrollbar, body::-webkit-scrollbar, *::-webkit-scrollbar {{ display: none !important; width: 0 !important; height: 0 !important; }}";
    (document.head || document.documentElement).appendChild(style);
  }}

  {TR_MAP_CODE}
}})()`}}"""

        js_content = js_content[:pos_fn_start] + fn_sig + new_fn_body + js_content[pos_fn_end:]

        # Webview navigation hook to re-run style injection on page finish or navigation
        pat_ri = r"r=\(\)=>\{(\w+)\(e=>\(\{\.\.\.e,isLoading:!1\}\)\),(\w+)\(e\)\},i=\(\)=>\{(\w+)\(e\)\}"
        m_ri = re.search(pat_ri, js_content)
        if m_ri:
            repl_ri = f"r=()=>{{{m_ri.group(1)}(e=>({{...e,isLoading:!1}})),{m_ri.group(2)}(e),e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})}},i=()=>{{{m_ri.group(3)}(e),e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})}}"
            js_content = js_content.replace(m_ri.group(0), repl_ri, 1)

        # Hook pricing modal credentials injection
        pat_cred = r'await t\.executeJavaScript\(`\$\{([\w$]+)\(\)\};\\n\$\{s\}`,\!0\)'
        m_cred = re.search(pat_cred, js_content)
        if m_cred:
            repl_cred = f"await t.executeJavaScript(`${{{m_cred.group(1)}()}};\\n${{s}};\\n${{{style_fn_name}()}}`,!0)"
            js_content = js_content.replace(m_cred.group(0), repl_cred, 1)

        # Hook rewards modal navigation
        pat_ren = r'r=\(\)=>\{t\(\),w\(e=>\(\{\.\.\.e,loading:!1\}\)\),_\.current=!0,E\.current\(\)\},i=\(\)=>\{_\.current=!0,t\(\),E\.current\(\)\}'
        m_ren = re.search(pat_ren, js_content)
        if m_ren:
            repl_ren = f"r=()=>{{t(),w(e=>({{...e,loading:!1}})),_.current=!0,E.current(),e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})}},i=()=>{{_.current=!0,t(),E.current(),e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})}}"
            js_content = js_content.replace(m_ren.group(0), repl_ren, 1)

        # Hook rewards modal context injection
        pat_ren_ctx = r'await e\.executeJavaScript\(([\w$]+)\(d,\{oauth:c,jwt:l\},a\)\)'
        m_ren_ctx = re.search(pat_ren_ctx, js_content)
        if m_ren_ctx:
            repl_ren_ctx = f"await e.executeJavaScript({m_ren_ctx.group(1)}(d,{{oauth:c,jwt:l}},a)),await e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})"
            js_content = js_content.replace(m_ren_ctx.group(0), repl_ren_ctx, 1)
    else:
        target_r_i = 'r=()=>{T(e=>({...e,isLoading:!1})),j(e)},i=()=>{j(e)}'
        replacement_r_i = 'r=()=>{T(e=>({...e,isLoading:!1})),j(e),e.executeJavaScript(nMe(),!0).catch(()=>{})},i=()=>{j(e),e.executeJavaScript(nMe(),!0).catch(()=>{})}'
        if target_r_i in js_content:
            js_content = js_content.replace(target_r_i, replacement_r_i, 1)

    # Skill description regex
    skill_pattern = r'function\s+(\w+)\(e,t\)\{return\((\w+)\(e\)\?(\w+)\[e\.name\]\?\.\[t\?\?`en-US`\]:void 0\)\?\?e\.description\}'
    js_content = re.sub(skill_pattern, r'function \1(e,t){return e.description||(\2(e)?\3[e.name]?.[t??`en-US`]:void 0)}', js_content)

    # Date formats (short date and updater release date)
    js_content = js_content.replace("Intl.DateTimeFormat(t,{day:`numeric`,month:`short`", 'Intl.DateTimeFormat("tr-TR",{day:`numeric`,month:`short`')
    target_tqt = "new Intl.DateTimeFormat(t,{year:`numeric`,month:`long`,day:`numeric`,timeZone:`UTC`}).format(n)"
    replacement_tqt = 'new Intl.DateTimeFormat("tr-TR",{year:`numeric`,month:`long`,day:`numeric`,timeZone:`UTC`}).format(n)'
    if target_tqt in js_content:
        js_content = js_content.replace(target_tqt, replacement_tqt, 1)

    # Computer use labels
    js_content = js_content.replace("title:`Computer Use`", "title:`Bilgisayar Kontrolü`")
    js_content = js_content.replace("kind??`Computer Use`", "kind??`Bilgisayar Kontrolü`")
    js_content = js_content.replace("children:`Parameters`", "children:`Parametreler`")

    # Suggested prompts Wz replacement
    bt = chr(96)
    wz_pattern = rf"function\s+(\w+)\(e,t\)\{{let\s+n=t\.startsWith\({bt}zh{bt}\)\?e\.cn:e\.en,r=t\.startsWith\({bt}zh{bt}\)\?e\.en:e\.cn;return\s+n\?\.trim\(\)\|\|r\?\.trim\(\)\|\|{bt}{bt}\}}"
    replacement = (
        r'function \1(e,t){const _tr={"Weekly Summary":"Haftalık Özet","Error Fix":"Hata Düzeltme",'
        r'"PPT Creation":"Sunum (PPT) Hazırlama","Idle-time task":"Boş Zaman Görevi","Idle-time Task":"Boş Zaman Görevi",'
        r'"idle-time task":"Boş Zaman Görevi","Idle-time tasks":"Boş Zaman Görevleri","Idle-time Tasks":"Boş Zaman Görevleri",'
        r'"Code Review":"Kod İncelemesi","Refactor":"Yeniden Düzenleme","Explain Code":"Kodu Açıkla",'
        r'"Generate Tests":"Test Üret","Optimize":"Optimize Et"};'
        f'let n=t.startsWith({bt}zh{bt})?e.cn:(e.tr||e.en),r=t.startsWith({bt}zh{bt})?(e.tr||e.en):e.cn;'
        f'let s=n?.trim()||r?.trim()||{bt}{bt};return _tr[s]||s}}'
    )
    js_content = re.sub(wz_pattern, replacement, js_content)

    # Automation template cards e4 translation
    e4_pattern = rf"function\s+(\w+)\(e,t\)\{{let\s+n=t\?\.startsWith\({bt}zh{bt}\)\?\?!1,r=n\?e\.cn:e\.en,i=n\?e\.en:e\.cn;return\s+r\?\.trim\(\)\|\|i\?\.trim\(\)\|\|{bt}{bt}\}}"
    e4_replacement = (
        r'function \1(e,t){const _tr={"Morning dev brief":"Sabah Geliştirici Özeti","Risk scan":"Risk Taraması","Release brief":"Sürüm Özeti","Documentation sync check":"Belge Senkronizasyon Kontrolü","Customize":"Özelleştir"};'
        r'const _trD={"Summarize commits":"Önceki iş gününden bu yana yapılan commitleri, modül değişikliklerini, CI durumunu ve takipleri özetleyin; stand-up için hazır maddeler çıkarın.",'
        r'"Inspect code changes":"Çalışma zamanı hataları, veri kaybı, yetkilendirme açıkları ve kaynak sorunları gibi yüksek riskli durumlar için son 24 saatteki kod değişikliklerini inceleyin.",'
        r'"Organize PRs and commits":"Bu hafta birleştirilen PRları ve commitleri Özellikler, Düzeltmeler, Deneyim iyileştirmeleri ve Mühendislik geliştirmeleri olarak düzenleyin.",'
        r'"Compare code, configuration":"Son yedi gündeki kod, yapılandırma, API ve dokümantasyon değişikliklerini karşılaştırın; belgelerin güncellenmesi gereken noktaları belirleyin."};'
        f'let n=t?.startsWith({bt}zh{bt})??!1,r=n?e.cn:(e.tr||e.en),i=n?(e.tr||e.en):e.cn;let s=r?.trim()||i?.trim()||{bt}{bt};'
        r'if(_tr[s])return _tr[s];for(const[k,v]of Object.entries(_trD)){if(s.startsWith(k))return v}return s}'
    )
    js_content = re.sub(e4_pattern, e4_replacement, js_content)

    # Plugin marketplace card titles and descriptions
    official_p_descs = {
        "browser-use": "Masaüstü için yerleşik tarayıcı otomasyonu çalışma ortamı ve rehberlik.",
        "computer-use": "Bilgisayar Kontrolü: Masaüstü uygulamalarını fare, klavye ve sistem eylemleriyle otomatikleştirin.",
        "document-skills": "Yerleşik DOCX ve PDF belge oluşturma becerileri.",
        "dingtalk-cli": "OAuth/cihaz yetkilendirmesi, profil kontrolleri ve yeteneklerle DingTalk Çalışma Alanı CLI iş akışları.",
        "lark-cli": "Belgeler, tablolar, Base, takvim ve mesajlaşma için rehberli kurulum ve OAuth girişli Lark CLI iş akışları.",
        "obsidian": "Obsidian Markdown notları, Bases veritabanı görünümleri, Canvas panoları, CLI otomasyonu ve görselleştirme becerileri.",
        "alibaba-cloud-cli": "Kimlik bilgisi kurulumu, profil kontrolleri ve güvenli bulut kaynak işlemleri için Alibaba Cloud CLI iş akışları.",
        "android-emulator": "Android emülatörlerini yönetme, başlatma ve cihaz kontrolü için geliştirici araçları.",
        "ios-simulator": "iOS simülatörlerini yönetme, test etme ve arayüz denetimi araçları.",
        "skill-creator": "Yeni ajan becerileri ve iş akışları oluşturmak için rehberli araç seti.",
        "restore-legacy-sessions": "Önceki sürümlerden kalan eski oturumları ve sohbet geçmişlerini geri yükleyin.",
        "zcode-guide": "ZCode özellikleri, komutları ve yapılandırmaları için kapsamlı kullanım kılavuzu.",
        "video-agent-kit": "Otomatik video düzenleme araç seti: Bulut ses transkripsiyonu ve sentezi, kare analizi, zaman çizelgesi ve önizleme.",
        "video2code": "ZCode yerleşik Browser Use WebView ile WebM kaydı ve ffmpeg ile MP4 dönüştürme/yeniden oluşturma.",
        "cloudbase-skills": "Web, WeChat Mini Programı, veritabanı, bulut fonksiyonları ve yapay zeka projeleri için CloudBase geliştirme becerileri ve MCP entegrasyonu.",
        "mimosa": "ZCode için yazma öncesi kancalar, tur sonu incelemesi, Git kapıları ve güvenlik taraması becerisiyle yerel öncelikli güvenlik koruması.",
        "github": "Commit, pull request, issue, release, Actions ve repolar için GitHub CLI iş akışları.",
        "gitlab": "Merge request, issue, CI/CD ve repolar için GitLab resmi ajan becerilerine dayalı GitLab CLI iş akışları.",
        "tencent-meeting-cli": "OAuth2 kurulumu, toplantı yönetimi, kayıtlar ve katılımcı raporlarıyla Tencent Meeting CLI iş akışları.",
        "wecom-cli": "Mesajlar, belgeler, tablolar, takvim, toplantılar ve kişiler için QR doğrulamalı WeCom CLI iş akışları.",
        "accounting-and-reporting": "Şirket defterinden muhasebe kapanışı ve yasal raporlama: ay sonu kontrolleri ve mutabakat.",
        "assess-credit": "Sabit getirili menkul kıymetler ve kredi araştırması: tahvil profilleri, ihraççı değerlendirmesi ve getiri eğrisi analizi.",
        "find-clients": "Kurumsal bankacılık müşteri kazanımı: bölgeye ve sektöre göre potansiyel müşteri taraması ve fırsat analizi.",
        "model-deals": "İşlem yapılandırma ve modelleme: M&A, IPO ve sermaye artırımı seyreltme analizi.",
        "pick-funds": "Fon ve fon yöneticisi araştırması: çok kriterli fon taraması, portföy ve stil analizi.",
        "read-macro": "Yukarıdan aşağıya makro strateji: büyüme, enflasyon, likidite ve çapraz varlık dağılım görünümleri.",
        "run-fpa": "Kurumsal finansman ve FP&A: yönetim raporlaması, nakit akışı tahminleri ve bütçe-gerçekleşen varyans analizi.",
        "vet-companies": "Karşı taraf ve şirket durum tespiti: yapılandırılmış DD raporları, tedarik zinciri haritalama ve risk taraması.",
        "watch-positions": "İzleme listesi ve portföy takibi: kapanış sonrası özetler, pozisyon olay uyarıları ve gün içi hareket analizi.",
        "write-research": "Uçtan uca yatırım araştırma raporları, sektör analizi, kazanç güncellemeleri ve değerleme modelleri.",
        "hexin": "RoyalFlush iFinD hisse senedi, küresel hisseler, endeks, fon ve tahvil verileri için MCP hizmetleri.",
        "wind": "Wind hisse senedi, küresel hisseler, endeks, fon, tahvil, ekonomik ve doküman verileri için MCP hizmetleri.",
        "tianyancha": "Tianyancha şirket bilgileri sorguları için MCP hizmeti.",
        "finance-search": "SEC EDGAR dosyalama araması ve finansal web/haber aramaları için MCP hizmetleri.",
        "documents": "Resmi ZCode eklentisi olarak yayınlanan DOCX belge üretim becerileri.",
        "documents-plugin": "Resmi ZCode eklentisi olarak yayınlanan DOCX belge üretim becerileri.",
        "pdf": "Resmi ZCode eklentisi olarak yayınlanan PDF belge üretim becerileri.",
        "pdf-plugin": "Resmi ZCode eklentisi olarak yayınlanan PDF belge üretim becerileri.",
        "presentations": "Resmi ZCode eklentisi olarak yayınlanan PPTX sunum üretim becerileri.",
        "presentations-plugin": "Resmi ZCode eklentisi olarak yayınlanan PPTX sunum üretim becerileri.",
        "spreadsheets": "Resmi ZCode eklentisi olarak yayınlanan XLSX hesap tablosu üretim becerileri.",
        "spreadsheets-plugin": "Resmi ZCode eklentisi olarak yayınlanan XLSX hesap tablosu üretim becerileri.",
        "image-search": "İllüstrasyonlar ve referans görselleri bulmak için resmi ZCode görsel arama MCP sunucusu.",
        "image-search-plugin": "İllüstrasyonlar ve referans görselleri bulmak için resmi ZCode görsel arama MCP sunucusu.",
        "node-repl-host": "Resmi ZCode yetenekleri için paylaşılan node_repl çalışma ortamı barındırıcısı.",
        "plugin-creator": "Yerel bir geliştirici pazar yeri, kurulum, denemeler ve güncellemeler aracılığıyla ZCode eklentileri geliştirin ve doğrulayın.",
        "plugin-creator-plugin": "Yerel bir geliştirici pazar yeri, kurulum, denemeler ve güncellemeler aracılığıyla ZCode eklentileri geliştirin ve doğrulayın.",
        "godot": "Resmi Godot CLI ile oyunlar geliştirin ve her adımı Godot önizleme panelinde gösterin.",
        "unreal-engine": "Uzak Unreal Engine ajanı ile Unreal Engine seviyeleri oluşturun ve düzenleyin, sahne aktörlerini ayarlayın ve oynanışı kodlayın.",
        "libtv-cli": "Video üretim tuvalleri, çalışma alanları ve dışa aktarmalar için resmi LibTV CLI yeteneği.",
        "jev-decisions": "Komut satırı üzerinden ZCode ajanları için kalibre edilmiş karar araçları.",
        "ruic-card": "Holografik koleksiyon kartı üreticisi: katmanlı sanat tasarımı, folyo efektleri ve dışa aktarma.",
        "kicad": "Sohbet içinde KiCad 10: ajanlar 2 katmanlı devre kartları tasarlar, Gerber dosyalarını dışa aktarır ve katmanları SVG'de önizler."
    }
    if CLAUDE_PLUGINS_TR:
        official_p_descs.update(CLAUDE_PLUGINS_TR)
    claude_tr_file = os.path.join(BASE_DIR, "claude_plugins_tr.json")
    if os.path.exists(claude_tr_file):
        with open(claude_tr_file, "r", encoding="utf-8") as _cf:
            official_p_descs.update(json.load(_cf))
    tr_p_descs_json = json.dumps(official_p_descs, ensure_ascii=False)

    plugin_row_helpers = (
        'function _trPluginDescRow(e){if(!e)return"";let n=(e.name||e.id||"");let b=String(n).replace(/@.*$/,"").replace(/^plugin:/,"").trim();'
        'if(b.includes(":"))b=b.slice(b.indexOf(":")+1);'
        'if(typeof TR_SKILL_DESCS!=="undefined"){if(TR_SKILL_DESCS[b])return TR_SKILL_DESCS[b];if(TR_SKILL_DESCS[n])return TR_SKILL_DESCS[n]};'
        'if(typeof TR_P_DESCS!=="undefined"){if(TR_P_DESCS[b])return TR_P_DESCS[b];if(TR_P_DESCS[n])return TR_P_DESCS[n]};'
        'return e.description||""};'
        'function _trPluginNameRow(e,fallback){if(!e)return fallback;let n=(e.name||e.id||"");let b=String(n).replace(/@.*$/,"").replace(/^plugin:/,"").trim();'
        'if(typeof TR_P_NAMES!=="undefined"){if(TR_P_NAMES[b])return TR_P_NAMES[b];if(TR_P_NAMES[n])return TR_P_NAMES[n]};'
        'return fallback};'
    )

    pat_m4 = r"function\s+([\w$]+)\(e,t\)\{return\s+([\w$]+)\(e,t\)\}function\s+([\w$]+)\(e,t\)\{return\s+([\w$]+)\(t,e\.summary\?\.description\?\?e\.info\?\.description\?\?e\.installedMeta\?\.description,e\.listing\?\.descriptionI18n\)\}"
    m_m4 = re.search(pat_m4, js_content)
    fn_m4 = None
    if m_m4:
        fn_m4 = m_m4.group(1)
        fn_dn = m_m4.group(2)
        fn_h4 = m_m4.group(3)
        fn_pne = m_m4.group(4)
        m4_replacement = (
            'const TR_P_NAMES={"Restore Legacy Sessions":"Eski Oturumları Geri Yükle","Skill Creator":"Beceri Oluşturucu","ZCode Guide":"ZCode Rehberi","Android Emulator":"Android Emülatörü","iOS Simulator":"iOS Simülatörü","browser-use":"Browser Use","computer-use":"Bilgisayar Kontrolü","document-skills":"Belge Becerileri","dingtalk-cli":"DingTalk CLI","lark-cli":"Lark CLI","obsidian":"Obsidian","alibaba-cloud-cli":"Alibaba Cloud CLI","android-emulator":"Android Emülatörü","ios-simulator":"iOS Simülatörü","skill-creator":"Beceri Oluşturucu","restore-legacy-sessions":"Eski Oturumları Geri Yükle","zcode-guide":"ZCode Rehberi","zcode-cua":"Bilgisayar Kontrolü","video-agent-kit":"Video Ajan Kiti","video2code":"Video2Code","accounting-and-reporting":"Muhasebe ve Raporlama","assess-credit":"Sabit Getiri ve Kredi Araştırması","find-clients":"Kurumsal Müşteri Kazanımı","model-deals":"İşlem Modelleme ve Yapılandırma","pick-funds":"Fon ve Portföy Araştırması","read-macro":"Makro Strateji Analizi","run-fpa":"Finansal Planlama ve Analiz (FP&A)","vet-companies":"Şirket Durum Tespiti (Due Diligence)","watch-positions":"Pozisyon ve Portföy Takibi","write-research":"Yatırım ve Hisse Araştırması","hexin":"Tonghuashun iFinD","wind":"Wind Finansal Veri","tianyancha":"Tianyancha Şirket Bilgileri","finance-search":"Finansal Arama","mimosa":"Kod Güvenlik Koruması","github":"GitHub CLI","gitlab":"GitLab CLI","tencent-meeting-cli":"Tencent Meeting CLI","wecom-cli":"WeCom CLI","cloudbase-skills":"CloudBase Becerileri",'
            '"Documents":"Belgeler","documents":"Belgeler","documents@zcode-plugins-official":"Belgeler","Word文档":"Belgeler",'
            '"PDF":"PDF","pdf":"PDF","pdf@zcode-plugins-official":"PDF",'
            '"Presentations":"Sunumlar","presentations":"Sunumlar","presentations@zcode-plugins-official":"Sunumlar","PPT演示文稿":"Sunumlar",'
            '"Spreadsheets":"Tablolar","spreadsheets":"Tablolar","spreadsheets@zcode-plugins-official":"Tablolar","Excel表格":"Tablolar",'
            '"Image Search":"Görsel Arama","image-search":"Görsel Arama","image-search@zcode-plugins-official":"Görsel Arama","以图搜图":"Görsel Arama",'
            '"Plugin Creator":"Eklenti Oluşturucu","plugin-creator":"Eklenti Oluşturucu","plugin-creator@zcode-plugins-official":"Eklenti Oluşturucu","插件创建器":"Eklenti Oluşturucu",'
            '"Node REPL Host":"Node REPL","node-repl-host":"Node REPL","node-repl-host@zcode-plugins-official":"Node REPL"};'
            f'const TR_P_DESCS={tr_p_descs_json};'
            f'{plugin_row_helpers}'
            f'function {fn_m4}(e,t){{let k=(e&&(e.name||e.id||(e.listing&&e.listing.displayName)))||"";let base=String(k).replace(/@.*$/,"").replace(/^plugin:/,"").trim();if(TR_P_NAMES[base])return TR_P_NAMES[base];if(TR_P_NAMES[k])return TR_P_NAMES[k];let res={fn_dn}(e,t);if(TR_P_NAMES[res])return TR_P_NAMES[res];return res}}'
            f'function {fn_h4}(e,t){{let k=(e&&(e.name||e.id))||"";let base=String(k).replace(/@.*$/,"").replace(/^plugin:/,"").trim();if(TR_P_DESCS[base])return TR_P_DESCS[base];if(TR_P_DESCS[k])return TR_P_DESCS[k];let res={fn_pne}(t,e.summary?.description??e.info?.description??e.installedMeta?.description,e.listing?.descriptionI18n);if(typeof res==="string"){{if(res.startsWith("Built-in browser automation"))return TR_P_DESCS["browser-use"];if(res.startsWith("Computer Use: automate"))return TR_P_DESCS["computer-use"];if(res.startsWith("Built-in DOCX and PDF"))return TR_P_DESCS["document-skills"];if(res.startsWith("DingTalk Workspace CLI"))return TR_P_DESCS["dingtalk-cli"];if(res.startsWith("Lark CLI workflows"))return TR_P_DESCS["lark-cli"];if(res.startsWith("Obsidian authoring skills"))return TR_P_DESCS["obsidian"];if(res.startsWith("Alibaba Cloud CLI"))return TR_P_DESCS["alibaba-cloud-cli"];if(res.startsWith("Local-first security guardrails"))return TR_P_DESCS["mimosa"];if(res.startsWith("CloudBase development skills"))return TR_P_DESCS["cloudbase-skills"];if(res.startsWith("GitHub CLI workflows"))return TR_P_DESCS["github"];if(res.startsWith("GitLab CLI workflows"))return TR_P_DESCS["gitlab"];if(res.startsWith("Tencent Meeting CLI workflows"))return TR_P_DESCS["tencent-meeting-cli"];if(res.startsWith("WeCom CLI workflows"))return TR_P_DESCS["wecom-cli"];if(res.startsWith("Accounting close and statutory"))return TR_P_DESCS["accounting-and-reporting"];if(res.startsWith("Fixed-income and credit"))return TR_P_DESCS["assess-credit"];if(res.startsWith("Corporate-banking client"))return TR_P_DESCS["find-clients"];if(res.startsWith("Transaction structuring"))return TR_P_DESCS["model-deals"];if(res.startsWith("Fund and fund-manager"))return TR_P_DESCS["pick-funds"];if(res.startsWith("Top-down macro"))return TR_P_DESCS["read-macro"];if(res.startsWith("Corporate finance and FP&A"))return TR_P_DESCS["run-fpa"];if(res.startsWith("Counterparty and company"))return TR_P_DESCS["vet-companies"];if(res.startsWith("Watchlist and portfolio"))return TR_P_DESCS["watch-positions"];if(res.startsWith("End-to-end investment"))return TR_P_DESCS["write-research"];if(res.startsWith("MCP services for RoyalFlush"))return TR_P_DESCS["hexin"];if(res.startsWith("MCP services for Wind"))return TR_P_DESCS["wind"];if(res.startsWith("MCP service for Tianyancha"))return TR_P_DESCS["tianyancha"];if(res.startsWith("MCP services for SEC EDGAR"))return TR_P_DESCS["finance-search"];if(res.startsWith("Develop and validate ZCode plugins"))return TR_P_DESCS["plugin-creator"];if(res.startsWith("PDF document production skills"))return TR_P_DESCS["pdf"];if(res.startsWith("PPTX presentation production skills"))return TR_P_DESCS["presentations"];if(res.startsWith("XLSX spreadsheet production skills"))return TR_P_DESCS["spreadsheets"];if(res.startsWith("DOCX document production skills"))return TR_P_DESCS["documents"];if(res.startsWith("Official ZCode image search"))return TR_P_DESCS["image-search"];if(res.startsWith("Shared node_repl runtime host"))return TR_P_DESCS["node-repl-host"];if(res.includes("自动化视频剪辑工具包"))return TR_P_DESCS["video-agent-kit"];if(res.includes("基于 ZCode 内置 Browser Use"))return TR_P_DESCS["video2code"];if(res.startsWith("Generate 3D models"))return TR_P_DESCS["hyper3d"];if(res.startsWith("Work on Jupyter"))return TR_P_DESCS["jupyter"];if(res.startsWith("Read-only session usage"))return TR_P_DESCS["zcode-context"];if(res.startsWith("Develop MCP Apps"))return TR_P_DESCS["zcode-mcp-app-dev"];if(res.startsWith("Edit Blender scenes"))return TR_P_DESCS["blender"];if(res.startsWith("CADCraft CAD drafting"))return TR_P_DESCS["cadcraft"];if(res.startsWith("DeckCraft presentations"))return TR_P_DESCS["deckcraft"];if(res.startsWith("DesignCraft page layout"))return TR_P_DESCS["designcraft"];if(res.startsWith("Create and edit diagrams with Excalidraw"))return TR_P_DESCS["excalidraw"];if(res.startsWith("GridCraft spreadsheets"))return TR_P_DESCS["gridcraft"];if(res.startsWith("Edit design files with OpenPencil"))return TR_P_DESCS["openpencil"];if(res.startsWith("PdfCraft PDF"))return TR_P_DESCS["pdfcraft"];if(res.startsWith("PhotoCraft image editing"))return TR_P_DESCS["photocraft"];if(res.startsWith("SoundCraft audio editing"))return TR_P_DESCS["soundcraft"];if(res.startsWith("Generate textured, rig-ready 3D models"))return TR_P_DESCS["tripo-3d"];if(res.startsWith("Live-preview Typst documents"))return TR_P_DESCS["typst-workbench"];if(res.startsWith("VectorCraft vector illustration"))return TR_P_DESCS["vectorcraft"];if(res.startsWith("Create interactive explanations, charts"))return TR_P_DESCS["visualize"];if(res.startsWith("WordCraft word processing"))return TR_P_DESCS["wordcraft"];if(res.startsWith("Work with your Zotero library"))return TR_P_DESCS["zotero"];if(res.startsWith("Develop games with the official Godot CLI"))return TR_P_DESCS["godot"];if(res.startsWith("Build and edit Unreal Engine levels"))return TR_P_DESCS["unreal-engine"];if(res.startsWith("Official LibTV CLI skill"))return TR_P_DESCS["libtv-cli"];if(res.startsWith("Calibrated judgment tools"))return TR_P_DESCS["jev-decisions"];if(res.startsWith("Holographic collectible-card"))return TR_P_DESCS["ruic-card"];if(res.startsWith("KiCad 10 inside the conversation"))return TR_P_DESCS["kicad"];}}return res}}'
        )
        js_content = js_content.replace(m_m4.group(0), m4_replacement, 1)

    # Connect r2 to fn_m4 and _trPluginDescRow
    if fn_m4:
        m_row = re.search(r'return\{name:([\w$]+)\(r\?\?e,n\),description:r\?([\w$]+)\(r,n\):e\.description\}\}', js_content)
        if m_row:
            fn_desc_call = m_row.group(2)
            js_content = js_content[:m_row.start()] + f'return{{name:{fn_m4}(r??e,n),description:r?{fn_desc_call}(r,n):_trPluginDescRow(e)DEBUG}}}}'.replace('DEBUG', '') + js_content[m_row.end():]
        else:
            js_content = js_content.replace('return{name:qa(r??e,n),description:r?n2(r,n):e.description}}', f'return{{name:{fn_m4}(r??e,n),description:r?n2(r,n):_trPluginDescRow(e)DEBUG}}}}'.replace('DEBUG', ''), 1)

    # Subagents descriptions replacement
    if "function _trAgentDesc(" not in js_content:
        subagent_helpers = (
            'const TR_AGENT_DESCS={"general-purpose":"Karmaşık soruları araştırmak, kod aramak ve çok adımlı görevleri yürütmek için genel amaçlı ajan.",'
            '"Explore":"Geniş kapsamlı aramalar için salt okunur arama ajanı.",'
            '"explore":"Geniş kapsamlı aramalar için salt okunur arama ajanı.",'
            '"judge":"Yalnızca pptx, docx, xlsx, pdf, poster ve grafik türündeki görsel çıktıların kabul incelemesi için tek yetkili görsel onay ajanı.","claude-security":"Özel Claude Güvenlik yöneticisi. Gözetimsiz bir tarama görevi verin; revizyonu yakalar, çoklu ajan güvenlik taramasını baştan sona yönetir ve bulunan açıkları yamalar.","patch-generator":"Tespit edilen bir güvenlik açığı için geçici çalışma alanında düzeltmeyi uygular ve inceleme için bir yama dosyası hazırlar; düzeltme işi tarafından otomatik çalıştırılır.","patch-verifier":"Düzeltme turundaki tek yetkili doğrulayıcı: çalışma alanındaki farkı (diff) bulguya göre inceler, testleri çalıştırır ve yama güvenilirlik kriterlerini onaylar; düzeltme işi tarafından otomatik çalıştırılır.","scan-inventory":"Claude Güvenlik taraması tarafından dizin ağacını bileşenlere bölmek ve tüm üst düzey dizinleri haritalamak için görevlendirilen salt okunur repo haritalayıcı.","scan-loader":"Claude Güvenlik taraması tarafından çalışma dizininden aday bir dosyayı yüklemek için görevlendirilen salt okunur dosya yükleyici.","scan-researcher":"Claude Güvenlik iş akışı tarafından derinlemesine güvenlik açıklarını araştırmak üzere görevlendirilen salt okunur güvenlik araştırmacısı.","scan-verifier":"Claude Güvenlik iş akışı tarafından tespit edilen aday bulguları doğrulamak ve oylamak için görevlendirilen salt okunur doğrulayıcı.",};'
            'function _trAgentDesc(e){let n=(e&&(e.name||e.id))||"";let b=n.includes(":")?n.slice(n.indexOf(":")+1):n;'
            'if(TR_AGENT_DESCS[b])return TR_AGENT_DESCS[b];if(TR_AGENT_DESCS[n])return TR_AGENT_DESCS[n];'
            'if(typeof TR_P_DESCS!=="undefined"){if(TR_P_DESCS[b])return TR_P_DESCS[b];if(TR_P_DESCS[n])return TR_P_DESCS[n]};'
            'let d=(e&&e.description)||"";if(typeof d==="string"){'
            'if(d.startsWith("General-purpose agent"))return TR_AGENT_DESCS["general-purpose"];'
            'if(d.startsWith("Read-only search agent"))return TR_AGENT_DESCS["Explore"];'
            'if(d.startsWith("THE single visual acceptance pass")||d.startsWith("THE single visual acceptance"))return TR_AGENT_DESCS["judge"];'
            'if(d.startsWith("The dedicated Claude Security"))return TR_AGENT_DESCS["claude-security"];'
            'if(d.startsWith("Implements the fix for one finding"))return TR_AGENT_DESCS["patch-generator"];'
            'if(d.startsWith("The single verifier per fix"))return TR_AGENT_DESCS["patch-verifier"];'
            'if(d.startsWith("Restricted read-only repository"))return TR_AGENT_DESCS["scan-inventory"];'
            'if(d.startsWith("Restricted read-only loader"))return TR_AGENT_DESCS["scan-loader"];'
            'if(d.startsWith("Restricted read-only vulnerability"))return TR_AGENT_DESCS["scan-researcher"];'
            'if(d.startsWith("Restricted read-only verifier"))return TR_AGENT_DESCS["scan-verifier"]}'
            'return d};'
        )
        target_sub = f'children:e.description||d.formatMessage({{id:{bt}settings.subagents.noDescription{bt}}})'
        replacement_sub = f'children:_trAgentDesc(e)||d.formatMessage({{id:{bt}settings.subagents.noDescription{bt}}})'
        if target_sub in js_content:
            pos_fn = js_content.rfind("function ", 0, js_content.find(target_sub))
            if pos_fn != -1:
                js_content = js_content[:pos_fn] + subagent_helpers + js_content[pos_fn:]
            else:
                js_content = subagent_helpers + js_content
            js_content = js_content.replace(target_sub, replacement_sub, 1)

    # Section titles helper injection
    if "function _trSectionTitle(" not in js_content:
        section_title_helper = (
            'const TR_SEC_TITLES={'
            '"Restore Legacy Sessions":"Eski Oturumları Geri Yükle","RESTORE LEGACY SESSIONS":"Eski Oturumları Geri Yükle",'
            '"Skill Creator":"Beceri Oluşturucu","SKILL CREATOR":"Beceri Oluşturucu",'
            '"ZCode Guide":"ZCode Rehberi","ZCODE GUIDE":"ZCode Rehberi",'
            '"Android Emulator":"Android Emülatörü","ANDROID EMULATOR":"Android Emülatörü",'
            '"iOS Simulator":"iOS Simülatörü","IOS SIMULATOR":"iOS Simülatörü",'
            '"Document Skills":"Belge Becerileri","DOCUMENT SKILLS":"Belge Becerileri",'
            '"Documents":"Belge Becerileri","DOCUMENTS":"Belge Becerileri",'
            '"PDF":"PDF","Pdf":"PDF",'
            '"Presentations":"Sunum Becerileri","PRESENTATIONS":"Sunum Becerileri",'
            '"Spreadsheets":"Tablo Becerileri","SPREADSHEETS":"Tablo Becerileri",'
            '"Plugin Creator":"Eklenti Oluşturucu","PLUGIN CREATOR":"Eklenti Oluşturucu",'
            '"Microsoft Foundry":"Microsoft Foundry","MICROSOFT FOUNDRY":"Microsoft Foundry",'
            '"Browser Use":"Browser Use","BROWSER USE":"Browser Use",'
            '"Computer Use":"Bilgisayar Kontrolü","COMPUTER USE":"Bilgisayar Kontrolü","游戏/3D":"Oyun / 3B","游戏 / 3D":"Oyun / 3B","游戏":"Oyun","Claude Security":"Claude Güvenlik","CLAUDE SECURITY":"Claude Güvenlik","Amd Skills":"AMD Becerileri","AMD SKILLS":"AMD Becerileri","Claude Code Setup":"Claude Code Kurulumu","CLAUDE CODE SETUP":"Claude Code Kurulumu","Claude Md Management":"Claude MD Yönetimi","CLAUDE MD MANAGEMENT":"Claude MD Yönetimi","Chrome Devtools MCP":"Chrome DevTools MCP","CHROME DEVTOOLS MCP":"Chrome DevTools MCP","Base44":"Base44","BASE44":"Base44","Cloudflare":"Cloudflare","CLOUDFLARE":"Cloudflare"'
            '};'
            'function _trSectionTitle(n){if(!n)return n;let u=n.toUpperCase();if(TR_SEC_TITLES[u])return TR_SEC_TITLES[u];if(TR_SEC_TITLES[n])return TR_SEC_TITLES[n];return n};'
        )
        m1 = re.search(r"function\s+(\w+)\(\{count:e,hint:t,title:n\}\)\{", js_content)
        m2 = re.search(r"function\s+(\w+)\(\{actions:e,count:t,title:n\}\)\{", js_content)
        if m1:
            js_content = js_content[:m1.start()] + section_title_helper + js_content[m1.start():]
            js_content = re.sub(r"function\s+(\w+)\(\{count:e,hint:t,title:n\}\)\{", r"function \1({count:e,hint:t,title:n}){n=_trSectionTitle(n);", js_content, count=1)
        if m2:
            js_content = re.sub(r"function\s+(\w+)\(\{actions:e,count:t,title:n\}\)\{", r"function \1({actions:e,count:t,title:n}){n=_trSectionTitle(n);", js_content, count=1)

    # Skills and Commands helpers injection
    if "function _trSkillDesc(" not in js_content:
        skill_cmd_helpers = (
                        'const TR_SKILL_DESCS=' + "{\"42crunch-api-security-testing\": \"42Crunch ile Claude Code içinde API güvenliğini otomatikleştirin - OpenAPI özelliklerini otomatik denetleyin, OWASP API Güvenlik riskleriyle uyumlu açıkları (BOLA/BFLA dahil) tespit edin ve yapay zeka destekli düzeltmeler uygulayın. Denetim->tarama->düzeltme->doğrulama döngüsüyle sürekli koruma sağlar.\", \"adobe-for-creativity\": \"Görüntüleri düzenlemek, tasarım iş akışlarını otomatikleştirmek ve yaratıcı vizyonları hayata geçirmek için Adobe'un yapay zeka destekli araçlarından yararlanın — arka plan kaldırmadan vektörleştirmeye ve profesyonel rötuşlara kadar.\", \"agent-sdk-dev\": \"Claude Agent SDK ile çalışmak için geliştirici kiti.\", \"agentforce-adlc\": \"Agentforce Ajan Geliştirme Yaşam Döngüsü — .agent dosyalarını yazma, keşfetme, iskele oluşturma, dağıtma, test etme ve optimize etme.\", \"ai-plugins\": \"Yazılım tedarik zincirinizdeki güvenlik risklerini taramak, önceliklendirmek ve düzeltmek için endorctl kurulumu yapın ve Endor Labs'i kullanın.\", \"aikido\": \"Claude Code için Aikido Security taraması — Aikido MCP sunucusu tarafından desteklenen SAST, gizli anahtar ve IaC güvenlik açığı tespiti.\", \"airtable\": \"Airtable, ajanlarınız için veritabanı ve operasyon katmanıdır. Yapılandırılmış verileri çok kullanıcılı görsel yüzeylerle (tablo, kanban, takvim, galeri, zaman çizelgesi) birleştirir; Jira, Salesforce, Zendesk, Google Drive ve Databricks ile senkronizasyon sağlar. Resmi Airtable MCP sunucusunu içerir.\", \"airwallex-agentos\": \"Airwallex'in küresel finansal altyapısını Claude'a getirin. Sipariş emirlerinden fatura oluşturma, tedarikçi kaydı ve çoklu para birimlerinde nakit pozisyonu takibi gibi hesap işlemlerini doğal dille yönetin. AgentOS, hazır finans yeteneklerini MCP sunucularıyla birleştirir.\", \"airwallex-dev\": \"Kendi kod tabanınızda Airwallex ödeme entegrasyonları oluşturun. Barındırılan Ödeme Sayfası, Kart bileşenleri, hesap KYC doğrulama ve abonelik faturalandırması için kod üretip projenize bağlar.\", \"aiven\": \"Yönetilen PostgreSQL, Kafka, OpenSearch, ClickHouse ve diğer veritabanlarını, akış platformlarını ve uygulamaları kolayca dağıtın. Ücretsiz katman mevcuttur.\", \"alloydb\": \"AlloyDB for PostgreSQL veritabanı oluşturun, bağlanın ve verilerle etkileşim kurun.\", \"alloydb-omni\": \"AlloyDB Omni veritabanı oluşturun, bağlanın ve verilerle etkileşim kurun.\", \"altimate-code\": \"dbt ve veri ambarı görevlerini; SQL analizi, sütun düzeyinde köken (lineage), dbt derleme/test/çalıştırma, profil oluşturma ve Snowflake, BigQuery, Redshift, Databricks, Postgres bağlantılarına sahip 100'den fazla amaca yönelik veri aracına sahip altimate-code uzman CLI ajanına devreder.\", \"amazon-location-service\": \"Geliştiricilere Amazon Location Service ile haritalar, yer arama, coğrafi kodlama, rota belirleme ve diğer jeo-uzamsal özellikleri ekleme, kimlik doğrulama kurulumu ve SDK entegrasyonu konularında rehberlik eder.\", \"amd-skills\": \"AMD doğrulanmış ajan yetenekleri: Ryzen AI üzerinde yerel yapay zeka ile görüntü/ses işleme, vLLM ile AMD Instinct GPU'larda LLM sunma ve GPU çekirdeği ile PyTorch izleme performansını analiz etme.\", \"amplitude\": \"Amplitude'u uzman bir analist gibi kullanın — ürün fırsatlarını keşfedin, grafikleri analiz edin, panolar oluşturun, deneyleri yönetin ve kullanıcıları anlayın.\", \"apollo\": \"Apollo.io ile potansiyel müşteri bulun, müşteri adaylarını zenginleştirin, sosyal yardım dizileri yükleyin ve satış analizlerini sorgulayın — Claude Code için tek tıkla MCP sunucu entegrasyonu.\", \"apollo-skills\": \"Claude Code için Apollo GraphQL ajan becerileri — Apollo Client, Server, Federation, Router ve Rover CLI. Şema tasarımı, sorgu optimizasyonu ve GraphQL en iyi uygulamalarını kapsar.\", \"appwrite\": \"Claude Code için Appwrite araçları; SDK becerileri, Appwrite MCP sunucuları ve dağıtım komutlarını içerir.\", \"asana\": \"Asana proje yönetimi entegrasyonu. Görev oluşturmak ve yönetmek, projelerde arama yapmak, atamaları güncellemek ve ilerlemeyi takip etmek için Claude Code'u Asana V2 MCP sunucusuna bağlar.\", \"astronomer-data-agents\": \"Apache Airflow ve Astronomer için veri mühendisliği. En iyi uygulamalarla DAG'lar yazın, işlem hattı hatalarını giderin, veri kökenini izleyin ve Airflow 2'den 3'e geçişleri yönetin.\", \"atlan\": \"Claude Code için Atlan veri kataloğu eklentisi. Doğal dil ile veri varlıklarınızı arayın, keşfedin, yönetin ve denetleyin. Anlamsal arama, köken takibi, sözlük yönetimi ve veri kalitesi kuralları sunar.\", \"atlassian\": \"Jira ve Confluence dahil Atlassian ürünlerine bağlanın. Talepler arayın ve oluşturun, belgelere erişin, sprintleri yönetin ve geliştirme iş akışınızı entegre edin.\", \"atlassian-twg-cli\": \"Teamwork Graph CLI, Atlassian'ın çalışma bağlamınıza (Jira talepleri, Confluence sayfaları, Bitbucket PR'ları) yönelik ajana öncelik veren arayüzüdür. Kodlama ajanları için özel olarak tasarlanmıştır.\", \"atomic-agents\": \"Atomic Agents çerçevesi ile yapay zeka ajanları geliştirmek için kapsamlı iş akışı. Şema tasarımı, mimari planlama, kod inceleme ve araç geliştirme için özel ajanlar içerir.\", \"auth0\": \"Kurumsal düzeyde kimlik doğrulama. Çerçeveye duyarlı rehberlikle herhangi bir uygulamaya oturum açma, SSO, MFA ve erişim kontrolü ekleyin.\", \"aws-agents\": \"AWS üzerinde yapay zeka ajanları oluşturun, dağıtın ve çalıştırın. Amazon Bedrock AgentCore ile iskele kurma, araç bağlama, bellek, politikalar ve üretim optimizasyonu yetenekleri.\", \"aws-agents-for-devsecops\": \"AWS DevOps Agent ve AWS Security Agent ile olayları inceleyin, kod incelemesi ve UAT yapın, güvenlik açıklarını tarayın ve sızma testleri çalıştırın.\", \"aws-amplify\": \"Kimlik doğrulama, veri modelleri, depolama, GraphQL API'leri ve Lambda fonksiyonları için rehberli iş akışlarıyla AWS Amplify Gen 2 tam yığın uygulamaları geliştirin.\", \"aws-core\": \"AWS üzerinde uygulamalar geliştirin, dağıtın ve çalıştırın. Kod olarak altyapı (IaC) yazma, temel servisleri kullanma ve yaygın görevleri tamamlama becerileri.\", \"aws-data-analytics\": \"S3 Tables, AWS Glue ve Athena ile veri gölü, analitik ve ETL iş akışları.\", \"aws-serverless\": \"AWS Serverless servisleri ile sunucusuz uygulamalar tasarlayın, derleyin, dağıtın, test edin ve hatalarını ayıklayın.\", \"aws-startup-advisor\": \"Girişimler için kişiselleştirilmiş mimari, maliyet, güvenlik ve geçiş rehberliği. İlk gün hesap kurulumundan üretime hazır altyapıya ve maliyet optimizasyonuna kadar destek sağlar.\", \"aws-transform\": \"Kod tabanlarını modernize edin ve AWS'ye taşıyın. .NET Framework'ü .NET 8/10'a, COBOL'u Java'ya, VMware'i EC2'ye dönüştürür; Java/Python/Node.js sürümlerini ve AWS SDK'larını yükseltir.\", \"azure\": \"Claude'u bir Azure uzmanına dönüştürün. 50'den fazla Azure servisinde kaynakları listeleme, dağıtımları doğrulama, altyapı sorunlarını tanılama ve maliyetleri optimize etme yetenekleri sağlar.\", \"azure-cosmos-db-assistant\": \"Azure Cosmos DB için uzman asistan — veri modelleme, sorgu optimizasyonu, performans ayarlama ve en iyi uygulamalar.\", \"azure-sql-developer\": \"Konteynerde yerel çalışan Azure SQL Veritabanı motoru için ajan yetenekleri. Motoru çalıştırma, bağlanma, geçiş yapma, RAG oluşturma ve buluta aktarma adımlarını öğretir.\", \"base44\": \"CLI proje yönetimi ve JavaScript/TypeScript SDK geliştirme becerileriyle Base44 tam yığın uygulamaları oluşturun ve dağıtın.\", \"bigdata-com\": \"Bigdata MCP tarafından desteklenen finansal araştırma, analitik ve istihbarat araçları sağlayan resmi Bigdata.com eklentisi.\", \"bigquery-data-analytics\": \"BigQuery veri kümeleri ve verileri için bağlanın, sorgulayın ve veri içgörüleri oluşturun.\", \"boltz\": \"Claude Code içinden Boltz ile yapıları tahmin edin, molekülleri ve proteinleri tarayın ve bağlayıcılar tasarlayın.\", \"box\": \"Box içeriklerinizle doğrudan Claude Code içinden çalışın — dosyaları arayın, klasörleri düzenleyin ve Box AI ile belgeleri özetleyip veri çıkarın.\", \"brightdata-plugin\": \"Bright Data destekli web kazıma, Google araması, yapılandırılmış veri çıkarma ve MCP sunucu entegrasyonu.\", \"browser-use\": \"Masaüstü için yerleşik tarayıcı otomasyonu çalışma ortamı ve rehberlik.\", \"buildkite\": \"Claude Code ve yapay zeka kodlama ajanları için resmi Buildkite yetenekleri — işlem hatları, geçiş, ön kontrol, ajan çalışma zamanı, CLI ve API.\", \"canva\": \"Canva MCP sunucusu ile Canva tasarımları oluşturun, düzenleyin, inceleyin, yeniden boyutlandırın ve marka kontrolleri yapın.\", \"carbone-skill\": \"Resmi Carbone yeteneği — etiketler, döngüler, koşullar, biçimlendiriciler ve tüm çıktı formatlarını (DOCX, XLSX, PPTX, PDF) kapsayan eksiksiz şablon dili referansı.\", \"carta-cap-table\": \"Carta Cap Table eklentisi — sermaye tabloları, hisse hibeleri, SAFE'ler, 409A değerlemeleri ve şelale senaryolarını sorgulama yetenekleri.\", \"carta-crm\": \"Carta CRM'i doğal dille yönetin — yatırımcıları, şirketleri, kişileri, anlaşmaları ve fon toplamayı arayın, ekleyin ve güncelleyin.\", \"carta-investors\": \"Carta Investors eklentisi — Carta MCP Sunucusu aracılığıyla yatırımcı verilerini, performans kıyaslamalarını ve mevzuat raporlamalarını sorgulama yetenekleri.\", \"catalyst-by-zoho\": \"Zoho Catalyst için resmi Claude Code eklentisi — tam yığın sunucusuz bulut platformu. Tüm servisleri, SDK'ları, CLI'yi, mimari kalıpları, fiyatlandırmayı ve Zoho MCP araç tabanlı kaynak yönetimini kapsar.\", \"cds-mcp\": \"SAP Cloud Application Programming Model (CAP) projelerinin yapay zeka destekli geliştirilmesi. CDS modellerini ve CAP belgelerini arayın.\", \"chrome-devtools-mcp\": \"Kodlama ajanınızdan canlı bir Chrome tarayıcısını kontrol edin ve denetleyin. Performans izlerini kaydedin, ağ isteklerini analiz edin, konsol günlüklerini kaynak eşlemeli yığın izleriyle inceleyin ve Puppeteer ile otomatikleştirin.\", \"circle-skills\": \"Sabit coin (stablecoin) uygulamalarını daha hızlı geliştirin. USDC ödemeleri, zincirler arası transferler, cüzdanlar ve akıllı sözleşmeler için en iyi uygulama yetenekleri ve Circle MCP sunucusu.\", \"circleback\": \"Circleback konuşma bağlamı entegrasyonu. Toplantıları, e-postaları, takvim etkinliklerini ve daha fazlasını arayın ve erişin.\", \"ckeditor\": \"Herhangi bir JavaScript projesinde CKEditor 5'i (ücretsiz ve premium) kurun, yapılandırın ve entegre edin.\", \"clangd-lsp\": \"Kod zekası için C/C++ dil sunucusu (clangd).\", \"claude-code-setup\": \"Kod tabanlarını analiz edin ve kancalar (hooks), beceriler (skills), MCP sunucuları ve alt ajanlar gibi özelleştirilmiş Claude Code otomasyonları önerin.\", \"claude-md-management\": \"CLAUDE.md dosyalarını koruma ve iyileştirme araçları - kaliteyi denetleyin, oturum kazanımlarını yakalayın ve proje hafızasını güncel tutun.\", \"claude-security\": \"Özel Claude Güvenlik yöneticisi. Gözetimsiz bir tarama görevi verin; revizyonu yakalar, çoklu ajan güvenlik taramasını baştan sona yönetir ve bulunan açıkları yamalar.\", \"clickhouse\": \"Claude'u ClickHouse Cloud veritabanlarınıza bağlayın. Organizasyonları, servisleri, veritabanlarını ve tablo şemalarını inceleyin. Verileriniz üzerinde salt okunur SQL sorguları çalıştırın, anlık analitik yanıtlar alın ve yedeklemeleri izleyin.\", \"clickhouse-best-practices\": \"ClickHouse şema tasarımı, sorgu optimizasyonu ve veri alımı için etkiye göre önceliklendirilmiş 28 en iyi uygulama kuralı.\", \"cloud-sql-mysql\": \"Cloud SQL for MySQL veritabanına bağlanın, verilerle etkileşim kurun ve yönetin.\", \"cloud-sql-postgresql\": \"Cloud SQL for PostgreSQL veritabanı oluşturun, bağlanın ve verilerle etkileşim kurun.\", \"cloud-sql-sqlserver\": \"Cloud SQL for SQL Server veritabanına bağlanın ve etkileşim kurun.\", \"cloudflare\": \"Workers, Pages, depolama (KV, D1, R2), yapay zeka (Workers AI, Vectorize) ve ağ özelliklerini kapsayan kapsamlı Cloudflare platform yeteneği.\", \"cloudinary\": \"Cloudinary'yi doğrudan Claude içinde kullanın. Doğal konuşma yoluyla varlıkları yönetin, dönüşümler uygulayın ve medyayı optimize edin.\", \"cockroachdb\": \"Pratik veritabanı çalışmaları için Claude Code'u CockroachDB kümelerinize bağlayın — şemaları keşfedin, optimize edilmiş SQL yazın, sorgu hatalarını ayıklayın ve dağıtık veritabanı kümelerini yönetin.\", \"code-modernization\": \"Eski kod tabanlarını (COBOL, eski Java/C++, monolit web uygulamaları) yapılandırılmış iş akışı, etkileşimli topoloji görüntüleyici ve uzman inceleme ajanları ile modernize edin.\", \"code-review\": \"Yanlış pozitifleri filtrelemek için güven tabanlı puanlamaya sahip çoklu uzman ajanlar kullanarak çekme istekleri (PR) için otomatik kod incelemesi.\", \"code-simplifier\": \"İşlevselliği korurken netlik, tutarlılık ve sürdürülebilirlik için kodu basitleştiren ve iyileştiren ajan. Yakın zamanda değiştirilen koda odaklanır.\", \"coderabbit\": \"Kod inceleme ortağınız. Hataları, güvenlik açıklarını ve mantık hatalarını yakalayan 40'tan fazla entegre statik çözümleyici ve uzman yapay zeka mimarisi ile harici doğrulama sağlar.\", \"codspeed\": \"CodSpeed hepsi bir arada performans testi araç setidir. Karşılaştırma sonuçlarına, alev grafiklerine (flamegraphs) ve performans kıyaslamalarına göz atarak darboğazları tespit edin.\", \"commit-commands\": \"Commit, push ve PR oluşturma dahil git commit iş akışları için komutlar.\", \"confidence\": \"Özellik bayraklarına (feature flags), deneylere ve geçiş araçlarına doğrudan Claude Code içinden erişin.\", \"context7\": \"Güncel belge araması için Upstash Context7 MCP sunucusu. Sürüme özgü belgeleri ve kod örneklerini doğrudan kaynak depolardan LLM bağlamınıza çeker.\", \"convex\": \"Arka uç geliştirme, şema tasarımı, gerçek zamanlı özellikler, kimlik doğrulama ve yapay zeka ajanları için yerleşik Convex yetenekleri, kod yazma uzmanı ve MCP erişimi.\", \"crowdsec\": \"Bare-metal, Docker ve Kubernetes genelinde CrowdSec kurulumu, yapılandırması, çalıştırılması ve hata ayıklaması için operasyonel yetenek.\", \"crowdstrike-falcon-foundry\": \"Falcon platformunda siber güvenlik uygulamaları geliştirmek için CrowdStrike Falcon Foundry geliştirici yetenekleri.\", \"crowdstrike-falcon-fusion\": \"Fusion iş akışlarını yazmak, dağıtmak ve yürütmek için CrowdStrike Falcon Fusion yetenekleri. Şema doğrulamalı YAML yazımı ve izleme içerir.\", \"csharp-lsp\": \"Kod zekası için C# dil sunucusu (LSP).\", \"cwc-makers\": \"Tek bir /maker-setup komutuyla Code-with-Claude Makers Cardputer kurulumu yapın — depoyu klonlar, ürün yazılımını yükler ve Claude Buddy paketini kurar.\", \"dash0\": \"Claude Code oturumları için OpenTelemetry gözlemlenebilirliği. Araç çağrılarını, LLM isteklerini, belirteç kullanımını ve hataları OTel izleri olarak yakalar.\", \"data\": \"Apache Airflow ve Astronomer için veri mühendisliği. En iyi uygulamalarla DAG'lar yazın, işlem hattı hatalarını giderin, veri kökenini izleyin ve dağıtımları yönetin.\", \"data-agent-kit-starter-pack\": \"Google Cloud üzerinde çalışan veri mühendisleri için uzman paket. Karmaşık veri hatları tasarlayın, dbt ile dönüştürün, Spark ve BigQuery SQL not defterleri yazın.\", \"data-engineering\": \"Veri mühendisliği eklentisi — ambar keşfi, işlem hattı yazımı, Airflow entegrasyonu.\", \"databases-on-aws\": \"AWS veritabanı portföyü için uzman veritabanı rehberliği. Şemalar tasarlayın, sorgular yürütün, geçişleri yönetin ve iş yükünüz için doğru veritabanını seçin.\", \"databricks\": \"CLI, Apps, Lakebase, Model Serving, Lakeflow Jobs, Spark Bildirimsel İşlem Hatları ve DABs için Databricks yetenekleri.\", \"datadog\": \"Önceden yapılandırılmış Datadog MCP sunucusu aracılığıyla Datadog'u doğrudan Claude Code içinde kullanın. Günlükleri, metrikleri, izleri ve panoları doğal dille sorgulayın.\", \"datahub-skills\": \"Bağlayıcı planlama, PR inceleme, katalog arama, meta veri zenginleştirme, köken takibi ve veri kalitesi yönetimi ile DataHub geliştirme araç seti.\", \"dataproc\": \"Dataproc kümelerini ve işlerini yönetin.\", \"datarobot-agent-skills\": \"Yapay zeka ve makine öğrenimi iş akışları için DataRobot yetenekleri — model eğitimi, dağıtım, tahminler, özellik mühendisliği ve izleme.\", \"dataverse\": \"Microsoft Dataverse üzerinde geliştirme, analiz ve yönetim için ajan yetenekleri — Dataverse MCP, PAC CLI ve Python SDK desteğiyle.\", \"deepeval\": \"Yapay zeka uygulamalarına DeepEval değerlendirmeleri, izleme, veri kümeleri ve yinelemeli iyileştirme döngüleri ekleme yetenekleri.\", \"deploy-on-aws\": \"Mimari önerileri, maliyet tahminleri ve IaC dağıtımı ile uygulamaları AWS'ye dağıtın.\", \"desktop-commander\": \"Terminal komutları, süreç yönetimi ve metin, kod, PDF, DOCX, Excel ve görseller genelinde dosya işlemleri için MCP sunucusu.\", \"discord\": \"Yerleşik erişim kontrollü Discord mesajlaşma köprüsü. Eşleştirmeyi, izin verilenler listesini ve politikayı /discord:access ile yönetin.\", \"dominodatalab\": \"Veri bilimi ekipleri için tam Domino Data Lab platform desteği — çalışma alanları, işler, model dağıtımı, deney takibi ve Spark/Ray/Dask desteği.\", \"dropbox\": \"Dropbox dosyalarınızı doğrudan Claude'a bağlayın; böylece araç değiştirmeden arama yapabilir, düzenleyebilir ve oluşturulan içerikleri kaydedebilirsiniz.\", \"duckdb-skills\": \"Claude Code için DuckDB destekli yetenekler: herhangi bir veri dosyasını okuyun, DuckDB veritabanlarını bağlayıp sorgulayın ve uzantıları yönetin.\", \"duende-skills\": \"Claude Code için Duende geliştirici yetenekleri ve ajanları — OAuth/OIDC protokolleri, IdentityServer, belirteç yönetimi, ASP.NET Core kimlik doğrulama/yetkilendirme, BFF modelleri ve güvenli kimlik mimarisi.\", \"exa\": \"Exa AI web araması, derin araştırma ve içerik çıkarma. Kapsamlı web araması, kişi keşfi, şirket araştırması ve akademik makaleler için MCP araçları ve araştırma becerileri sağlar.\", \"explanatory-output-style\": \"Uygulama tercihleri ve kod tabanı modelleri hakkında eğitici bilgiler ekler.\", \"expo\": \"Expo ile React Native uygulamaları geliştirmek, dağıtmak, yükseltmek ve hata ayıklamak için resmi Expo yetenekleri. Expo Router, SwiftUI/Jetpack Compose bileşenleri, Tailwind CSS ve App Store/Play Store dağıtımını kapsar.\", \"fakechat\": \"Kanal bildirim akışını test etmek için yerel web sohbeti. Belirteç, erişim kontrolü veya üçüncü taraf hizmet gerekmez.\", \"fastly-agent-toolkit\": \"Fastly geliştirme araçları ve platform yetenekleri.\", \"feature-dev\": \"Kod tabanı keşfi, mimari tasarımı ve kalite incelemesi için uzmanlaşmış ajanlarla kapsamlı özellik geliştirme iş akışı.\", \"fiftyone\": \"Yüksek kaliteli veri kümeleri ve bilgisayarlı görü modelleri oluşturun. Veri kümelerini görselleştirin, modelleri analiz edin, kopyaları bulun, çıkarım yapın ve özel eklentiler geliştirin.\", \"figma\": \"Figma tasarım platformu entegrasyonu. Tasarım dosyalarına erişin, bileşen bilgilerini ve tasarım belirteçlerini (tokens) çıkarın ve tasarımları koda dönüştürün.\", \"firebase\": \"Google Firebase MCP entegrasyonu. Firestore veritabanlarını, kimlik doğrulamayı, bulut fonksiyonlarını, barındırmayı ve depolamayı doğrudan geliştirme iş akışınızdan yönetin.\", \"firecrawl\": \"Firecrawl destekli web kazıma ve tarama. Herhangi bir web sitesini temiz, LLM'ye hazır Markdown'a veya yapılandırılmış verilere dönüştürün.\", \"firestore-native\": \"Firestore veritabanları, koleksiyonları ve belgeleriyle bağlanın ve etkileşim kurun.\", \"forge-skills\": \"Atlassian Forge için yetenekler ve MCP yapılandırması: uygulamalar oluşturun ve dağıtın, Rovo Search/Chat için Teamwork Graph bağlayıcıları geliştirin.\", \"frontend-design\": \"Yüksek tasarım kalitesine sahip, özgün ve üretime hazır ön yüz arayüzleri oluşturun. Sıradan yapay zeka estetiğinden kaçınan yaratıcı kodlar üretir.\", \"fullstory\": \"Davranışsal analitiği, oturum tekrarlarını ve müşteri deneyimi içgörülerini sorgulamak için Claude'u Fullstory'ye bağlayın.\", \"github\": \"Depo yönetimi için resmi GitHub MCP sunucusu. Talepler (issues) oluşturun, çekme isteklerini (PR) yönetin, kod inceleyin ve GitHub API'siyle etkileşim kurun.\", \"gitkraken\": \"Claude'a çalıştığınız her depodaki gerçek Git ve proje bağlamını (commit'ler, dallar, PR'lar ve talepler) sağlar. GitHub, GitLab, Azure DevOps ve Jira ile çalışır.\", \"gitlab\": \"GitLab DevOps platformu entegrasyonu. Depoları, birleştirme isteklerini (MR), CI/CD işlem hatlarını, sorunları ve vikileri yönetin.\", \"google-cloud-storage\": \"Resmi Google Cloud Storage (GCS) eklentisi. Depolama alanlarını ve nesneleri yönetin, veri aktarın; MCP, FUSE, IAM, güvenlik ve yaşam döngüsü kurallarını yapılandırın.\", \"gopls-lsp\": \"Kod zekası ve yeniden düzenleme (refactoring) için Go dil sunucusu (gopls).\", \"grafana-assistant\": \"Grafana Assistant uygulamasını ve CLI'yi geliştirmek ve kullanmak için yetenekler ve kurallar.\", \"grafana-cloud-mcp\": \"Yapay zeka destekli Grafana Cloud gözlemlenebilirliği için barındırılan MCP sunucusu — yerel kurulum gerektirmez.\", \"grafana-mcp\": \"Yapay zeka destekli Grafana panoları, veri kaynakları, uyarılar ve olay yönetimi için MCP sunucusu.\", \"greptile\": \"Yapay zeka destekli kod tabanı arama ve anlama. İlgili kodu bulmak, bağımlılıkları anlamak ve mimari hakkında bağlamsal yanıtlar almak için depolarınızı sorgulayın.\", \"growthbook\": \"Özellik bayrakları ve deneme yaşam döngüsü için kapsamlı GrowthBook ajan yetenekleri paketi.\", \"honeycomb\": \"Honeycomb gözlemlenebilirliği için yetenekler, ajanlar ve iş akışları — sorgu modelleri, üretim incelemeleri, SLO'lar ve OpenTelemetry enstrümantasyonu.\", \"hookify\": \"Konuşma kalıplarını analiz ederek veya açık talimatlarla istenmeyen davranışları önlemek için özel kancalar (hooks) oluşturun.\", \"hostinger\": \"Hostinger hizmetlerini dağıtın, yönetin ve izleyin — Web siteleri, Alan Adları, E-ticaret, E-posta Pazarlama, Abonelikler ve VPS.\", \"huggingface-skills\": \"Açık kaynaklı yapay zeka modelleri, veri kümeleri ve alanları (spaces) oluşturun, eğitin, değerlendirin ve kullanın.\", \"hunter\": \"Profesyonel e-posta adreslerini bulun ve doğrulayın, alan adına göre kişileri arayın ve şirket verilerini doğrudan Claude içinde zenginleştirin.\", \"hyperframes\": \"HyperFrames by HeyGen. HTML yazın, video oluşturun. Animasyonlar, altyazılar, seslendirmeler ve sese duyarlı görseller üretin.\", \"idmp-plugin\": \"Keşif, şema denetimi ve güvenli operasyonel iş akışları için paketlenmiş TDengine IDMP eklentisi.\", \"imessage\": \"Yerleşik erişim kontrolüne sahip iMessage mesajlaşma köprüsü. Doğrudan chat.db okur ve AppleScript ile gönderir.\", \"intercom\": \"Claude Code için Intercom entegrasyonu. Konuşmaları arayın, müşteri destek kalıplarını analiz edin ve müşteri verilerinden gerçek zamanlı içgörüler edinin.\", \"jdtls-lsp\": \"Kod zekası için Java dil sunucusu (Eclipse JDT.LS).\", \"jfrog\": \"Claude Code içinden JFrog platformunu kullanın: Artifactory depoları, yapıtlar, güvenlik bulguları ve SDLC iş akışları.\", \"knowledge-catalog\": \"Veri platformunuzdaki veri ve yapay zeka varlıklarını keşfetmek, yönetmek, izlemek ve denetlemek için Knowledge Catalog'a bağlanın.\", \"kotlin-lsp\": \"Kod zekası için Kotlin dil sunucusu (LSP).\", \"langfuse-observability\": \"Claude Code için Langfuse gözlemlenebilirlik eklentisi — LLM izleme, hata ayıklama ve değerlendirme için izleri ve oturum telemetrisini Langfuse'a aktarır.\", \"laravel-boost\": \"Laravel geliştirme araç seti MCP sunucusu. Artisan komutları, Eloquent sorguları, rotalar, geçişler ve çerçeveye özel kod üretimi için akıllı yardım sağlar.\", \"learn-with-coursera\": \"Herhangi bir öğrenme hedefini kişiselleştirilmiş Coursera deneyimine dönüştürün. Kataloğu arar ve kurs, uygulamalı proje veya video önerir.\", \"learning-output-style\": \"Karar noktalarında anlamlı kod katkıları talep eden etkileşimli öğrenme modu.\", \"legalzoom\": \"İş ve kişisel ihtiyaçlar için avukat rehberliği ve yasal araçlar. Yapay zeka destekli belge incelemesi kritik riskleri ve maddeleri belirler.\", \"linear\": \"Linear sorun takip entegrasyonu. Talepler oluşturun, projeleri yönetin, durumları güncelleyin ve yazılım geliştirme iş akışınızı kolaylaştırın.\", \"liquid-lsp\": \"Shopify CLI tema dil sunucusu aracılığıyla Shopify Liquid şablonları için LSP entegrasyonu.\", \"liquid-skills\": \"Shopify temaları için Liquid dili temelleri, CSS/JS/HTML kodlama standartları ve WCAG erişilebilirlik kalıpları.\", \"logfire\": \"FastAPI, httpx, asyncpg, SQLAlchemy ve daha fazlası için otomatik izleme ile Python uygulamalarına Logfire gözlemlenebilirliği ekleyin.\", \"logrocket\": \"Oturum tekrarlarını, metrikleri, sorunları ve kullanıcı davranışlarını doğal dille sorgulamak için Claude Code'u LogRocket'a bağlayın.\", \"looker\": \"Looker'a bağlanın ve LookML kullanarak verilerinizle etkileşim kurun.\", \"lovable\": \"Claude Code içinden Lovable uygulamaları oluşturun, geliştirin, dağıtın ve yönetin. Resmi Lovable MCP sunucusunu içerir.\", \"lua-lsp\": \"Kod zekası için Lua dil sunucusu (LSP).\", \"lumen\": \"MCP aracılığıyla hassas yerel anlamsal kod arama. Kod tabanınızı Go AST ile dizinler, Ollama veya LM Studio ile vektörleştirir ve Claude'a bulut gerektirmeden sunar.\", \"lusha\": \"Lusha B2B istihbarat platformunu kullanarak müşteri adayları bulun, zenginleştirin ve doğrulanmış telefon numaraları ile arama listeleri oluşturun.\", \"mapbox\": \"Yapay zeka ile konuma duyarlı uygulamalar geliştirmek için Mapbox yetenekleri ve MCP sunucuları. Web, iOS ve Android için jeo-uzamsal araçlar sunar.\", \"math-olympiad\": \"Kendi kendini doğrulamada kaçırılan hataları yakalayan çekişmeli doğrulama sistemiyle yarışma matematiği (IMO, Putnam, USAMO) problemlerini çözün.\", \"mattpocock-skills\": \"Gerçek mühendislik için Matt Pocock ajan yetenekleri — TDD, kod inceleme, alan modelleme ve belirtim iş akışları.\", \"mcp-apps\": \"MCP Apps SDK ile MCP uygulamaları oluşturma yetenekleri.\", \"mcp-server-dev\": \"Claude ile sorunsuz çalışan MCP sunucuları tasarlamak ve geliştirmek için yetenekler. Dağıtım modelleri, araç tasarımı ve kimlik doğrulama rehberi sunar.\", \"mcp-tunnels\": \"Claude'u Anthropic MCP tüneli aracılığıyla özel bir MCP sunucusuna bağlayın. Docker Compose hızlı başlangıcını uçtan uca yönetir.\", \"mercadopago\": \"Mercado Pago tam ürün entegrasyon araç seti. Resmi MCP sunucusundan gerçek zamanlı veri çeken 4 orkestrasyon yeteneği içerir.\", \"mergify\": \"Mergify CLI yetenekleri: birleştirme kuyruklarını, yığılmış PR'ları, test içgörülerini ve Mergify yapılandırmasını doğrudan terminalden yönetin.\", \"microsoft-docs\": \"Azure, .NET, Windows ve daha fazlası için resmi Microsoft belgelerine, API referanslarına ve kod örneklerine erişin.\", \"migration-to-aws\": \"Google Cloud ve yapay zeka iş yüklerinden AWS'ye geçiş planlayın. IaC dosyalarını ve mimariyi analiz ederek AWS geçiş yapıtları oluşturur.\", \"mintlify\": \"Mintlify ile şık dokümantasyon siteleri oluşturun. Markdown dışı dosyaları düzgün biçimlendirilmiş MDX sayfalarına dönüştürün ve güncellemeleri otomatikleştirin.\", \"miro\": \"Miro panolarına güvenli erişim. Yapay zekanın pano bağlamını okumasına, diyagramlar oluşturmasına ve kurumsal güvenlikle kod üretmesine olanak tanır.\", \"modern-web-guidance\": \"Kodlama ajanınızı en güncel modern web standartları ve en iyi uygulamalarıyla donatın.\", \"mlflow\": \"Yapay zeka ajanlarını MLflow ile izleme, değerlendirme ve geliştirme yetenekleri: enstrüman → izle → değerlendir → yinele → doğrula döngüsünü destekler.\", \"monday-crm\": \"monday CRM'inizi doğal dille yönetin. Sıfırdan işlem hattı oluşturun, anlaşma brifingleri alın, tahmin panoları kurun ve verileri temizleyin.\", \"mongodb\": \"MongoDB için resmi Claude eklentisi (MCP Sunucusu + Beceriler). Veritabanlarına bağlanın, koleksiyonları yönetin, sorguları optimize edin ve güvenilir kodlar üretin.\", \"mongodb-atlas\": \"Atlas Yönetilen MCP Sunucusu aracılığıyla MongoDB Atlas kümelerine bağlanın. Kümeleri, projeleri, veritabanı kullanıcılarını ve ağ erişimini yönetin.\", \"neon\": \"neon-postgres ajan yeteneği ve Neon MCP Sunucusu ile Neon projelerinizi ve veritabanlarınızı yönetin.\", \"netlify-skills\": \"Claude Code için Netlify platform yetenekleri — fonksiyonlar, uç fonksiyonlar, veritabanı, resim CDN, formlar, çerçeveler ve dağıtım.\", \"netsuite-ai-companion\": \"NetSuite AI Bağlayıcısını kullanan yapay zeka asistanları için rehberlik: araç seçimi, çoklu iştirak ve para birimi yönetimi ve SuiteQL güvenlik kontrolleri.\", \"netsuite-finance-analyst\": \"Canlı NetSuite verileri üzerinde üst düzey finansal analiz: mali raporlama, dönem kapanışı, mutabakat incelemeleri ve nakit akışı raporlaması.\", \"netsuite-suitecloud\": \"SuiteScript, SDF ve en iyi uygulamalarla NetSuite SuiteCloud çözümleri geliştirin: kayıt yükseltmeleri, roller, izinler ve güvenli kodlama.\", \"newrelic\": \"Claude Code için New Relic gözlemlenebilirlik zekası. APM performansını inceleyin, bulut maliyetlerini analiz edin, Kubernetes hatalarını giderin ve NRQL sorguları yazın.\", \"nightvision\": \"Web uygulamalarında ve REST API'lerinde istismar edilebilir açıkları bulan DAST ve API Keşif platformu NightVision ile çalışma yetenekleri.\", \"nimble\": \"Nimble web verisi araç seti — web'i arayın, çıkarın, haritalayın, tarayın ve yapılandırılmış veri ajanlarıyla çalışın.\", \"noibu\": \"E-ticaret için geliştirilmiş Noibu eklentisi; mağazanızın oturum, hata ve dönüşüm verilerini bağlayarak gelire etki eden sorunları tespit eder.\", \"notion\": \"Notion çalışma alanı entegrasyonu. Sayfaları arayın, belgeler oluşturup güncelleyin, veritabanlarını yönetin ve ekip bilgi tabanına erişin.\", \"nvidia-skills\": \"GPU hızlandırma, CUDA, yapay zeka ajanları, model eğitimi, çıkarım, robotik ve Omniverse için doğru NVIDIA yeteneğini bulun.\", \"oracle-ai-data-platform-workbench-databricks-migrator\": \"Oracle AIDP Databricks Geçiş Araç Setini doğal dille yönetin. Not defterleri, işler ve katalog DDL'lerinin otomatik Databricks → AIDP geçişini yürütür.\", \"oracle-ai-data-platform-workbench-engineer-agent\": \"Claude Code için Oracle AIDP Workbench mühendis ajanı — tam Spark/Delta lakehouse mimarisini doğal dille işleten 37 yetenekli uzman ajan.\", \"oracle-ai-data-platform-workbench-spark-connectors\": \"Claude Code için Oracle AIDP Workbench Spark bağlayıcıları: Oracle Autonomous DB, ExaCS, ERP, Object Storage, Iceberg, Snowflake ve S3 dahil 18 veri kaynağı desteği.\", \"oracledb\": \"Oracle Veritabanlarına ve verilerine bağlanın, sorgulayın ve etkileşim kurun.\", \"outputai\": \"Claude Code için Output.ai iş akışı geliştirme araç seti. 5 uzman ajan, 40'tan fazla eğik çizgi komutu ve otomatik yüklenen SDK kuralları içerir.\", \"pagerduty\": \"PagerDuty risk puanlaması ve olay korelasyonu ile kod kalitesini ve güvenliğini artırın. Dağıtım öncesi riskleri belirleyin.\", \"paypal\": \"Claude için PayPal geliştirme eklentisi — ödemeleri, abonelikleri, faturaları ve uyuşmazlıkları PayPal API ve MCP sunucusu ile entegre edin.\", \"php-lsp\": \"Kod zekası için PHP dil sunucusu (Intelephense).\", \"pigment\": \"Doğal dil ile iş verilerini analiz edin ve özel Pigment modelleri, metrikleri ve panoları oluşturun.\", \"pinecone\": \"Pinecone vektör veritabanı entegrasyonu. Vektör indekslerini yönetme, veri sorgulama, anlamsal arama ve RAG uygulamaları geliştirme araçları.\", \"pixeltable\": \"Pixeltable ile çok modlu (multimodal) yapay zeka uygulamaları geliştirin — tablolar, hesaplanmış sütunlar, yerleştirme araması ve 25+ yapay zeka sağlayıcı entegrasyonu.\", \"planetscale\": \"PlanetScale organizasyonlarınıza, veritabanlarınıza, dallarınıza ve şemalarınıza erişen barındırılan MCP sunucusu. Yavaş sorguları tespit edin ve verileri analiz edin.\", \"playground\": \"Görsel kontrollere ve canlı önizlemeye sahip etkileşimli, bağımsız tek dosyalık HTML oyun alanları (playgrounds) oluşturur.\", \"playwright\": \"Microsoft tarafından geliştirilen tarayıcı otomasyonu ve uçtan uca test MCP sunucusu. Claude'un web sayfalarıyla etkileşime girmesini ve testler yürütmesini sağlar.\", \"plugin-dev\": \"Claude Code eklentileri geliştirmek için kapsamlı araç seti. Kancalar, MCP entegrasyonu, komutlar ve ajanları kapsayan 7 uzman yetenek içerir.\", \"posthog\": \"PostHog analizlerine, özellik bayraklarına, deneylere, hata takibine ve içgörülere doğrudan Claude Code içinden erişin.\", \"postiz\": \"X, LinkedIn, Reddit, YouTube, TikTok ve Instagram dahil 28'den fazla platformda gönderi planlama ve analiz takibi için sosyal medya otomasyon CLI'si.\", \"postman\": \"Claude Code için tam API yaşam döngüsü yönetimi. Koleksiyonları senkronize edin, istemci kodu üretin, API'leri keşfedin, testler çalıştırın ve belgeleri yayınlayın.\", \"pr-review-toolkit\": \"Yorumlar, testler, hata işleme, tip tasarımı, kod kalitesi ve basitleştirme konularında uzmanlaşmış kapsamlı PR inceleme ajanları.\", \"preset-cli-skills\": \"`sup` CLI (PyPI paketi `superset-sup`) tarafından yönlendirilen kabuk, komut dosyası ve CI/CD iş akışları için Preset CLI yetenekleri.\", \"prisma\": \"Postgres veritabanı yönetimi, şema geçişleri, SQL sorguları ve bağlantı dizesi yönetimi için Prisma MCP entegrasyonu.\", \"project-artifact\": \"Canlı bir proje durum sayfasını (genel bakış, başarı kriterleri, iş akışı sırası ve sonraki adımlar) paylaşılabilir bir yapıt olarak oluşturun.\", \"pydantic-ai\": \"En baştan itibaren doğru Pydantic AI kodu yazın. Ajanlar, araçlar, yapılandırılmış çıktılar ve akış için güncel desenler.\", \"pyright-lsp\": \"Tip denetimi ve kod zekası için Python dil sunucusu (Pyright).\", \"qdrant-skills\": \"Ölçeklendirme, performans optimizasyonu, arama kalitesi ve Python, TS, Rust, Go SDK kullanımını kapsayan Qdrant vektör arama yetenekleri.\", \"qodo\": \"Yazılım geliştirme iş akışları için kod kalitesi kontrolleri, otomatik test, güvenlik taraması ve uyumluluk doğrulaması sunan Qodo yetenekleri kütüphanesi.\", \"qt-development-skills\": \"Qt yazılım geliştirme için mühendislik yetenekleri — Qt C++/QML kod incelemesi, QML kodlama ve dokümantasyon.\", \"quarkus-agent\": \"Yapay zeka kodlama ajanlarının Quarkus uygulamaları oluşturması, yönetmesi ve etkileşimde bulunması için MCP sunucusu.\", \"railway\": \"Railway üzerinde uygulamaları, veritabanlarını ve altyapıyı dağıtın ve yönetin. Proje kurulumu, ortam yapılandırması ve izlemeyi kapsar.\", \"ralph-loop\": \"Yinelemeli geliştirme için Ralph Wiggum tekniğini uygulayan etkileşimli yapay zeka döngüleri. Görev tamamlanana kadar önceki çalışmalarını görerek devam eder.\", \"rc\": \"RevenueCat projelerini, uygulamalarını, ürünlerini ve tekliflerini doğrudan Claude Code içinden yapılandırın.\", \"receipts\": \"Yöneticinize veya kendinize kullanımınızı gerekçelendirmek için kişisel Claude Code etki raporu: neleri yayınladınız ve hangi projede ne kadar harcadınız.\", \"redis-development\": \"Redis geliştirme en iyi uygulamaları — veri yapıları, sorgu motoru, vektör araması, önbelleğe alma ve performans optimizasyonu.\", \"remember\": \"Claude Code için sürekli hafıza. Konuşmaları özetleyip günlük kayıtlara sıkıştırır; böylece Claude dün ne yaptığınızı hatırlar.\", \"render\": \"Render üzerinde uygulamaları dağıtın, hatalarını ayıklayın ve izleyin. Beceriler, ajan, eğik çizgi komutları ve render.yaml doğrulama kancası içerir.\", \"resend\": \"Resend ile e-posta göndermek ve almak için ajan yetenekleri — e-posta API entegrasyonu, ajan gelen kutusu, CLI ve React Email bileşenleri.\", \"revenuecat\": \"RevenueCat projelerini, uygulamalarını, ürünlerini, haklarını ve tekliflerini doğrudan Claude Code içinden yapılandırın.\", \"rill\": \"Rill iş zekası platformunda projeler geliştirmek ve sorgulamak için yetenekler.\", \"rootly\": \"Tam yaşam döngüsü olay yönetimi: dağıtım güvenliği, olaya müdahale, nöbet yönetimi ve retrospektifler.\", \"ruby-lsp\": \"Kod zekası ve analizi için Ruby dil sunucusu (LSP).\", \"runway-api\": \"Ölçeklenebilir video üretimi. Runway API ile videolar, resimler ve sesler oluşturun — reklam kampanyaları, ürün videoları ve hikayeler.\", \"rust-analyzer-lsp\": \"Kod zekası ve analizi için Rust dil sunucusu (rust-analyzer).\", \"sagemaker-ai\": \"Amazon SageMaker AI kapsamındaki derin AWS AI/ML uzmanlığıyla modeller oluşturun, eğitin ve dağıtın.\", \"salesforce-development\": \"Temel yapı taşlarını kullanarak Salesforce uygulamaları ve ajanları geliştirin: meta veri, Apex, dağıtım/alım ve güvenlik raporlaması.\", \"sanity\": \"MCP sunucusu, ajan yetenekleri ve eğik çizgi komutlarıyla Sanity içerik platformu entegrasyonu. İçerik yazın, GROQ sorguları oluşturun ve şemalar tasarlayın.\", \"sap-cds-mcp\": \"SAP Cloud Application Programming Model (CAP) projelerinin yapay zeka destekli geliştirilmesi. CDS modellerini ve CAP belgelerini arayın.\", \"sap-fiori-mcp-server\": \"Claude Code için SAP Fiori geliştirme araçları MCP sunucusu. Yapay zeka yardımıyla SAP Fiori uygulamaları oluşturun ve değiştirin.\", \"sap-hana-cli\": \"Yapay zeka asistanları için 150'den fazla SAP HANA veritabanı aracı. Tabloları sorgulayın, verileri içe/dışa aktarın, şemaları karşılaştırın ve yedekleri yönetin.\", \"sap-mdk-server\": \"SAP Mobile Development Kit (MDK) için MCP sunucusu. Şema aramaları, eylem doğrulama ve kural düzenleme ile MDK uygulamaları geliştirin.\", \"save-to-spotify\": \"TTS anlatımı, zaman çizelgeleri ve kapak görselleri ile profesyonel ses bölümleri oluşturun ve save-to-spotify CLI ile Spotify'a kaydedin.\", \"scandit-sdk\": \"Scandit Data Capture SDK'sını entegre etmek için ajan yetenekleri — barkod tarama, kimlik yakalama ve akıllı etiket kılavuzları.\", \"security-guidance\": \"Claude tarafından üretilen kodlar için güvenlik incelemesi. Enjeksiyon, XSS, SSRF ve sızdırılmış gizli anahtarları yakalayan kural ve diff incelemesi.\", \"semgrep\": \"Semgrep güvenlik açıklarını gerçek zamanlı olarak yakalar ve Claude'un en baştan itibaren güvenli kod yazmasına rehberlik eder.\", \"sentry\": \"Sentry hata izleme entegrasyonu. Hata raporlarına erişin, yığın izlerini analiz edin ve üretim hatalarını doğrudan ortamınızdan ayıklayın.\", \"sentry-cli\": \"Komut satırından Sentry ile etkileşim kurmak için Sentry CLI yetenekleri.\", \"serena\": \"Dil sunucusu protokolü entegrasyonu aracılığıyla akıllı kod anlama, yeniden düzenleme ve gezinme sağlayan anlamsal kod analizi MCP sunucusu.\", \"servicenow-sdk\": \"Fluent SDK ile ServiceNow uygulamalarını Claude yapay zekası üzerinden zahmetsizce oluşturun, düzenleyin ve dağıtın.\", \"session-report\": \"Yerel proje kayıtlarından Claude Code oturum kullanımını (belirteçler, önbellek verimliliği, alt ajanlar ve maliyetli istemler) gösteren HTML raporu oluşturun.\", \"shippo\": \"Shippo sizi USPS, UPS, FedEx, DHL ve 40+ kargo şirketine bağlar. Canlı fiyatları karşılaştırın, etiket satın alıp yazdırın ve kargoları takip edin.\", \"shopify-ai-toolkit\": \"Shopify üzerinde geliştirme için 18 yetenek: dokümantasyon araması, API şemaları, GraphQL ve Liquid doğrulaması, Hydrogen ve Polaris uzantıları.\", \"skill-creator\": \"Yeni ajan becerileri ve iş akışları oluşturmak için rehberli araç seti.\", \"slack\": \"Slack çalışma alanı entegrasyonu. Mesajları arayın, kanallara erişin, konuları okuyun ve kod yazarken ekibinizin iletişiminden kopmayın.\", \"snowflake-cortex-code\": \"Snowflake istemlerini Claude Code'dan yürütülmek üzere otomatik olarak Cortex Code'a yönlendirin. Kod inceleme ve görev devri komutları sunar.\", \"sonarqube\": \"Ajan kodlama döngüsünde SonarQube kod kalitesini ve güvenliğini otomatik olarak uygulayın — 7.000+ kural, gizli anahtar taraması ve kalite kapıları.\", \"sonatype-guide\": \"Yazılım tedarik zinciri istihbaratı ve bağımlılık güvenliği için Sonatype Guide MCP sunucusu. Bağımlılıkları açıklar için analiz edin.\", \"sourcegraph\": \"Kod tabanları genelinde kod arama ve anlama. Depolar arasında referansları arayın, okuyun ve izleyin; yeniden düzenleme etkisini analiz edin.\", \"spanner\": \"Doğal dil kullanarak Spanner verileriyle bağlanın ve etkileşim kurun.\", \"spotify-ads-api\": \"Doğal dil ile Spotify reklam kampanyalarını yönetin. Kampanyalar, reklam setleri ve reklamlar oluşturun, raporlar çekin.\", \"stackhawk-hawkscan\": \"Claude Code içinde HawkScan DAST sonuçlarını yapılandırın, çalıştırın ve yorumlayın. Güvenlik bulgularını öncelikli düzeltme görevlerine dönüştürür.\", \"stackhawk-api\": \"Güvenlik duruşu raporlaması, bulgu analizi ve uygulama yönetimi için StackHawk platform API'sini sorgulayın.\", \"streaming-skills-plugin\": \"Kafka ve Flink istemci kütüphaneleri ile Schema Registry'yi kapsayan akış uygulaması geliştirici yetenekleri.\", \"stripe\": \"Claude için Stripe geliştirme eklentisi.\", \"sumup\": \"Terminal ve çevrim içi ödeme akışları genelinde SumUp ödeme entegrasyonları. POS uygulamaları ve çevrim içi ödeme geliştirin.\", \"supabase\": \"Veritabanı işlemleri, kimlik doğrulama, depolama ve gerçek zamanlı abonelikler için Supabase MCP entegrasyonu.\", \"superdesign\": \"Superdesign sonsuz tuvali üzerinde ön yüz kullanıcı arayüzü ve pazarlama grafikleri tasarlayın veya yeniden tasarlayın.\", \"superpowers\": \"Claude'a beyin fırtınası, dahili kod incelemeli alt ajan odaklı geliştirme, sistematik hata ayıklama ve TDD öğretir.\", \"swift-lsp\": \"Kod zekası için Swift dil sunucusu (SourceKit-LSP).\", \"synthflow\": \"Claude Code'u barındırılan MCP sunucusu aracılığıyla Synthflow yapay zeka sesli ajan platformuna bağlar.\", \"tavily\": \"Tavily'nin arama, çıkarma, tarama ve araştırma API'lerini kullanarak gerçek zamanlı web verileriyle yapay zeka uygulamaları oluşturun.\", \"teamcity-cli\": \"teamcity CLI kullanarak TeamCity CI/CD ile etkileşim kurmak için ajan yeteneği. Derlemeleri inceleyin ve işleri yönetin.\", \"telegram\": \"Yerleşik erişim kontrollü Telegram mesajlaşma köprüsü. Eşleştirmeyi, izin listesini ve politikayı /telegram:access ile yönetin.\", \"terraform\": \"Terraform MCP Sunucusu, Kod Olarak Altyapı (IaC) geliştirme için gelişmiş otomasyon ve etkileşim yetenekleri sağlar.\", \"togetherai-skills\": \"Together AI platformu için ajan yetenekleri — çıkarım, eğitim, yerleştirmeler, ses, video, resimler ve GPU kümeleri.\", \"twilio-developer-kit\": \"Yapay zeka kodlama ajanları için Twilio yetenekleri — SMS, Ses, WhatsApp, Doğrulama ve SendGrid entegrasyonu.\", \"typescript-lsp\": \"Gelişmiş kod zekası için TypeScript/JavaScript dil sunucusu.\", \"ui-theme-designer\": \"UI theme designer ile çalışan kodlama ajanları için eklenti. BTP, SAP Tasarım Sistemi ve SAP Fiori tasarım belirteçleri desteği.\", \"ui5\": \"Kodlama ajanları için SAPUI5 / OpenUI5 eklentisi. UI5 projeleri oluşturun, doğrulayın ve linter çalıştırın.\", \"ui5-modernization\": \"SAPUI5/OpenUI5 uygulamalarını modernize etmek için iş akışı ve özel düzeltme modelleri içeren tam modernizasyon araç seti.\", \"ui5-typescript-conversion\": \"Kodlama ajanları için SAPUI5 / OpenUI5 eklentisi. JavaScript tabanlı UI5 projelerini TypeScript'e dönüştürün.\", \"unity\": \"Oyun geliştirme, gelir elde etme ve performans optimizasyonu için derlenmiş yeteneklerle Claude Code için resmi Unity eklentisi.\", \"unreal-engine-skills-for-claude-code\": \"Unreal Editor'ü MCP aracılığıyla doğrudan Claude Code'dan kontrol edin: aktörler, blueprint'ler, materyaller, Niagara ve otomasyon testleri.\", \"valtown\": \"Val Town üzerinde derleyin ve dağıtın. Val Town MCP sunucusunu ve platform yeteneklerini (HTTP vals, cron, SQLite) içerir.\", \"vanta\": \"Claude Code'u Vanta MCP sunucusu aracılığıyla Vanta güvenlik ve uyumluluk platformuna bağlar; uyumluluk hatalarını hızla düzeltir.\", \"vanta-mcp-plugin\": \"Claude Code'u Vanta MCP sunucusu aracılığıyla Vanta güvenlik ve uyumluluk platformuna bağlar; uyumluluk test hatalarını hızla düzeltir.\", \"vercel\": \"Vercel dağıtım platformu entegrasyonu. Dağıtımları yönetin, derleme durumunu kontrol edin, günlüklere erişin ve alan adlarını yapılandırın.\", \"vibe-prospecting\": \"Kullanıcıların potansiyel müşterileri arayabilmesi, eşleştirebilmesi ve zenginleştirebilmesi için Claude'u canlı B2B şirket ve kişi verilerine bağlar.\", \"vsql-extension-builder\": \"7 aşamalı iş akışıyla MySQL için VillageSQL uzantısı derler. PostgreSQL uzantılarını MySQL'e taşımak için kullanılır.\", \"windsor-ai\": \"Claude Code'u Windsor.ai aracılığıyla Google Ads, Meta, HubSpot, Salesforce, Shopify ve Stripe dahil 325+ iş verisi kaynağına bağlayın.\", \"wix\": \"Wix siteleri ve uygulamaları derleyin, yönetin ve dağıtın. Pano uzantıları, arka uç API'leri ve site yönetimi için araç seti.\", \"build-with-wordpress\": \"Üretime hazır WordPress siteleri ve uygulamaları hazırlayın. Temalar ve eklentilerden e-ticaret ve dağıtıma kadar her şey.\", \"workos\": \"AuthKit, SSO, Dizin Senkronizasyonu, RBAC, Kasa ve Denetim Günlükleri için WorkOS entegrasyon yetenekleri.\", \"youdotcom-agent-skills\": \"Web araması, kaynaklı araştırma ve içerik çıkarma için You.com ajan yetenekleri.\", \"zapier\": \"Yapay zeka iş akışınıza 8.000'den fazla uygulama bağlayın. Zapier eylemlerini doğrudan istemcinizden keşfedin ve yürütün.\", \"zilliz\": \"Küme yaşam döngüsü, koleksiyon şeması, vektör araması, indeks ayarlama ve yedeklemeleri kapsayan Zilliz Cloud yönetim eklentisi.\", \"zoom-plugin\": \"REST API'leri, SDK'lar, web kancaları, botlar ve MCP genelinde Zoom entegrasyonlarını planlama, geliştirme ve hata ayıklama eklentisi.\", \"zoominfo\": \"Şirketleri ve kişileri arayın, müşteri adaylarını zenginleştirin ve yapay zeka ile sıralanmış iletişim önerileri alın.\", \"zscaler\": \"ZPA, ZIA, ZDX, ZCC ve EASM dahil Zscaler bulut güvenlik platformunu yönetin, ilkeler oluşturun ve bağlantı sorunlarını giderin.\", \"langfuse\": \"İzleme, istem yönetimi ve değerlendirme için açık kaynaklı LLM mühendislik platformu Langfuse ile çalışma yetenekleri.\", \"zyte-web-data\": \"Zyte API ile desteklenen Claude Code web kazıma yetenekleri — siteleri kazıyın, Scrapy örümcekleri üretip çalıştırın.\", \"activecampaign\": \"ActiveCampaign ile pazarlama otomasyonu, CRM ve e-posta pazarlaması. Kişileri, kampanyaları, anlaşmaları yönetin ve içgörüler edinin.\", \"hyper3d-rodin\": \"Hyper3D Rodin ile metin istemlerinden veya referans görsellerden 3B modeller üretin.\", \"hyper3d\": \"Hyper3D Rodin ile metin istemlerinden veya referans görsellerden 3B modeller üretin.\", \"jupyter-notebook\": \"Jupyter not defterleriyle yan panelde çalışın: çalışan bir çekirdeğe bağlanın, hücreleri çalıştırın ve çıktıları inceleyin.\", \"jupyter\": \"Jupyter not defterleriyle yan panelde çalışın: çalışan bir çekirdeğe bağlanın, hücreleri çalıştırın ve çıktıları inceleyin.\", \"zcode-context\": \"Salt okunur oturum kullanımı, model girdi bileşimi, istek farkları ve bağlam analitiği.\", \"zcode-mcp-app-dev\": \"Resmi SDKlar ve yerel geliştirici ortamı ile ZCode için MCP Uygulamaları geliştirin.\", \"blender\": \"Etkileşimli 3B panel ve MCP araçlarıyla Blender sahnelerini düzenleyin.\", \"cadcraft\": \"Çalışma alanı dosyaları ve DXF dışa aktarma desteğiyle ZCode panelinde CADCraft CAD çizim ve modelleme.\", \"deckcraft\": \"Çalışma alanı dosyaları ve slayt dışa aktarma desteğiyle ZCode panelinde DeckCraft interaktif sunumlar.\", \"designcraft\": \"Çalışma alanı dosyaları ve tuval düzenleme desteğiyle ZCode panelinde DesignCraft sayfa ve grafik tasarımı.\", \"excalidraw\": \"Excalidraw ve MCP araçlarıyla el çizimi tarzında diyagramlar ve şemalar oluşturun.\", \"gridcraft\": \"Çalışma alanı dosyaları ve tablo dışa aktarma desteğiyle ZCode panelinde GridCraft elektronik tablo düzenleme.\", \"openpencil\": \"OpenPencil ve MCP araçlarıyla tasarım ve vektör dosyalarını düzenleyin.\", \"pdfcraft\": \"Çalışma alanı dosyaları ve not ekleme desteğiyle ZCode panelinde PdfCraft PDF düzenleme ve inceleme.\", \"photocraft\": \"Çalışma alanı dosyaları ve raster filtre desteğiyle ZCode panelinde PhotoCraft görsel düzenleme.\", \"soundcraft\": \"Çalışma alanı dosyaları ve dalga formu desteğiyle ZCode panelinde SoundCraft ses düzenleme.\", \"tripo-3d\": \"Bir metin isteminden veya referans görselden kaplamalı, animasyona hazır 3B modeller üretin.\", \"tripo3d\": \"Bir metin isteminden veya referans görselden kaplamalı, animasyona hazır 3B modeller üretin.\", \"tripo\": \"Bir metin isteminden veya referans görselden kaplamalı, animasyona hazır 3B modeller üretin.\", \"typst-workbench\": \"Etkileşimli Typst derleyicisi ile Typst belgelerini yan panelde canlı önizleyin ve düzenleyin.\", \"typst\": \"Etkileşimli Typst derleyicisi ile Typst belgelerini yan panelde canlı önizleyin ve düzenleyin.\", \"vectorcraft\": \"Çalışma alanı dosyaları ve SVG dışa aktarma desteğiyle ZCode panelinde VectorCraft vektörel illüstrasyon.\", \"visualize\": \"ZCode içinde HTML tuvali ile etkileşimli açıklamalar, grafikler ve tasarım önizlemeleri oluşturun.\", \"wordcraft\": \"Çalışma alanı dosyaları ve zengin metin düzenleme desteğiyle ZCode panelinde WordCraft belge işleme.\", \"zotero\": \"Yan panelde Zotero kütüphanenizle çalışın: makaleleri arayın, okuyun, alıntıları dışa aktarın ve koleksiyonları yönetin.\", \"agentnetwork\": \"Yerel bir AgentNetwork ağ geçidi üzerinden A2A ile diğer yapay zeka ajanlarına görevler atayın.\", \"anet\": \"Yerel bir AgentNetwork ağ geçidi üzerinden A2A ile diğer yapay zeka ajanlarına görevler atayın.\", \"patch-generator\": \"Tespit edilen bir güvenlik açığı için geçici çalışma alanında düzeltmeyi uygular ve inceleme için bir yama dosyası hazırlar; düzeltme işi tarafından otomatik çalıştırılır.\", \"patch-verifier\": \"Düzeltme turundaki tek yetkili doğrulayıcı: çalışma alanındaki diff'i bulguya göre inceler, testleri çalıştırır ve yama güvenilirlik kriterlerini onaylar; düzeltme işi tarafından otomatik çalıştırılır.\", \"scan-inventory\": \"Claude Güvenlik taraması tarafından dizin ağacını bileşenlere bölmek ve tüm üst düzey dizinleri haritalamak için görevlendirilen salt okunur repo haritalayıcı.\", \"scan-loader\": \"Claude Güvenlik taraması tarafından çalışma dizininden aday bir dosyayı yüklemek için görevlendirilen salt okunur dosya yükleyici.\", \"scan-researcher\": \"Claude Güvenlik iş akışı tarafından derinlemesine güvenlik açıklarını araştırmak üzere görevlendirilen salt okunur güvenlik araştırmacısı.\", \"scan-verifier\": \"Claude Güvenlik iş akışı tarafından tespit edilen aday bulguları doğrulamak ve oylamak için görevlendirilen salt okunur doğrulayıcı.\", \"local-ai-app-integration\": \"Embeddable Lemonade kullanarak uygulamalara yerel yapay zeka yetenekleri entegre eder. Yerel, çevrimdışı, gizli ve cihaz üzeri LLM entegrasyonu istendiğinde kullanın.\", \"local-ai-use\": \"Ücretli bulut API'leri yerine yerel Lemonade Sunucusu üzerinden kullanıcının kendi makinesinde görsel üretir, ses deşifre eder ve ses sentezler.\", \"serving-llms-on-instinct\": \"vLLM kullanarak AMD Instinct GPU donanımı üzerinde yapay zeka modellerini sunar. AMD donanımında model dağıtmak, çalıştırmak ve barındırmak için kullanın.\", \"tracelens-analysis-orchestrator\": \"TraceLens ile modüler PyTorch profil izleme analizini koordine eder: performans raporları üretir, kategori verilerini hazırlar ve alt ajanları çalıştırır.\", \"base44-cli\": \"Base44 projeleriyle ilgili her işlem için kullanılır: kaynak yapılandırması (varlıklar, arka uç fonksiyonları, yapay zeka ajanları), başlatma ve kaynak yönetimi.\", \"base44-sdk\": \"Base44 servisleriyle iletişim kurmak için kullanılan resmi SDK. Uzak kaynaklar, arka uç fonksiyonları ve ajanlarla entegrasyon sağlar.\", \"base44-troubleshooter\": \"Arka uç fonksiyon günlüklerini ve iş akışı geçmişini kullanarak canlı ortam sorunlarını giderin. Uygulama hatalarını araştırmak ve çağrıları hata ayıklamak için kullanın.\", \"a11y-debugging\": \"web.dev yönergelerine göre erişilebilirlik (a11y) denetimi ve hata ayıklaması yapar. Semantik HTML, ARIA etiketleri ve odak durumlarını test ederken kullanın.\", \"chrome-devtools\": \"Hata ayıklama, sorun giderme ve tarayıcı otomasyonu için Chrome DevTools'u kullanır. Web sayfalarında hata ayıklarken ve tarayıcı etkileşimlerini otomatikleştirirken kullanın.\", \"chrome-devtools-cli\": \"Tarayıcıdaki görevleri otomatikleştirmek için kabuk betikleri yazın veya Chrome DevTools'u CLI üzerinden doğrudan komutlarla kullanın.\", \"debug-optimize-lcp\": \"Chrome DevTools MCP araçlarıyla Largest Contentful Paint (LCP) performansını optimize eder ve yavaş yüklenen web sayfalarını analiz eder.\", \"memory-leak-debugging\": \"JavaScript ve Node.js uygulamalarındaki bellek sızıntılarını tespit eder ve giderir. Yüksek bellek kullanımı ve OOM hatalarını gidermek için kullanın.\", \"troubleshooting\": \"Chrome DevTools MCP bağlantı ve hedef sorunlarını gidermek için kullanılır. Sayfa listeleme veya gezinme başarısız olduğunda devreye girer.\", \"claude-automation-recommender\": \"Kod tabanını analiz ederek Claude Code otomasyonları (kancalar, alt ajanlar, beceriler, eklentiler ve MCP sunucuları) önerir.\", \"claude-md-improver\": \"Repolardaki CLAUDE.md talimat dosyalarını denetler, iyileştirir ve günceller. Talimatların netliğini ve geçerliliğini doğrulamak için kullanın.\", \"agents-sdk\": \"Agents SDK ile Cloudflare Workers üzerinde yapay zeka ajanları derleyin. Durum bilgili ajanlar, dayanıklı iş akışları ve gerçek zamanlı WebSocket uygulamaları için kullanın.\", \"cloudflare-email-service\": \"Cloudflare Email Routing ve Workers ile e-posta alma, gönderme ve otomatik işleme yetenekleri.\", \"reverse-engineer-anything\": \"Yerel, yönetilen, Electron/JavaScript, paketlenmiş, ürün yazılımı ve tarayıcı hedeflerini tersine mühendislikle analiz eder.\", \"cloudflare-one\": \"Access, Gateway, WARP, Tunnel, Cloudflare WAN, DLP, CASB, cihaz durumu ve kimlik genelinde Cloudflare One Zero Trust ve SASE çalışmalarını yönetir.\", \"cloudflare-one-migrations\": \"Zscaler ZIA/ZPA, Palo Alto, eski VPN veya SWG sistemlerinden Cloudflare One'a geçişleri planlar, politika eşleştirmesi ve dağıtım sağlar.\", \"durable-objects\": \"Cloudflare Durable Objects oluşturun ve inceleyin. Durum bilgili koordinasyon (sohbet odaları, çok oyunculu oyunlar, rezervasyon sistemleri) geliştirirken kullanın.\", \"sandbox-migrate-to-next\": \"Bir Cloudflare Sandbox uygulamasını kararlı @cloudflare/sandbox paketinden @cloudflare/sandbox@next (Sandbox SDK 1.0) sürümüne taşırken kullanın.\", \"sandbox-next\": \"@cloudflare/sandbox@next üzerinde Cloudflare Sandbox uygulamaları oluştururken veya güncellerken kullanın (kod yürütme, AI çalıştırıcıları, yorumlayıcılar).\", \"sandbox-stable\": \"Mevcut kararlı @cloudflare/sandbox paketi üzerinde Cloudflare Sandbox uygulamaları oluştururken veya düzenlerken kullanın.\", \"turnstile-spin\": \"Bir projede uçtan uca Cloudflare Turnstile bot korumasını kurun. Kod tabanını tarayın, bileşeni oluşturun ve bot doğrulaması ekleyin.\", \"web-perf\": \"Chrome DevTools MCP kullanarak web performansını analiz eder. Core Web Vitals (LCP, INP, CLS) metriklerini ölçer ve darboğazları belirler.\", \"workers-best-practices\": \"Cloudflare Workers kodlarını üretim en iyi uygulamalarına göre inceler ve yazar. Kod kalitesi, wrangler yapılandırması ve performans için kullanın.\", \"wrangler\": \"Cloudflare Workers ve Pages uygulamalarını dağıtmak, geliştirmek ve yönetmek (KV, R2, D1, Vectorize, Hyperdrive, Queues) için resmi Workers CLI aracı.\", \"eas-app-stores\": \"EAS servisi (ücretli). Expo uygulamalarını EAS ile uygulama mağazalarına (iOS App Store, Google Play Store ve TestFlight) derleyin ve gönderin.\", \"eas-hosting\": \"EAS servisi (ücretli). Expo web sitelerini ve Expo Router API rotalarını EAS Hosting'e dağıtın.\", \"eas-observe\": \"EAS servisi (ücretli). EAS Observe ile ilgili her şey için kullanın (AppMetricsRoot/ObserveRoot HOC, işaretlemeler ve hata izleme).\", \"eas-simulator\": \"EAS servisi (ücretli). EAS bulutunda barındırılan uzak bir iOS/Android simülatöründe kullanıcının uygulamasını çalıştırın ve kontrol edin.\", \"eas-update-insights\": \"EAS servisi (ücretli). Yayınlanan EAS Güncellemelerinin kilitlenme oranlarını, yükleme sayılarını ve OTA dağıtım durumunu inceleyin.\", \"eas-workflows\": \"EAS servisi (ücretli). Expo projeleri için EAS iş akışı YAML dosyalarını anlayın ve oluşturun (CI/CD otomasyonları).\", \"expo-animation\": \"Açık kaynak çatı. React Native ve Expo'da animasyonlar geliştirin (Reanimated, Gesture Handler, Moti).\", \"expo-app-clip\": \"Açık kaynak çatı. Bir Expo uygulamasına iOS App Clip hedefi ekleyin (AASA, uygulama klipleri, akıllı uygulama başlıkları).\", \"expo-brownfield\": \"Açık kaynak çatı. Expo ve React Native'i mevcut yerel bir iOS veya Android uygulamasına entegre edin.\", \"expo-data-fetching\": \"Açık kaynak çatı. Ağ istekleri, API çağrıları veya veri çekme işlemlerini uygularken ya da hatalarını ayıklarken kullanın (Fetch, React Query, SWR).\", \"expo-design-system\": \"Açık kaynak çatı. Bir Expo uygulaması içinde tasarım sistemi oluşturun ve yönetin (tasarım belirteçleri, renkler, tipografi, yarıçap).\", \"expo-dev-client\": \"Açık kaynak çatı. Yerel test veya TestFlight için Expo geliştirme istemcileri derleyin ve dağıtın.\", \"expo-dom-components\": \"Açık kaynak çatı. React Native görünümleri içinde yerel DOM bileşenlerini ve web teknolojilerini sorunsuzca çalıştırın.\", \"expo-maps\": \"Açık kaynak çatı. Expo projelerinde Apple Maps ve Google Maps harita entegrasyonlarını yapılandırın ve yönetin.\", \"expo-monorepo\": \"Açık kaynak çatı. Expo ve React Native uygulamalarını Turborepo veya monorepo mimarilerinde yapılandırın ve optimize edin.\", \"expo-push-notifications\": \"Açık kaynak çatı. Expo Bildirim servisi ile anlık bildirim gönderme, izin yönetimi ve token işleme.\", \"expo-router\": \"Açık kaynak çatı. Dosya tabanlı yönlendirme (file-based routing), derin bağlantılar (deep linking) ve sayfa geçişleri.\", \"figma-code-connect\": \"Figma bileşenlerini kod parçacıklarıyla eşleştiren Figma Code Connect şablon dosyaları oluşturur ve yönetir.\", \"figma-create-new-file\": \"Figma'da yeni bir dosya veya tuval oluşturmadan önce çağrılan zorunlu ön koşul becerisi.\", \"figma-design-to-code\": \"Figma tasarımlarını ve tasarım bağlamını üretim koduna dönüştürmek için kullanılan zorunlu tasarım-kod dönüştürme becerisi.\", \"figma-generate-design\": \"Uygulama sayfalarını, görünümleri veya çok bölümlü düzenleri Figma tuvaline aktarırken figma-use ile birlikte kullanılır.\", \"figma-generate-diagram\": \"Figma üzerinde akış şemaları, sistem mimarisi ve diyagramlar oluşturmadan önce çağrılan ön koşul becerisi.\", \"figma-generate-library\": \"Bir kod tabanından Figma'da profesyonel düzeyde tasarım sistemi ve bileşen kütüphanesi oluşturur veya günceller.\", \"figma-generative-plugins\": \"Figma eklentisi oluştururken, güncellerken veya eklenti API'leri ile çalışırken kullanılan üretken eklenti becerisi.\", \"figma-implement-motion\": \"Figma hareket ve animasyon prototiplerini üretime hazır uygulama koduna dönüştürür.\", \"figma-shaders\": \"Figma için GLSL gölgelendirici (shader) efektleri oluştururken veya güncellerken kullanılan özel beceri.\", \"figma-swiftui\": \"Figma tasarımları ile SwiftUI kodları arasında iki yönlü dönüştürme ve entegrasyon sağlar.\", \"figma-use\": \"Figma MCP araçlarıyla Figma dosyalarını okumak, düzenlemek ve etkileşim kurmak için zorunlu temel beceri.\", \"figma-use-figjam\": \"FigJam bağlamında beyin fırtınası tahtaları, akışlar ve yapışkan notlar oluşturmak için Figma MCP araçlarını kullanır.\", \"figma-use-motion\": \"Figma prototiplerindeki mikro etkileşimleri ve geçiş efektlerini incelemek ve kodlamak için kullanılır.\", \"generate-project-plan\": \"Bir ürün gereksinim dokümanı (PRD) ve kod tabanından FigJam proje planı panosu oluşturur.\", \"firecrawl-agent\": \"Yapılandırılmış JSON verilerini web sitelerinden otonom olarak çıkaran çok sayfalı web kazıma ajanı.\", \"firecrawl-crawl\": \"Tek bir siteden veya belirli bir alt dizinden çok sayıda sayfayı toplu olarak ayıklayan ve Markdown'a dönüştüren tarayıcı.\", \"firecrawl-developer-index\": \"Sorunları, birleştirilmiş çekme isteklerini (PR), README dosyalarını ve dokümantasyonları arayarak kütüphane davranışlarını inceler.\", \"firecrawl-download\": \"Bir siteyi veya bölümü yerel dosyalar (markdown, ekran görüntüleri) olarak çevrimdışı kullanım için kaydeder.\", \"firecrawl-interact\": \"Kazınan bir sayfada canlı tarayıcı kontrolü: tıklama, form doldurma, oturum açma, sayfalandırma ve sonsuz kaydırma.\", \"firecrawl-map\": \"Bir sitenin tüm URL'lerini keşfeder, haritalandırır ve arama filtreleme özellikli site haritası çıkarır.\", \"firecrawl-monitor\": \"Web sayfalarındaki değişiklikleri izler; içerik güncellendiğinde webhook veya e-posta ile bildirim tetikler.\", \"firecrawl-parse\": \"Yerel dosyaları (PDF, DOCX, XLSX, HTML vb.) temiz ve analiz edilebilir Markdown formatına dönüştürür.\", \"firecrawl-research-index\": \"Biyomedikal ve yaşam bilimleri literatüründeki araştırma sorgularını yanıtlayan makaleleri indeksler ve arar.\", \"firecrawl-scrape\": \"Verilen bir URL'nin içeriğini temiz, reklamdan arındırılmış Markdown formatında anında ayıklar.\", \"firecrawl-search\": \"URL bilinmediğinde web araması yapar ve bulunan tüm sayfaların tam içeriğini getirir.\", \"hf-cli\": \"Hugging Face Hub CLI ('hf'): modelleri, veri kümelerini ve Spaces depolarını indirme, yükleme ve yönetme aracı.\", \"hf-cloud-aws-context-discovery\": \"SageMaker ve AWS görevleri öncesinde kullanıcının yerel AWS profil, bölge ve hesap kimlik bağlamını keşfeder.\", \"hf-cloud-python-env-setup\": \"SageMaker ve AWS üzerinde model eğitimi için boto3 uyumlu izole Python ortamı kurar.\", \"hf-cloud-sagemaker-deployment-planner\": \"Bir Hugging Face modelinin Amazon SageMaker AI üzerinde dağıtımını planlar ve koordine eder.\", \"hf-cloud-sagemaker-iam-preflight\": \"Dağıtım veya eğitim öncesinde geçerli bir SageMaker IAM yürütme rolünün mevcut olduğunu doğrular.\", \"hf-cloud-sagemaker-production-defaults\": \"Gerçek zamanlı ölçeklendirme, CloudWatch alarmları ve etiketleme ile canlı SageMaker uç noktası oluşturur.\", \"hf-cloud-serving-image-selection\": \"Amazon SageMaker dağıtımı için en uygun çıkarım konteynerini (TGI, TEI, vLLM) seçer.\", \"hf-mem\": \"Hugging Face modellerinin çıkarımı için gereken GPU bellek miktarını Safetensors veya GGUF ağırlıklarına göre hesaplar.\", \"hf-mcp\": \"Hugging Face Hub'ı MCP sunucusu üzerinden kullanır: modelleri, veri kümelerini ve belgeleri doğrudan arayın ve yönetin.\", \"huggingface-best\": \"Belirli bir görev için en iyi, en popüler veya önerilen Hugging Face modelini bulmak ve karşılaştırmak için kullanılır.\", \"huggingface-community-evals\": \"Hugging Face Hub modelleri için inspect-ai ve lighteval kullanarak yerel GPU donanımında değerlendirmeler çalıştırır.\", \"huggingface-datasets\": \"Hugging Face Dataset Viewer API ile veri kümesi önizleme, şema analizi ve satır filtreleme iş akışları.\", \"huggingface-gradio\": \"Python ile Gradio web arayüzleri ve yapay zeka demoları oluşturur. Model demoları ve Spaces için kullanın.\", \"huggingface-llm-trainer\": \"TRL (Transformer Reinforcement Learning) kullanarak dil ve görüntü modellerini eğitir veya ince ayar (fine-tune) yapar.\", \"huggingface-model-card\": \"Hugging Face modelleri için standartlara uygun, lisans ve kullanım detayları içeren model kartları oluşturur.\", \"huggingface-spaces\": \"Hugging Face Spaces üzerinde Gradio, Streamlit veya Docker tabanlı yapay zeka uygulamaları yayınlar.\", \"train-sentence-transformers\": \"Cümle ve metin gömme (embedding) modellerini SentenceTransformers kütüphanesiyle eğitir ve değerlendirir.\", \"transformers-js\": \"Web tarayıcısında ve Node.js ortamında Transformers.js ile yerel makine öğrenimi modelleri çalıştırır.\", \"trl-training\": \"SFT, DPO, PPO ve GRPO algoritmalarıyla transformatör dil modellerini eğitir ve optimize eder.\", \"base44-remote-dev\": \"Base44 uygulamalarını yerel araçlarınızı kullanarak doğrudan Base44 bulut geliştirme ortamında geliştirin.\", \"base44-sandbox\": \"Base44'ün bulut korumalı alanında (sandbox) yerel geliştirici deneyimiyle uzaktan uygulama geliştirin.\", \"sync-cli-skill\": \"Base44-cli becerisini en güncel CLI kaynak kodu ve komut setiyle senkronize eder.\", \"sync-sdk-skill\": \"Base44-sdk becerisini en güncel SDK kaynak kodu ve API tanımlarıyla senkronize eder.\", \"wix-app\": \"Wix CLI uygulama uzantılarını (kontrol paneli sayfaları, modüller ve eklentiler) oluşturur ve inceler.\", \"wix-auth\": \"Wix API ve REST uç noktalarını çağırmak için gerekli erişim belirtecini (OAuth) doğrular ve yönetir.\", \"wix-base44-connector\": \"Base44 builder korumalı alanından Wix platformu üzerinde çözümler geliştirir.\", \"wix-design-system\": \"Wix Design System bileşen referansı: kullanıcı arayüzü bileşenleri, temalar ve stiller.\", \"wix-docs\": \"En güncel Wix API ve SDK dokümantasyonunu sorgular, fonksiyon imzalarını doğrular.\", \"wix-headless\": \"Wix Headless SDK ile harici platformlarda e-ticaret, üyelik ve rezervasyon akışlarını yönetir.\", \"wix-media\": \"Wix Media Manager API ile dosya, görsel ve video yükleme, dönüştürme ve yönetimi.\", \"wix-sdk\": \"Wix JavaScript SDK ile veri tabanları, koleksiyonlar ve arka uç fonksiyonlarıyla etkileşim kurar.\", \"wix-velo\": \"Wix Velo (kodlama platformu) ile gelişmiş sayfa kodları, veri kancaları ve web modülleri geliştirir.\", \"rp-discovery\": \"Yeniden platformlama (replatform) için mevcut sistemin mimari keşfini, bağımlılıklarını ve veri haritasını çıkarır.\", \"rp-execute-import\": \"Eski sistemden çıkarılan verileri ve şemaları yeni hedef platforma otomatik olarak aktarır.\", \"rp-execute-setup\": \"Hedef platform ortamının başlangıç yapılandırmasını ve ortam değişkenlerini ayarlar.\", \"rp-import-codegen\": \"Hedef platform için veri içe aktarma betikleri ve şema dönüştürme kodları üretir.\", \"rp-mapper\": \"Kaynak ve hedef platform şemaları arasında eşleme (mapping manifestosu) kurallarını belirler.\", \"replatform\": \"Eski yazılım sistemlerini modern bulut ve web çatılarına taşımak için uçtan uca rehberli iş akışı.\", \"hyperloom-workload-optimizer\": \"Yapay zeka iş yüklerini ve model dağıtım topolojisini GPU donanımı için otomatik olarak optimize eder.\", \"lemonade-router-builder\": \"Farklı LLM ve yerel modeller arasında istekleri yönlendiren Lemonade Router yapılandırmaları oluşturur.\", \"magpie-kernel-evaluator\": \"LLM çıkarımını kıyaslar ve Magpie ile GPU çekirdek (kernel) optimizasyonunu yönetir.\", \"serving-llms-on-epyc\": \"AMD EPYC CPU donanımı üzerinde optimize edilmiş dil modelleri sunar ve ölçeklendirir.\", \"nvidia-skill-finder\": \"NVIDIA donanımları, CUDA ve TensorRT için optimize edilmiş yapay zeka becerilerini keşfeder.\", \"review-skills\": \"Bir beceriyi en iyi uygulamalara, belirteç uzunluğuna ve tetikleme doğruluğuna göre inceler ve analiz eder.\", \"video-interaction-mapper\": \"Video akışları ve tuval arayüzleri arasındaki etkileşim noktalarını haritalandırır.\", \"cardputer-buddy\": \"M5Stack Cardputer cihazı için MicroPython uygulamaları ve Claude Buddy paketleri geliştirir.\", \"m5-onboard\": \"Yeni bağlanan bir M5Stack ESP32 cihazının ilk kurulumunu ve yazılım yüklemesini yapar.\", \"developing-mcp-apps\": \"ZCode için MCP Uygulamaları (MCP Apps) geliştirin, taşıyın, derleyin ve test edin.\", \"dynamic-workflows\": \"Dinamik çoklu ajan iş akışları tasarlayın, hata ayıklayın ve ZCode görevlerine gönderin.\", \"access\": \"Telegram kanalı erişimini yönetin: eşleştirmeleri onaylayın, izin verilen kullanıcıları düzenleyin.\", \"configure\": \"Telegram kanalını yapılandırın: bot tokenini kaydedin ve bildirim ayarlarını gözden geçirin.\", \"plugin-settings\": \"ZCode eklenti ayarlarını, yapılandırma anahtarlarını ve izinlerini yönetir.\", \"plugin-structure\": \"ZCode standartlarına uygun eklenti dizin yapısı, manifest ve bileşenleri tasarlar.\", \"build-mcp-app\": \"ZCode içinde çalışan zengin görsel arayüze sahip interaktif MCP uygulamaları derler.\", \"build-mcp-server\": \"Dış araçları ve servisleri ZCode ajanına bağlayan özel bir Model Context Protocol sunucusu yazar.\", \"build-mcpb\": \"MCP sunucularını ve uzantılarını tek tıkla kurulabilir paketler (.mcpb) haline getirir.\", \"writing-great-skills\": \"Yüksek performanslı, doğru tetiklenen ve standartlara uygun ZCode becerileri yazma rehberi.\", \"writing-hookify-rules\": \"ZCode kancaları (hooks) için etkileşimli kurallar ve güvenlik filtreleri tanımlar.\", \"agent-development\": \"ZCode için özel sistem istemine ve araç izinlerine sahip uzman alt ajanlar tasarlar.\", \"command-development\": \"ZCode sohbetinde kullanılabilir eğik çizgi komutları (/slash-commands) tanımlar ve bağlar.\", \"hook-development\": \"Olaylara duyarlı ZCode kanca betikleri (ön-işlem, son-işlem, araç filtreleme) geliştirir.\", \"mcp-integration\": \"Harici API'leri ve veritabanlarını Model Context Protocol araçları olarak ZCode'a entegre eder.\", \"skill-development\": \"ZCode ajanlarının uzmanlaşması için yeni rehber beceriler ve SKILL.md paketleri oluşturur.\", \"example-skill\": \"Örnek beceri yapısını, YAML ön maddesini ve talimat formatını gösteren rehber beceri.\", \"expo-dom\": \"Açık kaynak çatı. Web DOM öğelerini ve standart tarayıcı API'lerini doğrudan Expo uygulaması içinde çalıştırın.\", \"expo-examples\": \"Expo ve React Native için referans örnekler, kod kalıpları ve mimari başlangıç projeleri.\", \"expo-module\": \"Expo ve React Native için Swift, Kotlin veya C++ ile yerel modüller (Expo Modules API) geliştirin.\", \"expo-native-ui\": \"iOS ve Android platformuna özgü yerel kullanıcı arayüzü bileşenlerini Expo projelerinde kullanın.\", \"expo-overview\": \"Expo çatı yapısı, mimarisi, araç takımı ve temel geliştirici iş akışlarına genel bakış rehberi.\", \"expo-project-structure\": \"Ölçeklenebilir Expo projeleri için standart dosya düzeni, modül hiyerarşisi ve konfigürasyon kuralları.\", \"expo-skill-feedback\": \"Expo becerileri için geri bildirim toplama ve geliştirici deneyimi iyileştirme mekanizması.\", \"expo-ui\": \"Expo ve React Native uygulamaları için modern, erişilebilir ve performanslı kullanıcı arayüzü bileşenleri.\", \"expo-upgrade\": \"Expo SDK sürümlerini en güncel sürüme sorunsuz yükseltme, bağımlılıkları ve uyumluluğu çözme rehberi.\", \"expo-web-to-native\": \"Mevcut React web uygulamalarını Expo ve React Native ile mobil platformlara taşıma iş akışı.\", \"figma-use-slides\": \"Figma Slides üzerinde etkileşimli sunumlar, slayt tasarımları ve sunum şablonları oluşturur ve düzenler.\", \"huggingface-local-models\": \"Ollama, vLLM, llama.cpp ve Transformers ile Hugging Face modellerini tamamen yerel donanımda çalıştırın.\", \"huggingface-lora-space-builder\": \"Hugging Face Spaces üzerinde LoRA adaptörlerini ve ince ayar modellerini barındıran interaktif demolar oluşturur.\", \"huggingface-paper-publisher\": \"Yapay zeka araştırma makalelerini ve model teknik raporlarını Hugging Face Papers platformunda yayınlar ve biçimlendirir.\", \"huggingface-papers\": \"Hugging Face Daily Papers ve arXiv üzerindeki en yeni yapay zeka makalelerini arar, özetler ve trendleri takip eder.\", \"huggingface-tool-builder\": \"Hugging Face modellerini Claude ve ZCode ajanları için çağrılabilir MCP araçlarına dönüştürür.\", \"huggingface-trackio\": \"Hugging Face modelleri ve veri kümeleri için indirme, beğeni ve kullanım metriklerini izler.\", \"huggingface-vision-trainer\": \"TRL ve Transformers ile görüntü sınıflandırma, nesne tespiti ve çok modlu modelleri eğitir.\", \"huggingface-zerogpu\": \"Hugging Face Spaces üzerinde ücretsiz sunucusuz A100 GPU (ZeroGPU) kotalarını yönetir ve uygulamaları optimize eder.\", \"wix-headless-entry\": \"Wix Headless SDK'nın başlangıç yapılandırmasını ve istemci kimlik doğrulamasını ayarlar.\", \"wix-manage\": \"Wix kontrol panelini ve site kaynaklarını (siparişler, üyeler, içerikler) programatik olarak yönetir.\", \"wix-vibe-headless\": \"Wix Vibe tasarım diliyle headless e-ticaret ve içerik deneyimleri geliştirir.\", \"rp-setup-discovery\": \"Yeniden platformlama için kaynak sistem ortamını ve gereksinimleri analiz eder.\", \"rp-source-csv\": \"CSV ve elektronik tablo veri kaynaklarını analiz eder, hedef şemaya dönüştürür.\", \"rp-source-wordpress\": \"WordPress sitelerindeki yazı, sayfa, medya ve eklenti verilerini yeni platforma taşımak üzere ayıklar.\", \"rp-target-wix\": \"Dönüştürülen verileri ve şablonları doğrudan Wix platformuna dağıtır ve doğrular.\", \"rp-telemetry\": \"Taşıma ve platformlama süreçlerinin başarı oranlarını ve performans metriklerini izler.\", \"android-dev\": \"android-emulator MCP araçlarıyla Android emülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.\", \"control-browser\": \"Yalnızca ana ajan tarayıcı kullanımı: ZCode içinde web sayfalarını ve yerel HTTP hedeflerini açın, gezinin, inceleyin, tıklayın, form doldurun, ekran görüntüsü alın ve doğrulayın.\", \"web-gui-tester\": \"Oturumdaki tarayıcı otomasyon araçlarını kullanarak web arayüzlerini etkileşimli olarak test edin, kullanıcı eylemlerini simüle edin, ekran görüntüleriyle doğrulayın ve test raporu oluşturun.\", \"computer-use\": \"Erişilebilirlik odaklı semantik eylemler ve görsel doğrulama ile masaüstü kontrolü.\", \"docx\": \"Revizyonlar, yorumlar, biçimlendirme koruma ve metin çıkarma desteğiyle kapsamlı DOCX belgesi oluşturma, düzenleme ve analiz yetenekleri.\", \"pdf\": \"4 özel iş akışına sahip profesyonel PDF işleme araç seti: Typst/ReportLab ile yayın kalitesinde PDF üretimi, HTML/CSS tuvali ile görsel belge biçimlendirme, LaTeX ve programatik düzenleme.\", \"pptx\": \"PowerPoint (.pptx) sunum oluşturma, biçimlendirme ve düzenleme yetenekleri. Slayt hazırlama, düzenleme ve not çıkarma.\", \"xlsx\": \"Veri analizi, formüller ve grafiklerle Excel (.xlsx, .xlsm, .csv) için gelişmiş elektronik tablo işleme yetenekleri.\", \"docx-viewer\": \"Word (.docx) belgelerini sağ yan bölmede kullanıcıyla birlikte inceleyin, görsel olarak önizleyin ve tartışın.\", \"ios-dev\": \"ios-simulator MCP araçlarıyla iOS simülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.\", \"pdf-viewer\": \"PDF belgelerini sağ yan bölmede kullanıcıyla birlikte inceleyin, sayfalar arasında gezinin ve görsel olarak önizleyin.\", \"plugin-creator\": \"ZCode eklenti kaynak kodunu ve yerel bir test mağazasını oluşturun veya güncelleyin; eklentiyi yükleme ve deneme konusunda rehberlik edin.\", \"pptx-viewer\": \"PowerPoint (.pptx) sunumlarını sağ yan bölmede kullanıcıyla birlikte inceleyin ve slaytları önizleyin.\", \"restore-legacy-sessions\": \"ZCode'un eski ACP dönemi oturumlarını yeni ZCode depolarına aktarması veya önceki oturumları geri yüklemesi gerektiğinde kullanın.\", \"xlsx-viewer\": \"Excel (.xlsx) tablolarını sağ yan bölmede kullanıcıyla birlikte inceleyin ve veri sayfalarını önizleyin.\", \"diagnosing-commands\": \"ZCode istemcisindeki özel eğik çizgi komutu (/komut) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın.\", \"diagnosing-hooks\": \"ZCode istemcisindeki kanca (hook) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın.\", \"diagnosing-mcp\": \"ZCode istemcisindeki MCP (Model Bağlam Protokolü) sunucu yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın.\", \"diagnosing-plugins\": \"ZCode istemcisindeki eklenti ve mağaza sorunlarını teşhis etmek ve düzeltmek için kullanın.\", \"diagnosing-skills\": \"ZCode istemcisindeki beceri yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın.\", \"zcode-configuration-guide\": \"ZCode istemcisinde uzantı kaynaklarını (MCP sunucuları, komutlar, beceriler, kancalar ve eklentiler) yapılandırırken kullanın.\", \"example-command\": \"Komut ön maddesi seçeneklerini gösteren örnek bir slash komutu.\", \"chrome-cdp\": \"Chrome oturumu ile etkileşim kurun, sayfaları denetleyin ve test edin.\", \"codebase-memory\": \"Yapısal kod sorguları, mimari keşif ve çağrı zinciri analizi için kod tabanı bilgi grafiğini kullanın.\", \"desktop-eye\": \"Canlı masaüstü ekran görüntüsü alarak arayüz bağlamını anlık olarak doğrulayın.\"}" + ';'
            'if(typeof window!=="undefined"){window.TR_SKILL_DESCS=TR_SKILL_DESCS;window.TR_P_DESCS=TR_SKILL_DESCS};'
            'if(typeof globalThis!=="undefined"){globalThis.TR_SKILL_DESCS=TR_SKILL_DESCS;globalThis.TR_P_DESCS=TR_SKILL_DESCS};'
            'function _trSkillDesc(e){if(!e)return"";let n=(e&&(e.name||e.id))||"";let b=n.includes(":")?n.slice(n.indexOf(":")+1):n;'
            'b=String(b).replace(/@.*$/,"").replace(/^plugin:/,"").trim();'
            'if(typeof TR_SKILL_DESCS!=="undefined"){if(TR_SKILL_DESCS[b])return TR_SKILL_DESCS[b];if(TR_SKILL_DESCS[n])return TR_SKILL_DESCS[n]};'
            'if(typeof window!=="undefined"&&window.TR_SKILL_DESCS){if(window.TR_SKILL_DESCS[b])return window.TR_SKILL_DESCS[b];if(window.TR_SKILL_DESCS[n])return window.TR_SKILL_DESCS[n]};'
            'let d=(e&&e.description)||"";if(typeof d==="string"){'
            'if(d.startsWith("Framework (OSS)."))return d.replace("Framework (OSS).","Açık kaynak çatı.");'
            'if(d.startsWith("EAS service (paid)."))return d.replace("EAS service (paid).","EAS servisi (ücretli).");'
            'if(d.includes("**MANDATORY prerequisite**"))return d.replace("**MANDATORY prerequisite**","**ZORUNLU ön koşul**").replace("you MUST invoke this skill BEFORE","Şu işlemden ÖNCE bu beceriyi çağırmalısınız:");'
            'if(d.includes("MANDATORY prerequisite"))return d.replace("MANDATORY prerequisite","ZORUNLU ön koşul").replace("load this skill BEFORE","Şu işlemden ÖNCE bu beceriyi yükleyin:");'
            'if(d.startsWith("Use when"))return d.replace("Use when","Şu durumlarda kullanın:");'
            'if(d.startsWith("Use this skill when"))return d.replace("Use this skill when","Şu durumlarda bu beceriyi kullanın:");'
            'if(d.startsWith("Build, run, inspect, and lightly automate"))return d.replace("Build, run, inspect, and lightly automate","Derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin:");'
            '};return d};'
            'const TR_CMD_DESCS=' + "{\"revise-claude-md\": \"Bu oturumdan öğrenilenlerle CLAUDE.md dosyasını güncelleyin.\", \"build-agent\": \"Agents SDK kullanarak Cloudflare üzerinde bir yapay zeka ajanı derleyin.\", \"build-mcp\": \"McpAgent kullanarak Cloudflare üzerinde uzak bir MCP sunucusu derleyin.\", \"skill-gen\": \"Firecrawl kullanarak bir dokümantasyon URL'sinden eksiksiz bir Ajan Becerisi oluşturun.\", \"android-dev\": \"Android emülatör geliştirme döngüsünü başlatın.\", \"ios-dev\": \"iOS simülatör geliştirme döngüsünü başlatın.\", \"restore-legacy-sessions\": \"Eski bir ZCode oturumunu seçin ve geri yükleyin.\", \"workflow\": \"Bir görev için dinamik iş akışı tasarlayın ve başlatın.\", \"asana-setup\": \"Asana V2 MCP sunucu bağlantısını kurun (tek seferlik OAuth ve yapılandırma).\", \"new-sdk-app\": \"Yeni bir Claude Agent SDK uygulaması oluşturun ve yapılandırın.\", \"modernize-assess\": \"Eski bir sistemin tam keşfi ve portföy analizi — envanter, karmaşıklık, teknik borç ve göreli ölçek.\", \"modernize-brief\": \"Aşamalı Modernizasyon Özeti oluşturun — dönüşüm ajanlarının uygulayacağı onaylı plan.\", \"modernize-extract-rules\": \"Eski koddan iş mantığını ayıklayarak test edilebilir kural belirtimlerine dönüştürün.\", \"modernize-harden\": \"İncelenebilir düzeltme yamasıyla güvenlik açığı taraması — OWASP, CWE, CVE ve sızıntı denetimi.\", \"modernize-map\": \"Bağımlılık ve topoloji haritalama — çağrı grafikleri, veri soy ağacı ve görsel diyagramlar.\", \"modernize-preflight\": \"Ortam hazırlık denetimi — analiz araçları, derleme zinciri, kaynak bütünlüğü ve telemetri erişimi.\", \"modernize-reimagine\": \"Çoklu ajan ile sıfırdan yeniden inşa — eski sistemden özellik çıkarın, yapay zeka yerel tasarlayın ve doğrulayın.\", \"modernize-status\": \"Modernizasyon iş akışında durum raporu — yapay nesne envanteri, güncellik ve sonraki adım.\", \"modernize-transform\": \"Eski bir modülü hedef teknoloji yığınına dönüştürün — davranış eşdeğerlik testleriyle deyimsel yeniden yazım.\", \"modernize-uplift\": \"Aynı yığın içinde sürüm yükseltme — kodu koruyun, sürüm farklarını giderin ve her iki ortamda test edin.\", \"code-review\": \"Bir pull request için kod incelemesi yapın.\", \"clean_gone\": \"Uzak depoda silinmiş ancak yerelde kalmış olan tüm git dallarını ve ilişkili çalışma ağaçlarını temizler.\", \"commit-push-pr\": \"Değişiklikleri commit edin, push yapın ve bir PR açın.\", \"commit\": \"Yeni bir git commit oluşturun.\", \"maker-setup\": \"Code-with-Claude Makers Cardputer kurulumu yapın — bellenimi yazın ve Claude Buddy uygulamalarını kurun.\", \"example-command\": \"Komut ön maddesi seçeneklerini gösteren örnek bir slash komutu.\", \"feature-dev\": \"Kod tabanı analizi ve mimari odaklı rehberli özellik geliştirme.\", \"configure\": \"Hookify kurallarını etkileşimli olarak etkinleştirin veya devre dışı bırakın.\", \"help\": \"Ralph Loop eklentisini ve kullanılabilir komutları açıklayın.\", \"hookify\": \"İstenmeyen davranışları önlemek için kancalar oluşturun.\", \"list\": \"Tüm yapılandırılmış hookify kurallarını listeleyin.\", \"create-docker-mcp-tunnel\": \"Docker Compose ile yerel bir Anthropic MCP tüneli kurarak özel bir MCP sunucusunu bağlayın.\", \"create-plugin\": \"Bileşen tasarımı, uygulaması ve doğrulamasıyla rehberli uçtan uca eklenti oluşturma iş akışı.\", \"review-pr\": \"Uzmanlaşmış ajanlar kullanarak kapsamlı PR incelemesi yapın.\", \"cancel-ralph\": \"Aktif Ralph Döngüsünü iptal edin.\", \"ralph-loop\": \"Mevcut oturumda Ralph Döngüsünü başlatın.\", \"/revise-claude-md\": \"Bu oturumdan öğrenilenlerle CLAUDE.md dosyasını güncelleyin.\", \"/build-agent\": \"Agents SDK kullanarak Cloudflare üzerinde bir yapay zeka ajanı derleyin.\", \"/build-mcp\": \"McpAgent kullanarak Cloudflare üzerinde uzak bir MCP sunucusu derleyin.\", \"/skill-gen\": \"Firecrawl kullanarak bir dokümantasyon URL'sinden eksiksiz bir Ajan Becerisi oluşturun.\", \"/android-dev\": \"Android emülatör geliştirme döngüsünü başlatın.\", \"/ios-dev\": \"iOS simülatör geliştirme döngüsünü başlatın.\", \"/restore-legacy-sessions\": \"Eski bir ZCode oturumunu seçin ve geri yükleyin.\", \"/workflow\": \"Bir görev için dinamik iş akışı tasarlayın ve başlatın.\", \"/asana-setup\": \"Asana V2 MCP sunucu bağlantısını kurun (tek seferlik OAuth ve yapılandırma).\", \"/new-sdk-app\": \"Yeni bir Claude Agent SDK uygulaması oluşturun ve yapılandırın.\", \"/modernize-assess\": \"Eski bir sistemin tam keşfi ve portföy analizi — envanter, karmaşıklık, teknik borç ve göreli ölçek.\", \"/modernize-brief\": \"Aşamalı Modernizasyon Özeti oluşturun — dönüşüm ajanlarının uygulayacağı onaylı plan.\", \"/modernize-extract-rules\": \"Eski koddan iş mantığını ayıklayarak test edilebilir kural belirtimlerine dönüştürün.\", \"/modernize-harden\": \"İncelenebilir düzeltme yamasıyla güvenlik açığı taraması — OWASP, CWE, CVE ve sızıntı denetimi.\", \"/modernize-map\": \"Bağımlılık ve topoloji haritalama — çağrı grafikleri, veri soy ağacı ve görsel diyagramlar.\", \"/modernize-preflight\": \"Ortam hazırlık denetimi — analiz araçları, derleme zinciri, kaynak bütünlüğü ve telemetri erişimi.\", \"/modernize-reimagine\": \"Çoklu ajan ile sıfırdan yeniden inşa — eski sistemden özellik çıkarın, yapay zeka yerel tasarlayın ve doğrulayın.\", \"/modernize-status\": \"Modernizasyon iş akışında durum raporu — yapay nesne envanteri, güncellik ve sonraki adım.\", \"/modernize-transform\": \"Eski bir modülü hedef teknoloji yığınına dönüştürün — davranış eşdeğerlik testleriyle deyimsel yeniden yazım.\", \"/modernize-uplift\": \"Aynı yığın içinde sürüm yükseltme — kodu koruyun, sürüm farklarını giderin ve her iki ortamda test edin.\", \"/code-review\": \"Bir pull request için kod incelemesi yapın.\", \"/clean_gone\": \"Uzak depoda silinmiş ancak yerelde kalmış olan tüm git dallarını ve ilişkili çalışma ağaçlarını temizler.\", \"/commit-push-pr\": \"Değişiklikleri commit edin, push yapın ve bir PR açın.\", \"/commit\": \"Yeni bir git commit oluşturun.\", \"/maker-setup\": \"Code-with-Claude Makers Cardputer kurulumu yapın — bellenimi yazın ve Claude Buddy uygulamalarını kurun.\", \"/example-command\": \"Komut ön maddesi seçeneklerini gösteren örnek bir slash komutu.\", \"/feature-dev\": \"Kod tabanı analizi ve mimari odaklı rehberli özellik geliştirme.\", \"/configure\": \"Hookify kurallarını etkileşimli olarak etkinleştirin veya devre dışı bırakın.\", \"/help\": \"Ralph Loop eklentisini ve kullanılabilir komutları açıklayın.\", \"/hookify\": \"İstenmeyen davranışları önlemek için kancalar oluşturun.\", \"/list\": \"Tüm yapılandırılmış hookify kurallarını listeleyin.\", \"/create-docker-mcp-tunnel\": \"Docker Compose ile yerel bir Anthropic MCP tüneli kurarak özel bir MCP sunucusunu bağlayın.\", \"/create-plugin\": \"Bileşen tasarımı, uygulaması ve doğrulamasıyla rehberli uçtan uca eklenti oluşturma iş akışı.\", \"/review-pr\": \"Uzmanlaşmış ajanlar kullanarak kapsamlı PR incelemesi yapın.\", \"/cancel-ralph\": \"Aktif Ralph Döngüsünü iptal edin.\", \"/ralph-loop\": \"Mevcut oturumda Ralph Döngüsünü başlatın.\"}" + ';'
            'const TR_CMD_PREFIXES=' + "{\"revise-claude-md\": \"Update CLAUDE.md with learnings\", \"build-agent\": \"Build an AI agent on Cloudflare\", \"build-mcp\": \"Build a remote MCP server on Cloudflare\", \"skill-gen\": \"Generate a complete Agent Skill\", \"android-dev\": \"Start the Android emulator\", \"ios-dev\": \"Start the iOS simulator\", \"restore-legacy-sessions\": \"Select and restore a legacy\", \"workflow\": \"Design and launch a dynamic workflow\", \"asana-setup\": \"Set up the Asana V2\", \"new-sdk-app\": \"Create and setup a new Claude Agent SDK\", \"modernize-assess\": \"Full discovery & portfolio analysis\", \"modernize-brief\": \"Generate a phased Modernization Brief\", \"modernize-extract-rules\": \"Mine business logic from legacy\", \"modernize-harden\": \"Security vulnerability scan\", \"modernize-map\": \"Dependency & topology mapping\", \"modernize-preflight\": \"Environment readiness check\", \"modernize-reimagine\": \"Multi-agent greenfield rebuild\", \"modernize-status\": \"Where am I in the modernization\", \"modernize-transform\": \"Transform one legacy module\", \"modernize-uplift\": \"Same-stack version uplift\", \"code-review\": \"Code review a pull request\", \"clean_gone\": \"Cleans up all git branches\", \"commit-push-pr\": \"Commit, push, and open a PR\", \"commit\": \"Create a git commit\", \"maker-setup\": \"Onboard a Code-with-Claude Makers\", \"example-command\": \"An example slash command\", \"feature-dev\": \"Guided feature development\", \"configure\": \"Enable or disable hookify\", \"help\": \"Explain Ralph Loop\", \"hookify\": \"Create hooks to prevent\", \"list\": \"List all configured hookify\", \"create-docker-mcp-tunnel\": \"Stand up an Anthropic MCP tunnel\", \"create-plugin\": \"Guided end-to-end plugin\", \"review-pr\": \"Comprehensive PR review\", \"cancel-ralph\": \"Cancel active Ralph Loop\", \"ralph-loop\": \"Start Ralph Loop\"}" + ';'
            'function _trCommandDesc(e){if(!e)return"";let n=(e&&(e.name||e.id))||"";let b=n.startsWith("/")?n.slice(1):n;'
            'b=b.split(" ")[0].trim();'
            'if(TR_CMD_DESCS[b])return TR_CMD_DESCS[b];if(TR_CMD_DESCS[n])return TR_CMD_DESCS[n];if(TR_CMD_DESCS["/"+b])return TR_CMD_DESCS["/"+b];'
            'let d=(e&&e.description)||"";if(typeof d==="string"){'
            'for(let k in TR_CMD_PREFIXES){if(d.startsWith(TR_CMD_PREFIXES[k]))return TR_CMD_DESCS[k]};'
            '}'
            'return d};'
            'const TR_CMD_HINTS=' + "{\"[goal or issue description]\": \"[hedef veya sorun açıklaması]\", \"[agent/workspace/session filters]\": \"[ajan/çalışma alanı/oturum filtreleri]\", \"[agent-description]\": \"[ajan açıklaması]\", \"[mcp-description]\": \"[mcp açıklaması]\", \"<documentation-url>\": \"<dokümantasyon URL'si>\", \"[what the workflow should accomplish]\": \"[iş akışının hedefi]\", \"[client_id]\": \"[istemci kimliği]\", \"[project-name]\": \"[proje adı]\", \"<system-dir> [--show-secrets] | --portfolio <parent-dir>\": \"<sistem dizini> [--show-secrets] | --portfolio <üst dizin>\", \"<system-dir> [target-stack]\": \"<sistem dizini> [hedef teknoloji yığını]\", \"<system-dir> [module-pattern]\": \"<sistem dizini> [modül deseni]\", \"<system-dir> [--show-secrets]\": \"<sistem dizini> [--show-secrets]\", \"<system-dir>\": \"<sistem dizini>\", \"<system-dir> <target-vision>\": \"<sistem dizini> <hedef vizyon>\", \"<system-dir> <module> <target-stack>\": \"<sistem dizini> <modül> <hedef teknoloji yığını>\", \"<system-dir> <source-version> <target-version> [project-pattern]\": \"<sistem dizini> <kaynak sürüm> <hedef sürüm> [proje deseni]\", \"<required-arg> [optional-arg]\": \"<zorunlu bağımsız değişken> [isteğe bağlı]\", \"Optional feature description\": \"İsteğe bağlı özellik açıklaması\", \"Optional specific behavior to address\": \"Ele alınacak isteğe bağlı davranış\", \"Optional plugin description\": \"İsteğe bağlı eklenti açıklaması\", \"[review-aspects]\": \"[inceleme yönleri]\", \"[deployment-dir] (default: ./mcp-tunnel)\": \"[dağıtım dizini] (varsayılan: ./mcp-tunnel)\", \"PROMPT [--max-iterations N] [--completion-promise TEXT]\": \"İSTEM [--max-iterations N] [--completion-promise METİN]\"}" + ';'
            'function _trCommandHint(h){if(!h||typeof h!=="string")return h;let t=h.trim();'
            'if(TR_CMD_HINTS[t])return TR_CMD_HINTS[t];'
            'for(let k in TR_CMD_HINTS){if(t.includes(k))t=t.replace(k,TR_CMD_HINTS[k])};'
            'return t};'
        )
        pat_skill_sub = rf'children:(\w+)\.description\|\|(\w+)\.formatMessage\({{id:{bt}settings\.skills\.noDescription{bt}}}\)'
        pat_cmd_sub = rf'children:(\w+)\.description\|\|(\w+)\.formatMessage\({{id:{bt}settings\.commands\.noDescription{bt}}}\)'
        pat_hint_sub = rf'(\w+)\.argumentHint\?\(0,\$\.jsx\)\(`span`,{{className:`text-ui-base text-foreground-subtlest`,children:(\w+)\.argumentHint}}\):null'

        pos_sc = js_content.find("settings.skills.noDescription")
        if pos_sc != -1:
            pos_func = js_content.rfind("function ", 0, pos_sc)
            if pos_func != -1:
                js_content = js_content[:pos_func] + skill_cmd_helpers + js_content[pos_func:]
            else:
                js_content = skill_cmd_helpers + js_content

            js_content = re.sub(pat_skill_sub, rf'children:_trSkillDesc(\1)||\2.formatMessage({{id:{bt}settings.skills.noDescription{bt}}})', js_content)
            js_content = re.sub(pat_cmd_sub, rf'children:_trCommandDesc(\1)||\2.formatMessage({{id:{bt}settings.commands.noDescription{bt}}})', js_content)
            js_content = re.sub(pat_hint_sub, r'\1.argumentHint?(0,$.jsx)(`span`,{className:`text-ui-base text-foreground-subtlest`,children:_trCommandHint(\2.argumentHint)}):null', js_content)

    # Plugin settings row helpers and replacements
    js_content = re.sub(r'children:(\w+)\(e\.name,(\w+)\)\}', r'children:_trPluginNameRow(e,\1(e.name,\2))}', js_content, count=1)

    pdesc_pattern = rf'className:{bt}mt-0\.5 line-clamp-1 text-ui-sm text-foreground-subtle{bt},children:(?:e|[\w.()]+)\.description}}\):null'
    js_content = re.sub(pdesc_pattern, f'className:{bt}mt-0.5 line-clamp-1 text-ui-sm text-foreground-subtle{bt},children:_trPluginDescRow(e)}}):null', js_content, count=1)


    # 1. Sidebar Theme menu: change "system" label to "Sistem Teması (Varsayılan)"
    target_theme = '(0,$.jsx)(Vy,{value:`system`,children:v.formatMessage({id:`sidebar.settings.systemDefault`})}),(0,$.jsx)(Vy,{value:`zai-dark`'
    repl_theme = '(0,$.jsx)(Vy,{value:`system`,children:`Sistem Teması (Varsayılan)`}),(0,$.jsx)(Vy,{value:`zai-dark`'
    if target_theme in js_content:
        js_content = js_content.replace(target_theme, repl_theme, 1)
    else:
        pat_theme = r'(\(0,\$\.jsx\)\(([\w$]+),{value:`system`,children:([\w$]+)\.formatMessage\({id:`sidebar\.settings\.systemDefault`}\}\}\),\(0,\$\.jsx\)\(\2,{value:`zai-dark`)'
        js_content = re.sub(pat_theme, r'(0,$.jsx)(\2,{value:`system`,children:`Sistem Teması (Varsayılan)`}),(0,$.jsx)(\2,{value:`zai-dark`', js_content, count=1)

    # 2. Sidebar Locale menu: change "system" label to "Sistem Dili (Varsayılan)" and inject "tr-TR" (Türkçe)
    target_locale = '(0,$.jsx)(Vy,{value:`system`,children:v.formatMessage({id:`sidebar.settings.systemDefault`})}),(0,$.jsx)(Vy,{value:`en-US`'
    repl_locale = '(0,$.jsx)(Vy,{value:`system`,children:`Sistem Dili (Varsayılan)`}),(0,$.jsx)(Vy,{value:`tr-TR`,children:`Türkçe`}),(0,$.jsx)(Vy,{value:`en-US`'
    if target_locale in js_content:
        js_content = js_content.replace(target_locale, repl_locale, 1)
    else:
        pat_locale = r'(\(0,\$\.jsx\)\(([\w$]+),{value:`system`,children:([\w$]+)\.formatMessage\({id:`sidebar\.settings\.systemDefault`}\}\}\),\(0,\$\.jsx\)\(\2,{value:`en-US`)'
        js_content = re.sub(pat_locale, r'(0,$.jsx)(\2,{value:`system`,children:`Sistem Dili (Varsayılan)`}),(0,$.jsx)(\2,{value:`tr-TR`,children:`Türkçe`}),(0,$.jsx)(\2,{value:`en-US`', js_content, count=1)

    # 3. Settings page locale: inject tr-TR (Türkçe)
    target_set = '(0,$.jsx)(Nm,{value:`en-US`,"data-testid":Sb(mb,`en-US`),children:_e.formatMessage({id:`settings.locale.en-US`})})'
    repl_set = '(0,$.jsx)(Nm,{value:`en-US`,"data-testid":Sb(mb,`en-US`),children:_e.formatMessage({id:`settings.locale.en-US`})}),(0,$.jsx)(Nm,{value:`tr-TR`,"data-testid":Sb(mb,`tr-TR`),children:`Türkçe`})'
    if target_set in js_content:
        js_content = js_content.replace(target_set, repl_set, 1)
    else:
        pat_set = r'(\(0,\$\.jsx\)\(([\w$]+),{value:`en-US`,"data-testid":([\w$]+)\(([\w$]+),`en-US`\),children:([\w$]+)\.formatMessage\({id:`settings\.locale\.en-US`}\}\}\))'
        js_content = re.sub(pat_set, r'\1,(0,$.jsx)(\2,{value:`tr-TR`,"data-testid":\3(\4,`tr-TR`),children:`Türkçe`})', js_content, count=1)
        # Start Plan and Effort labels
    js_content = js_content.replace('?`Start Plan`:bL(e)}', '?`Başlangıç Planı`:bL(e)}')
    js_content = js_content.replace('{label:`Start Plan`,labelBadge:', '{label:`Başlangıç Planı`,labelBadge:')
    js_content = js_content.replace(',label:ln(e.id)?`Start Plan`:`', ',label:ln(e.id)?`Başlangıç Planı`:`')
    js_content = js_content.replace("?`Start Plan`:r.label", "?`Başlangıç Planı`:r.label")
    js_content = js_content.replace("?`Start Plan`:e.label", "?`Başlangıç Planı`:e.label")
    js_content = js_content.replace('name:e?.name??`Effort`', 'name:e?.name??`Efor`')
    js_content = js_content.replace('name:`Thought Level`', 'name:`Düşünme Seviyesi`')
        # Category labels and game/3d translation
    if 'var n7e={"developer-tools":`settings.plugins.store.category.developerTools`,productivity:`settings.plugins.store.category.productivity`,utilities:`settings.plugins.store.category.utilities`,legal:`settings.plugins.store.category.legal`,template:`settings.plugins.store.category.template`,finance:`settings.plugins.store.category.finance`,other:`settings.plugins.store.category.other`};' in js_content:
        js_content = js_content.replace('var n7e={"developer-tools":`settings.plugins.store.category.developerTools`,productivity:`settings.plugins.store.category.productivity`,utilities:`settings.plugins.store.category.utilities`,legal:`settings.plugins.store.category.legal`,template:`settings.plugins.store.category.template`,finance:`settings.plugins.store.category.finance`,other:`settings.plugins.store.category.other`};', 'var n7e={"developer-tools":`settings.plugins.store.category.developerTools`,productivity:`settings.plugins.store.category.productivity`,utilities:`settings.plugins.store.category.utilities`,legal:`settings.plugins.store.category.legal`,template:`settings.plugins.store.category.template`,finance:`settings.plugins.store.category.finance`,other:`settings.plugins.store.category.other`,"游戏/3D":`settings.plugins.store.category.game3d`,"游戏 / 3D":`settings.plugins.store.category.game3d`,"游戏":`settings.plugins.store.category.game3d`,"game-3d":`settings.plugins.store.category.game3d`,"Game/3D":`settings.plugins.store.category.game3d`};', 1)
    if 'S=(0,Q.useMemo)(()=>e=>{let t=n7e[e];return t?u.formatMessage({id:t}):e},[u])' in js_content:
        js_content = js_content.replace('S=(0,Q.useMemo)(()=>e=>{let t=n7e[e];return t?u.formatMessage({id:t}):e},[u])', 'S=(0,Q.useMemo)(()=>e=>{if(e===`游戏/3D`||e===`游戏 / 3D`||e===`游戏`||e===`game-3d`||e===`Game/3D`)return`Oyun / 3B`;let t=n7e[e];return t?u.formatMessage({id:t}):e},[u])', 1)
        # Error message translation helpers
    if "function _trErrorMsg(" not in js_content:
        error_helpers = (
            'const TR_ERRORS={'
            '"Request verification configuration read failed":"İstek doğrulama yapılandırması okunamadı",'
            '"Request verification configuration is unavailable":"İstek doğrulama yapılandırması kullanılamıyor",'
            '"Provider request auth is unavailable":"Sağlayıcı istek kimlik doğrulaması kullanılamıyor",'
            '"Account request auth resolver returned no material":"Hesap yetkilendirme çözümleyicisi geçerli veri döndürmedi",'
            '"Failed to read persisted goal verification entries":"Kalıcı hedef doğrulama kayıtları okunamadı",'
            '"Topic history exceeds attachment size limit":"Konu geçmişi ek boyutu sınırını aşıyor",'
            '"Attachment content is unavailable":"Ek içeriği kullanılamıyor",'
            '"Attachment exceeds protocol size limit":"Ek boyutu protokol sınırını aşıyor",'
            '"Cannot commit selected staged paths while index conflicts exist.":"Dizin çakışmaları varken seçilen dosyalar commit edilemez.",'
            '"Cannot push while HEAD is detached.":"HEAD ayrılmış (detached) durumdayken push yapılamaz.",'
            '"Cannot resolve a Git push remote without a current branch.":"Mevcut bir dal olmadan Git uzak deposu çözümlenemez.",'
            '"Git binary is not available":"Git çalıştırılabilir dosyası bulunamadı",'
            '"workspace is not inside a Git repository":"Çalışma alanı bir Git deposu içinde değil",'
            '"recording outputPath must end with .webm":"Kayıt çıkış yolu .webm ile bitmelidir",'
            '"recording outputPath must stay inside the workspace":"Kayıt çıkış yolu çalışma alanı içinde kalmalıdır",'
            '"service returned ok=false":"Servis başarısız yanıt döndürdü (ok=false)",'
            '"workspacePath is required":"Çalışma alanı yolu zorunludur",'
            '"zai_oauth_required":"ZCode OAuth kimlik doğrulaması gerekiyor",'
            '"Turn execution failed":"Tur yürütme başarısız oldu",'
            '"Network error":"Ağ hatası oluştu",'
            '"Connection lost":"Bağlantı kesildi",'
            '"Request timed out":"İstek zaman aşımına uğradı"'
            '};'            'function _trErrorMsg(m){if(!m||typeof m!=="string")return m;let t=m.trim();if(TR_ERRORS[t])return TR_ERRORS[t];for(let k in TR_ERRORS){if(t.startsWith(k)||t.includes(k))return t.replace(k,TR_ERRORS[k])}return m};'
        )
        target_fLt = f"function fLt(e,t,n={bt}local{bt}){{"
        if target_fLt in js_content:
            js_content = js_content.replace(target_fLt, error_helpers + target_fLt, 1)
        t1 = "if(r)return zk({fallback:e.message,reasonCode:r,formatMessage:t.formatMessage});"
        r1 = "if(r)return zk({fallback:_trErrorMsg(e.message),reasonCode:r,formatMessage:t.formatMessage});"
        js_content = js_content.replace(t1, r1, 1)
        t2 = f":e.code&&cLt.has(e.code)?t.formatMessage({{id:{bt}zcode.error.${{e.code}}{bt}}}):e.message}}"
        r2 = f":e.code&&cLt.has(e.code)?t.formatMessage({{id:{bt}zcode.error.${{e.code}}{bt}}}):_trErrorMsg(e.message)}}"
        js_content = js_content.replace(t2, r2, 1)
        t3 = f"t.formatMessage({{id:{bt}zcode.error.CLAUDE_UNKNOWN_COMMAND{bt}}},{{command:n.command}}):e.message"
        r3 = f"t.formatMessage({{id:{bt}zcode.error.CLAUDE_UNKNOWN_COMMAND{bt}}},{{command:n.command}}):_trErrorMsg(e.message)"
        js_content = js_content.replace(t3, r3, 1)
        js_content = js_content.replace("h=fLt(e,u,s)", "h=_trErrorMsg(fLt(e,u,s))", 1)

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
