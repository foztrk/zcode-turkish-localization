# -*- coding: utf-8 -*-
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZCODE_RESOURCES = r"C:\Program Files\ZCode\resources"
ORIG_ASAR = (
    os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3171")
    if os.path.exists(os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3171"))
    else os.path.join(BASE_DIR, "app.asar.orig.v3171")
    if os.path.exists(os.path.join(BASE_DIR, "app.asar.orig.v3171"))
    else os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3163")
    if os.path.exists(os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3163"))
    else os.path.join(BASE_DIR, "app.asar.orig.v3163")
    if os.path.exists(os.path.join(BASE_DIR, "app.asar.orig.v3163"))
    else os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3162")
    if os.path.exists(os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3162"))
    else os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3153")
    if os.path.exists(os.path.join(ZCODE_RESOURCES, "app.asar.orig.v3153"))
    else os.path.join(ZCODE_RESOURCES, "app.asar")
)
PATCHED_ASAR = os.path.join(BASE_DIR, "app.asar.patched")
DICT_PATH = os.path.join(BASE_DIR, "tr_dictionary_zcode.json")

MENU_TR_V2 = {
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

def parse_asar_header(f):
    header_raw = f.read(16)
    if len(header_raw) < 16:
        raise ValueError("Geçersiz ASAR başlığı")
    u1, str_len, u2, json_len = struct.unpack("<IIII", header_raw)
    json_bytes = f.read(json_len)
    header = json.loads(json_bytes.decode("utf-8"))
    base_offset = 8 + str_len
    return header, base_offset, str_len

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
        raise FileNotFoundError("IntlProvider bundle bulunamadı!")
    if not styles_file:
        raise FileNotFoundError("Styles bundle bulunamadı!")
    if not usage_parts_file:
        raise FileNotFoundError("usageStatsUiParts bundle bulunamadı!")
    if not menu_file:
        raise FileNotFoundError("Menu chunk bundle bulunamadı!")

    return {
        "intl": ["out", "renderer", "assets", intl_file],
        "styles": ["out", "renderer", "assets", styles_file],
        "usage_parts": ["out", "renderer", "assets", usage_parts_file],
        "menu": ["out", "main", menu_file],
        "main": ["out", "main", "index.js"],
        "html": ["out", "renderer", "index.html"],
        "resource_html": ["out", "renderer", "resource-manager.html"],
    }

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

def patch_menu(js_content):
    m = re.search(r'(\w+)=(\{"zh-CN":\{"titleBar\.menu\.file":.*?\}\});function\s+', js_content)
    if m:
        var_name = m.group(1)
        json_str = m.group(2)
        kp_data = json.loads(json_str)
        for k, v in MENU_TR_V2.items():
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
        for k, v in MENU_TR_V2.items():
            if "en-US" in kp_data:
                kp_data["en-US"][k] = v
            if "zh-CN" in kp_data:
                kp_data["zh-CN"][k] = v
        new_kp_json = json.dumps(kp_data, ensure_ascii=False)
        return js_content[:pos_kp + 3] + new_kp_json + js_content[pos_end_kp + 1:]

    # Fallback to pp menu
    pos_pp = js_content.find("pp={")
    if pos_pp != -1:
        pos_by = js_content.find("function by(", pos_pp)
        if pos_by != -1:
            pp_str = js_content[pos_pp + 3:pos_by].strip().rstrip(";")
            try:
                pp_data = json.loads(pp_str)
                if "en-US" in pp_data:
                    for k, v in MENU_TR_V2.items():
                        pp_data["en-US"][k] = v
                new_pp_json = json.dumps(pp_data, ensure_ascii=False)
                return js_content[:pos_pp] + f"pp={new_pp_json};" + js_content[pos_by:]
            except Exception:
                pass
    return js_content

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
function _trPluginDesc(id,raw){{let cid=(id&&String(id).replace(/@.*$/,"").replace(/^plugin:/,"").trim())||"";if(cid==="ruic-card"||(raw&&typeof raw==="string"&&raw.toLowerCase().includes("holographic")))return "Katmanlı sanat eserleriyle holografik koleksiyon kartı üreticisi: Blender ve Three.js ile 3D paralaks kart web sitesi ve düzenlenebilir card.blend projesi üretir.";if(id&&TR_SKILL_DESCS[id])return TR_SKILL_DESCS[id];if(cid&&TR_SKILL_DESCS[cid])return TR_SKILL_DESCS[cid];if(raw&&typeof raw==="string"){{let t=raw.trim();if(TR_SKILL_DESCS[t])return TR_SKILL_DESCS[t];for(let k in TR_SKILL_DESCS){{if(t.length>15&&k.length>15&&(t.startsWith(k)||k.startsWith(t)||t.includes(k)||k.includes(t.slice(0,25))))return TR_SKILL_DESCS[k]}}}};return raw}};
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
    repl_o3 = '''function o3(e,t){let n=t?.startsWith(`zh`)??!1,r=n?e.cn:e.en,i=n?e.en:e.cn;let res=r?.trim()||i?.trim()||(typeof e===`string`?e.trim():``)||``;if(typeof res===`string`&&res){let s=res.toLowerCase();if(s.includes(`summarize commits`)||s.includes(`previous workday`)||s.includes(`stand-up-ready`)||s.includes(`standup-ready`))return `Önceki iş gününden bu yana commit'leri, modül değişikliklerini, CI durumunu ve takip edilecekleri özetleyin; engelleri ve sonraki adımları içeren en fazla beş maddelik toplantı özeti hazırlayın.`;if(s.includes(`inspect code changes`)||s.includes(`last 24 hours`)||s.includes(`authorization bypasses`)||s.includes(`runtime failures`))return `Son 24 saatteki kod değişikliklerini çalışma zamanı hataları, veri kaybı, yetkilendirme açıkları, kaynak sızıntıları veya eksik geri alma senaryoları açısından inceleyin.`;if(s.includes(`organize prs`)||s.includes(`merged this week`)||s.includes(`breaking changes`))return `Bu hafta birleştirilen PR ve commit'leri Özellikler, Düzeltmeler, Deneyim ve Mühendislik iyileştirmeleri olarak düzenleyin; kritik değişiklikleri ve kalan takip maddelerini vurgulayın.`;if(s.includes(`compare code`)||s.includes(`documentation changes`)||s.includes(`last seven days`)||s.includes(`public interfaces`))return `Son yedi günün kod, yapılandırma, API ve dokümantasyon değişikliklerini karşılaştırın. Genel arayüzlerin veya sistem davranışının belgelenmeden değiştiği durumları tespit edin.`;if(s.includes(`daily standup`)||s.includes(`standup summary`))return `Sabah Geliştirici Özeti`;if(s.includes(`risk scan`))return `Risk Taraması`;if(s.includes(`release summary`))return `Sürüm Özeti`;if(s.includes(`docs sync`)||s.includes(`sync check`))return `Belge Senkronizasyon Kontrolü`}if(typeof _trTemplateText===`function`)return _trTemplateText(res);return res}'''
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

    # 5.1 Beceriler ve Komutlar Listesi ve Detayı Kancaları
    target_skill_list = '(0,$.jsx)(`div`,{className:`mt-0.5 truncate text-ui-sm text-foreground-subtle`,children:e.description||g.formatMessage({id:`settings.skills.noDescription`})})'
    repl_skill_list = '(0,$.jsx)(`div`,{className:`mt-0.5 truncate text-ui-sm text-foreground-subtle`,children:(_trSkillDesc(e)||e.description)||g.formatMessage({id:`settings.skills.noDescription`})})'
    js_content = js_content.replace(target_skill_list, repl_skill_list, 1)

    target_skill_detail = '(0,$.jsx)(`div`,{className:`max-h-40 overflow-auto whitespace-pre-wrap text-ui-base/relaxed text-foreground-subtle`,children:ke.description||g.formatMessage({id:`settings.skills.noDescription`})})'
    repl_skill_detail = '(0,$.jsx)(`div`,{className:`max-h-40 overflow-auto whitespace-pre-wrap text-ui-base/relaxed text-foreground-subtle`,children:(_trSkillDesc(ke)||ke.description)||g.formatMessage({id:`settings.skills.noDescription`})})'
    js_content = js_content.replace(target_skill_detail, repl_skill_detail, 1)

    target_command_list = '(0,$.jsx)(`p`,{className:`mt-0.5 line-clamp-2 text-ui-sm text-foreground-subtle`,children:e.description||a.formatMessage({id:`settings.commands.noDescription`})})'
    repl_command_list = '(0,$.jsx)(`p`,{className:`mt-0.5 line-clamp-2 text-ui-sm text-foreground-subtle`,children:(_trCommandDesc(e)||e.description)||a.formatMessage({id:`settings.commands.noDescription`})})'
    js_content = js_content.replace(target_command_list, repl_command_list, 1)

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

def patch_html(html_content):
    if "zcode-tr-dom-patch" in html_content:
        return html_content

    dom_script = r"""<script id="zcode-tr-dom-patch">
(function() {
  const DOM_MAP = {
    "Daily standup summary": "Sabah Geliştirici Özeti",
    "Summarize commits, module changes, CI status, and follow-ups since the previous workday, then produce no more than five stand-up-ready highlights with blockers and next steps.": "Önceki iş gününden bu yana commit'leri, modül değişikliklerini, CI durumunu ve takip edilecekleri özetleyin; engelleri ve sonraki adımları içeren en fazla beş maddelik toplantı özeti hazırlayın.",
    "Risk scan": "Risk Taraması",
    "Inspect code changes from the last 24 hours for high-confidence risks involving runtime failures, data loss, authorization bypasses, resource leaks, or missing rollbacks.": "Son 24 saatteki kod değişikliklerini çalışma zamanı hataları, veri kaybı, yetkilendirme açıkları, kaynak sızıntıları veya eksik geri alma senaryoları açısından inceleyin.",
    "Release summary": "Sürüm Özeti",
    "Organize PRs and commits merged this week into Features, Fixes, Experience improvements, and Engineering improvements, then highlight breaking changes and remaining follow-ups.": "Bu hafta birleştirilen PR ve commit'leri Özellikler, Düzeltmeler, Deneyim ve Mühendislik iyileştirmeleri olarak düzenleyin; kritik değişiklikleri ve kalan takip maddelerini vurgulayın.",
    "Docs sync check": "Belge Senkronizasyon Kontrolü",
    "Compare code, configuration, API, and documentation changes from the last seven days. Identify high-confidence cases where public interfaces or behavior changed without documentation updates.": "Son yedi günün kod, yapılandırma, API ve dokümantasyon değişikliklerini karşılaştırın. Genel arayüzlerin veya sistem davranışının belgelenmeden değiştiği durumları tespit edin.",
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
    "Document Skills": "Belge Becerileri",
    "Documents": "Belge Becerileri",
    "DOCUMENTS": "Belge Becerileri",
        "Presentations": "Sunum Becerileri",
    "PRESENTATIONS": "Sunum Becerileri",
    "Spreadsheets": "Tablo Becerileri",
    "SPREADSHEETS": "Tablo Becerileri",
    "Plugin Creator": "Eklenti Oluşturucu",
    "PLUGIN CREATOR": "Eklenti Oluşturucu",
    "Microsoft Foundry": "Microsoft Foundry",
    "MICROSOFT FOUNDRY": "Microsoft Foundry",
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


def rebuild_asar(source_asar_path, dest_asar_path, modified_files_map):
    print("Rebuilding ASAR...")
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

        print(f"ASAR rebuilt successfully: {dest_asar_path} ({os.path.getsize(dest_asar_path)} bytes)")

def main():
    print("Reading original ASAR and dictionary...")
    with open(DICT_PATH, "r", encoding="utf-8") as f:
        tr_dict = json.load(f)

    with open(ORIG_ASAR, "rb") as f_src:
        header, base_offset, str_len = parse_asar_header(f_src)
        targets = find_target_paths(header, f_src, base_offset)
        print("Dynamic targets identified:")
        for k, v in targets.items():
            print(f"  {k}: {'/'.join(v)}")

        intl_orig = extract_file(f_src, find_node(header, targets["intl"]), base_offset).decode("utf-8")
        styles_orig = extract_file(f_src, find_node(header, targets["styles"]), base_offset).decode("utf-8")
        usage_orig = extract_file(f_src, find_node(header, targets["usage_parts"]), base_offset).decode("utf-8")
        menu_orig = extract_file(f_src, find_node(header, targets["menu"]), base_offset).decode("utf-8")
        main_orig = extract_file(f_src, find_node(header, targets["main"]), base_offset).decode("utf-8")
        html_orig = extract_file(f_src, find_node(header, targets["html"]), base_offset).decode("utf-8")
        resource_html_orig = extract_file(f_src, find_node(header, targets["resource_html"]), base_offset).decode("utf-8")

    print("Applying patches in memory...")
    intl_patched = patch_intl(intl_orig, tr_dict)
    styles_patched = patch_styles(styles_orig)
    usage_patched = patch_usage_parts(usage_orig)
    menu_patched = patch_menu(menu_orig)
    main_patched = patch_main(main_orig)
    html_patched = patch_html(html_orig)
    resource_html_patched = patch_resource_html(resource_html_orig)

    modified_files = {
        "/".join(targets["intl"]): intl_patched.encode("utf-8"),
        "/".join(targets["styles"]): styles_patched.encode("utf-8"),
        "/".join(targets["usage_parts"]): usage_patched.encode("utf-8"),
        "/".join(targets["menu"]): menu_patched.encode("utf-8"),
        "/".join(targets["main"]): main_patched.encode("utf-8"),
        "/".join(targets["html"]): html_patched.encode("utf-8"),
        "/".join(targets["resource_html"]): resource_html_patched.encode("utf-8"),
    }

    rebuild_asar(ORIG_ASAR, PATCHED_ASAR, modified_files)

    print("\nVerifying rebuilt ASAR by reading back modified files...")
    with open(PATCHED_ASAR, "rb") as f_check:
        h_check, b_check, s_check = parse_asar_header(f_check)
        for k, v in targets.items():
            p_str = "/".join(v)
            node = find_node(h_check, v)
            assert node is not None, f"Node {p_str} not found in check!"
            data = extract_file(f_check, node, b_check)
            assert len(data) == len(modified_files[p_str]), f"Size mismatch for {p_str}"
            print(f"  Verified {k}: {len(data)} bytes")

    print("\n>>> REBUILD AND INTEGRITY VERIFICATION 100% SUCCESSFUL! <<<")

if __name__ == "__main__":
    main()
