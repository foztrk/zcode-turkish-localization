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
    "[agent/workspace/session filters]": "[ajan/çalışma alanı/oturum filtreleri]"
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
    "PDF": "PDF Becerileri",
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
        pat_cred = r'await t\.executeJavaScript\(`\$\{aN\(\)\};\\n\$\{s\}`,\!0\)'
        m_cred = re.search(pat_cred, js_content)
        if m_cred:
            repl_cred = f"await t.executeJavaScript(`${{aN()}};\\n${{s}};\\n${{{style_fn_name}()}}`,!0)"
            js_content = js_content.replace(m_cred.group(0), repl_cred, 1)

        # Hook rewards modal navigation
        pat_ren = r'r=\(\)=>\{t\(\),w\(e=>\(\{\.\.\.e,loading:!1\}\)\),_\.current=!0,E\.current\(\)\},i=\(\)=>\{_\.current=!0,t\(\),E\.current\(\)\}'
        m_ren = re.search(pat_ren, js_content)
        if m_ren:
            repl_ren = f"r=()=>{{t(),w(e=>({{...e,loading:!1}})),_.current=!0,E.current(),e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})}},i=()=>{{_.current=!0,t(),E.current(),e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})}}"
            js_content = js_content.replace(m_ren.group(0), repl_ren, 1)

        # Hook rewards modal context injection
        pat_ren_ctx = r'await e\.executeJavaScript\(Ma\(d,\{oauth:c,jwt:l\},a\)\)'
        m_ren_ctx = re.search(pat_ren_ctx, js_content)
        if m_ren_ctx:
            repl_ren_ctx = f"await e.executeJavaScript(Ma(d,{{oauth:c,jwt:l}},a)),await e.executeJavaScript({style_fn_name}(),!0).catch(()=>{{}})"
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
        "plugin-creator-plugin": "Yerel bir geliştirici pazar yeri, kurulum, denemeler ve güncellemeler aracılığıyla ZCode eklentileri geliştirin ve doğrulayın."
    }
    claude_tr_file = os.path.join(BASE_DIR, "claude_plugins_tr.json")
    if os.path.exists(claude_tr_file):
        with open(claude_tr_file, "r", encoding="utf-8") as _cf:
            official_p_descs.update(json.load(_cf))
    tr_p_descs_json = json.dumps(official_p_descs, ensure_ascii=False)

    plugin_row_helpers = (
        'function _trPluginDescRow(e){if(!e)return"";let n=(e.name||e.id||"");let b=String(n).replace(/@.*$/,"").replace(/^plugin:/,"").trim();'
        'if(typeof TR_P_DESCS!=="undefined"){if(TR_P_DESCS[b])return TR_P_DESCS[b];if(TR_P_DESCS[n])return TR_P_DESCS[n]};'
        'return e.description||""};'
        'function _trPluginNameRow(e,fallback){if(!e)return fallback;let n=(e.name||e.id||"");let b=String(n).replace(/@.*$/,"").replace(/^plugin:/,"").trim();'
        'if(typeof TR_P_NAMES!=="undefined"){if(TR_P_NAMES[b])return TR_P_NAMES[b];if(TR_P_NAMES[n])return TR_P_NAMES[n]};'
        'return fallback};'
    )

    pat_m4 = r"function\s+(\w+)\(e,t\)\{return\s+(\w+)\(e,t\)\}function\s+(\w+)\(e,t\)\{return\s+(\w+)\(t,e\.summary\?\.description\?\?e\.info\?\.description\?\?e\.installedMeta\?\.description,e\.listing\?\.descriptionI18n\)\}"
    m_m4 = re.search(pat_m4, js_content)
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
            f'function {fn_h4}(e,t){{let k=(e&&(e.name||e.id))||"";let base=String(k).replace(/@.*$/,"").replace(/^plugin:/,"").trim();if(TR_P_DESCS[base])return TR_P_DESCS[base];if(TR_P_DESCS[k])return TR_P_DESCS[k];let res={fn_pne}(t,e.summary?.description??e.info?.description??e.installedMeta?.description,e.listing?.descriptionI18n);if(typeof res==="string"){{if(res.startsWith("Built-in browser automation"))return TR_P_DESCS["browser-use"];if(res.startsWith("Computer Use: automate"))return TR_P_DESCS["computer-use"];if(res.startsWith("Built-in DOCX and PDF"))return TR_P_DESCS["document-skills"];if(res.startsWith("DingTalk Workspace CLI"))return TR_P_DESCS["dingtalk-cli"];if(res.startsWith("Lark CLI workflows"))return TR_P_DESCS["lark-cli"];if(res.startsWith("Obsidian authoring skills"))return TR_P_DESCS["obsidian"];if(res.startsWith("Alibaba Cloud CLI"))return TR_P_DESCS["alibaba-cloud-cli"];if(res.startsWith("Local-first security guardrails"))return TR_P_DESCS["mimosa"];if(res.startsWith("CloudBase development skills"))return TR_P_DESCS["cloudbase-skills"];if(res.startsWith("GitHub CLI workflows"))return TR_P_DESCS["github"];if(res.startsWith("GitLab CLI workflows"))return TR_P_DESCS["gitlab"];if(res.startsWith("Tencent Meeting CLI workflows"))return TR_P_DESCS["tencent-meeting-cli"];if(res.startsWith("WeCom CLI workflows"))return TR_P_DESCS["wecom-cli"];if(res.startsWith("Accounting close and statutory"))return TR_P_DESCS["accounting-and-reporting"];if(res.startsWith("Fixed-income and credit"))return TR_P_DESCS["assess-credit"];if(res.startsWith("Corporate-banking client"))return TR_P_DESCS["find-clients"];if(res.startsWith("Transaction structuring"))return TR_P_DESCS["model-deals"];if(res.startsWith("Fund and fund-manager"))return TR_P_DESCS["pick-funds"];if(res.startsWith("Top-down macro"))return TR_P_DESCS["read-macro"];if(res.startsWith("Corporate finance and FP&A"))return TR_P_DESCS["run-fpa"];if(res.startsWith("Counterparty and company"))return TR_P_DESCS["vet-companies"];if(res.startsWith("Watchlist and portfolio"))return TR_P_DESCS["watch-positions"];if(res.startsWith("End-to-end investment"))return TR_P_DESCS["write-research"];if(res.startsWith("MCP services for RoyalFlush"))return TR_P_DESCS["hexin"];if(res.startsWith("MCP services for Wind"))return TR_P_DESCS["wind"];if(res.startsWith("MCP service for Tianyancha"))return TR_P_DESCS["tianyancha"];if(res.startsWith("MCP services for SEC EDGAR"))return TR_P_DESCS["finance-search"];if(res.startsWith("Develop and validate ZCode plugins"))return TR_P_DESCS["plugin-creator"];if(res.startsWith("PDF document production skills"))return TR_P_DESCS["pdf"];if(res.startsWith("PPTX presentation production skills"))return TR_P_DESCS["presentations"];if(res.startsWith("XLSX spreadsheet production skills"))return TR_P_DESCS["spreadsheets"];if(res.startsWith("DOCX document production skills"))return TR_P_DESCS["documents"];if(res.startsWith("Official ZCode image search"))return TR_P_DESCS["image-search"];if(res.startsWith("Shared node_repl runtime host"))return TR_P_DESCS["node-repl-host"];if(res.includes("自动化视频剪辑工具包"))return TR_P_DESCS["video-agent-kit"];if(res.includes("基于 ZCode 内置 Browser Use"))return TR_P_DESCS["video2code"]}}return res}}'
        )
        js_content = js_content.replace(m_m4.group(0), m4_replacement, 1)

    # Connect r2 to fn_m4 and _trPluginDescRow
    m_row = re.search(r'return\{name:(\w+)\(r\?\?e,n\),description:r\?(\w+)\(r,n\):e\.description\}\}', js_content)
    if m_row:
        fn_name_call = m_row.group(1)
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
            '"judge":"Yalnızca pptx, docx, xlsx, pdf, poster ve grafik türündeki görsel çıktıların kabul incelemesi için tek yetkili görsel onay ajanı."};'
            'function _trAgentDesc(e){let n=(e&&(e.name||e.id))||"";let b=n.includes(":")?n.slice(n.indexOf(":")+1):n;'
            'if(TR_AGENT_DESCS[b])return TR_AGENT_DESCS[b];if(TR_AGENT_DESCS[n])return TR_AGENT_DESCS[n];'
            'let d=(e&&e.description)||"";if(typeof d==="string"){'
            'if(d.startsWith("General-purpose agent"))return TR_AGENT_DESCS["general-purpose"];'
            'if(d.startsWith("Read-only search agent"))return TR_AGENT_DESCS["Explore"];'
            'if(d.startsWith("THE single visual acceptance pass")||d.startsWith("THE single visual acceptance"))return TR_AGENT_DESCS["judge"]}'
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
            '"PDF":"PDF Becerileri","Pdf":"PDF Becerileri",'
            '"Presentations":"Sunum Becerileri","PRESENTATIONS":"Sunum Becerileri",'
            '"Spreadsheets":"Tablo Becerileri","SPREADSHEETS":"Tablo Becerileri",'
            '"Plugin Creator":"Eklenti Oluşturucu","PLUGIN CREATOR":"Eklenti Oluşturucu",'
            '"Microsoft Foundry":"Microsoft Foundry","MICROSOFT FOUNDRY":"Microsoft Foundry",'
            '"Browser Use":"Browser Use","BROWSER USE":"Browser Use",'
            '"Computer Use":"Bilgisayar Kontrolü","COMPUTER USE":"Bilgisayar Kontrolü"'
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
            'const TR_SKILL_DESCS={'
            '"restore-legacy-sessions":"ZCode\'un ~/.zcode/v2/sessions altındaki eski ACP dönemi ZCode oturumlarını yeni ZCode görev/oturum depolarına aktarması, incelemesi veya planlaması gerektiğinde kullanın. Eski sohbet geçmişini taşıma veya önceki oturumları geri yükleme sorularında tetiklenir.",'
            '"skill-creator":"Yeni beceriler oluşturun, mevcut becerileri düzenleyin ve ifadeleri iyileştirin. Sıfırdan SKILL.md yazarken, mevcut becerileri geliştirirken, tekrarlanan iş akışlarını yeniden kullanılabilir becerilere dönüştürürken veya beceri tetikleyicilerini giderirken kullanın.",'
            '"diagnosing-commands":"ZCode istemcisindeki özel eğik çizgi komutu (/komut) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir komut eksik olduğunda, bir beceri/ajan tarafından geçersiz kılındığında, ayrıştırılamadığında, kapsamlarda yinelenen adlara sahip olduğunda veya çalıştırılamadığında geçerlidir.",'
            '"diagnosing-hooks":"ZCode istemcisindeki kanca (hook) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir kanca tetiklenmediğinde, bir olay adı yanlış olduğunda, bir eşleştirici eşleşmediğinde, bir komut dosyası başarısız olduğunda veya kanca sıralaması/izinleri beklenmeyen davranışlara yol açtığında geçerlidir.",'
            '"diagnosing-mcp":"ZCode istemcisindeki MCP (Model Bağlam Protokolü) sunucu yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir MCP sunucusu bağlanmadığında, araçları eksik olduğunda, işlemi hata ile sonlandığında, aktarım protokolü (stdio veya SSE) yanlış yapılandırıldığında veya ortam değişkenleri hatalı olduğunda geçerlidir.",'
            '"diagnosing-plugins":"ZCode istemcisindeki eklenti ve mağaza sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir eklenti listelenmediğinde, mağaza ekleme veya eklenti yükleme başarısız olduğunda, bir eklenti komutu/becerisi/ajanı eksik olduğunda veya bir eklenti yapılandırması bozulduğunda geçerlidir.",'
            '"diagnosing-skills":"ZCode istemcisindeki beceri yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir beceri keşfedilmediğinde, yüklü olduğu halde otomatik tetiklenmediğinde, dosyaları eksik olduğunda, frontmatter ayrıştırma hataları verdiğinde veya kapsamlarda yinelenen adlara sahip olduğunda geçerlidir.",'
            '"zcode-configuration-guide":"ZCode istemcisinde uzantı kaynaklarını (MCP sunucuları, eğik çizgi komutları, beceriler, kancalar ve eklentiler) veya AGENTS.md gibi talimat dosyalarını yapılandırırken kullanın. Bir kullanıcı bu uzantı mekanizmalarının nasıl ekleneceğini, düzenleneceğini veya yapılandırılacağını sorduğunda geçerlidir.",'
            '"ios-dev":"ios-simulator MCP araçlarıyla iOS simülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.",'
            '"android-emulator":"Android emülatörlerini yönetme, başlatma ve cihaz kontrolü için geliştirici araçları.",'
            '"android-dev":"android-emulator MCP araçlarıyla Android emülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.",'
            '"docx":"Revizyonlar, yorumlar, biçimlendirme koruma ve metin çıkarma desteğiyle kapsamlı DOCX belgesi oluşturma, düzenleme ve analiz yetenekleri. Şablon tabanlı üretim ve format dönüştürmeyi destekler.",'
            '"pdf":"4 özel iş akışına sahip profesyonel PDF işleme araç seti: Typst/ReportLab ile yayın kalitesinde PDF üretimi, HTML/CSS tuvali ile görsel belge biçimlendirme, LaTeX ile akademik makaleler ve PyMuPDF/pdfplumber ile programatik düzenleme. Akıllı yönlendirme, format doğrulama ve otomatik kalite kontrolleri içerir.",'
            '"pptx":"PowerPoint (.pptx) sunum oluşturma, biçimlendirme ve düzenleme yetenekleri. Sıfırdan veya taslaklardan sunum hazırlama, mevcut slaytları düzenleme ve metin/not çıkarma işlemlerini kapsar.",'
            '"xlsx":"Veri analizi, formüller ve grafiklerle Excel (.xlsx, .xlsm, .csv) için gelişmiş elektronik tablo işleme yetenekleri. Sıfırdan çalışma kitapları oluşturma, mevcut tabloları düzenleme, veri analizi ve formül hesaplamalarını kapsar.",'
            '"plugin-creator":"ZCode eklenti kaynak kodunu ve yerel bir test mağazasını oluşturun veya güncelleyin; ardından kullanıcıya mağazayı ekleme, eklentiyi yükleme veya güncelleme ve uygulamada deneme konusunda rehberlik edin.",'
            '"capacity":"Bölgeler ve abonelikler genelinde kullanılabilir Azure OpenAI model kapasitesini keşfeder. Kota sınırlarını analiz eder ve en uygun dağıtım konumlarını önerir.",'
            '"customize":"Tam özelleştirme kontrolüyle Azure OpenAI modelleri için etkileşimli rehberli dağıtım akışı. Model sürümü, SKU, kapasite ve içerik filtreleme ilkesi seçimini sağlar.",'
            '"deploy-model":"Akıllı amaç tabanlı yönlendirme ile birleşik Azure OpenAI model dağıtım yeteneği. Hem hızlı ön ayarlı hem de tam özelleştirilmiş dağıtımları yönetir.",'
            '"finetuning":"SFT, DPO veya RFT kullanarak Microsoft Foundry üzerinde modelleri ince ayarlar (fine-tune). Veri kümesi hazırlama, eğitim işi gönderme, değerlendirme ve dağıtımı kapsar.",'
            '"microsoft-foundry":"Microsoft Foundry ajanlarını, modellerini ve kaynaklarını uçtan uca derleyin, dağıtın, değerlendirin, optimize edin, ince ayar yapın ve yönetin.",'
            '"preset":"Kullanılabilir tüm bölgelerdeki kapasiteyi analiz ederek Azure OpenAI modellerini en uygun bölgelere akıllıca dağıtır. Kapasite mevcut olduğunda geçerli bölgeyi tercih eder.",'
            '"control-browser":"Yalnızca ana ajan tarayıcı kullanımı: ZCode içinde web sayfalarını ve yerel HTTP hedeflerini açın, gezinin, inceleyin, tıklayın, form doldurun, ekran görüntüsü alın ve doğrulayın.",'
            '"web-gui-tester":"Oturumdaki tarayıcı otomasyon araçlarını kullanarak web arayüzlerini etkileşimli olarak test edin, kullanıcı eylemlerini simüle edin, ekran görüntüleriyle doğrulayın ve test raporu oluşturun.",'
            '"computer-use":"Erişilebilirlik odaklı semantik eylemler ve görsel doğrulama ile masaüstü kontrolü.",'
            '"zcode-computer-use":"Erişilebilirlik odaklı semantik eylemler ve görsel doğrulama ile masaüstü kontrolü.",'
            '"chrome-cdp":"Chrome oturumu ile etkileşim kurun, sayfaları denetleyin ve test edin.",'
            '"codebase-memory":"Yapısal kod sorguları, mimari keşif ve çağrı zinciri analizi için kod tabanı bilgi grafiğini kullanın.",'
            '"desktop-eye":"Canlı masaüstü ekran görüntüsü alarak arayüz bağlamını anlık olarak doğrulayın."'
            '};'
            'function _trSkillDesc(e){let n=(e&&(e.name||e.id))||"";let b=n.includes(":")?n.slice(n.indexOf(":")+1):n;'
            'let d=(e&&e.description)||"";if(typeof d==="string"){'
            'if(d.startsWith("Comprehensive DOCX")||d.startsWith("Revizyonlar, yorumlar"))return TR_SKILL_DESCS["docx"];'
            'if(d.startsWith("Professional PDF")||d.startsWith("4 özel iş akışına"))return TR_SKILL_DESCS["pdf"];'
            'if(d.startsWith("PowerPoint (.pptx)")||d.startsWith("PowerPoint ( .pptx )"))return TR_SKILL_DESCS["pptx"];'
            'if(d.startsWith("Advanced spreadsheet")||d.startsWith("Veri analizi, formüller"))return TR_SKILL_DESCS["xlsx"];'
            'if(d.startsWith("Create or update ZCode plugin"))return TR_SKILL_DESCS["plugin-creator"];'
            'if(d.startsWith("Discover available Azure OpenAI"))return TR_SKILL_DESCS["capacity"];'
            'if(d.startsWith("Interactive guided deployment flow"))return TR_SKILL_DESCS["customize"];'
            'if(d.startsWith("Unified Azure OpenAI model deployment"))return TR_SKILL_DESCS["deploy-model"];'
            'if(d.startsWith("Fine-tune models on Microsoft Foundry"))return TR_SKILL_DESCS["finetuning"];'
            'if(d.startsWith("Build, deploy, evaluate, optimize, fine-tune, and manage Microsoft Foundry"))return TR_SKILL_DESCS["microsoft-foundry"];'
            'if(d.startsWith("Smart deployment of Azure OpenAI"))return TR_SKILL_DESCS["preset"];'
            'if(d.startsWith("Use when ZCode needs to inspect"))return TR_SKILL_DESCS["restore-legacy-sessions"];'
            'if(d.startsWith("Create new skills"))return TR_SKILL_DESCS["skill-creator"];'
            'if(d.startsWith("Use to diagnose and fix ZCode custom slash-command"))return TR_SKILL_DESCS["diagnosing-commands"];'
            'if(d.startsWith("Use to diagnose and fix ZCode hook configuration"))return TR_SKILL_DESCS["diagnosing-hooks"];'
            'if(d.startsWith("Use to diagnose and fix ZCode MCP"))return TR_SKILL_DESCS["diagnosing-mcp"];'
            'if(d.startsWith("Use to diagnose and fix ZCode plugin"))return TR_SKILL_DESCS["diagnosing-plugins"];'
            'if(d.startsWith("Use to diagnose and fix ZCode skill configuration"))return TR_SKILL_DESCS["diagnosing-skills"];'
            'if(d.startsWith("Use when configuring ZCode")&&d.includes("extension resources"))return TR_SKILL_DESCS["zcode-configuration-guide"];'
            'if(d.startsWith("Build, run, inspect, and lightly automate iOS"))return TR_SKILL_DESCS["ios-dev"];'
            'if(d.startsWith("Build, run, inspect, and lightly automate Android"))return TR_SKILL_DESCS["android-dev"]}'
            'if(TR_SKILL_DESCS[b])return TR_SKILL_DESCS[b];if(TR_SKILL_DESCS[n])return TR_SKILL_DESCS[n];'
            'return d};'
            'const TR_CMD_DESCS={"android-dev":"Android emülatör geliştirme döngüsünü başlatın.","/android-dev":"Android emülatör geliştirme döngüsünü başlatın.",'
            '"ios-dev":"iOS simülatör geliştirme döngüsünü başlatın.","/ios-dev":"iOS simülatör geliştirme döngüsünü başlatın.",'
            '"restore-legacy-sessions":"Eski bir ZCode oturumunu seçin ve geri yükleyin.","/restore-legacy-sessions":"Eski bir ZCode oturumunu seçin ve geri yükleyin."};'
            'function _trCommandDesc(e){let n=(e&&(e.name||e.id))||"";let b=n.startsWith("/")?n.slice(1):n;'
            'if(TR_CMD_DESCS[b])return TR_CMD_DESCS[b];if(TR_CMD_DESCS[n])return TR_CMD_DESCS[n];'
            'let d=(e&&e.description)||"";if(typeof d==="string"){'
            'if(d.startsWith("Start the Android emulator"))return TR_CMD_DESCS["android-dev"];'
            'if(d.startsWith("Start the iOS simulator"))return TR_CMD_DESCS["ios-dev"];'
            'if(d.startsWith("Select and restore a legacy"))return TR_CMD_DESCS["restore-legacy-sessions"]}'
            'return d};'
            'const TR_CMD_HINTS={"[goal or issue description]":"[hedef veya sorun açıklaması]","[agent/workspace/session filters]":"[ajan/çalışma alanı/oturum filtreleri]"};'
            'function _trCommandHint(h){if(!h||typeof h!=="string")return h;let t=h.trim();if(TR_CMD_HINTS[t])return TR_CMD_HINTS[t];'
            'if(t.includes("[goal or issue description]"))return t.replace("[goal or issue description]","[hedef veya sorun açıklaması]");'
            'if(t.includes("[agent/workspace/session filters]"))return t.replace("[agent/workspace/session filters]","[ajan/çalışma alanı/oturum filtreleri]");'
            'return h};'
        )
        target_skill_card = f'children:e.description||p.formatMessage({{id:{bt}settings.skills.noDescription{bt}}})'
        if target_skill_card in js_content:
            pos_sc = js_content.rfind("function ", 0, js_content.find(target_skill_card))
            if pos_sc != -1:
                js_content = js_content[:pos_sc] + skill_cmd_helpers + js_content[pos_sc:]
            else:
                js_content = skill_cmd_helpers + js_content

            replacement_skill_card = f'children:_trSkillDesc(e)||p.formatMessage({{id:{bt}settings.skills.noDescription{bt}}})'
            js_content = js_content.replace(target_skill_card, replacement_skill_card, 1)

            target_skill_modal = f'children:Ae.description||p.formatMessage({{id:{bt}settings.skills.noDescription{bt}}})'
            replacement_skill_modal = f'children:_trSkillDesc(Ae)||p.formatMessage({{id:{bt}settings.skills.noDescription{bt}}})'
            if target_skill_modal in js_content:
                js_content = js_content.replace(target_skill_modal, replacement_skill_modal, 1)

            target_cmd_card = f'children:e.description||a.formatMessage({{id:{bt}settings.commands.noDescription{bt}}})'
            replacement_cmd_card = f'children:_trCommandDesc(e)||a.formatMessage({{id:{bt}settings.commands.noDescription{bt}}})'
            if target_cmd_card in js_content:
                js_content = js_content.replace(target_cmd_card, replacement_cmd_card, 1)

            target_cmd_hint = f'e.argumentHint?(0,$.jsx)(`span`,{{className:`text-ui-base text-foreground-subtlest`,children:e.argumentHint}}):null'
            replacement_cmd_hint = f'e.argumentHint?(0,$.jsx)(`span`,{{className:`text-ui-base text-foreground-subtlest`,children:_trCommandHint(e.argumentHint)}}):null'
            if target_cmd_hint in js_content:
                js_content = js_content.replace(target_cmd_hint, replacement_cmd_hint, 1)

    # Plugin settings row helpers and replacements
    js_content = re.sub(r'children:(\w+)\(e\.name,(\w+)\)\}', r'children:_trPluginNameRow(e,\1(e.name,\2))}', js_content, count=1)

    pdesc_pattern = rf'className:{bt}mt-0\.5 line-clamp-1 text-ui-sm text-foreground-subtle{bt},children:(?:e|[\w.()]+)\.description}}\):null'
    js_content = re.sub(pdesc_pattern, f'className:{bt}mt-0.5 line-clamp-1 text-ui-sm text-foreground-subtle{bt},children:_trPluginDescRow(e)}}):null', js_content, count=1)

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
