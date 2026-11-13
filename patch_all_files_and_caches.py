# -*- coding: utf-8 -*-
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = r"C:\Users\Work-D\zcode-turkish-localization"

with open(os.path.join(BASE_DIR, "store_names_tr.json"), "r", encoding="utf-8") as f:
    NAMES_TR = json.load(f)

with open(os.path.join(BASE_DIR, "claude_plugins_tr.json"), "r", encoding="utf-8") as f:
    DESCS_TR = json.load(f)

def get_tr_desc(pid, raw_desc):
    if pid in DESCS_TR:
        return DESCS_TR[pid]
    if raw_desc in DESCS_TR:
        return DESCS_TR[raw_desc]
    if raw_desc and isinstance(raw_desc, str):
        t = raw_desc.strip()
        if t in DESCS_TR:
            return DESCS_TR[t]
        for k, v in DESCS_TR.items():
            if len(t) > 20 and len(k) > 20 and (t.startswith(k) or k.startswith(t)):
                return v
    return raw_desc

def patch_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False

    changed = False

    # 1. Marketplace dosyası mı (plugins veya manifest.plugins listesi)?
    plugins_list = None
    if isinstance(data, dict):
        if "plugins" in data and isinstance(data["plugins"], list):
            plugins_list = data["plugins"]
        elif "manifest" in data and isinstance(data["manifest"], dict) and "plugins" in data["manifest"] and isinstance(data["manifest"]["plugins"], list):
            plugins_list = data["manifest"]["plugins"]

    if plugins_list is not None:
        for p in plugins_list:
            pid = p.get("id") or p.get("name") or ""
            # Ad güncelle
            tr_name = NAMES_TR.get(pid) or NAMES_TR.get(p.get("name", "")) or NAMES_TR.get(p.get("displayName", ""))
            if tr_name:
                if p.get("displayName") != tr_name:
                    p["displayName"] = tr_name
                    changed = True
                if "displayName_i18n" in p and isinstance(p["displayName_i18n"], dict):
                    p["displayName_i18n"]["tr"] = tr_name
                    p["displayName_i18n"]["zh-CN"] = tr_name
                    changed = True

            # Açıklama güncelle
            cur_desc = p.get("description", "")
            tr_desc = get_tr_desc(pid, cur_desc)
            if tr_desc and tr_desc != cur_desc:
                p["description"] = tr_desc
                changed = True
                
            # i18n objesi varsa
            for i18n_key in ["descriptionI18n", "description_i18n"]:
                if i18n_key in p and isinstance(p[i18n_key], dict):
                    if tr_desc:
                        p[i18n_key]["tr-TR"] = tr_desc
                        p[i18n_key]["tr"] = tr_desc
                        p[i18n_key]["en-US"] = tr_desc
                        p[i18n_key]["en"] = tr_desc
                        p[i18n_key]["zh-CN"] = tr_desc
                        changed = True

    # 2. Tekil plugin.json veya package.json mı?
    elif isinstance(data, dict):
        pid = data.get("name") or data.get("id") or ""
        clean_pid = pid.replace("-plugin", "").replace("@zcode/", "")
        tr_name = NAMES_TR.get(clean_pid) or NAMES_TR.get(pid) or NAMES_TR.get(data.get("displayName", ""))
        if tr_name:
            if "displayName" in data and data.get("displayName") != tr_name:
                data["displayName"] = tr_name
                changed = True
            elif "name" in data and data.get("name") != tr_name and not filepath.endswith("package.json"):
                # package.json içinde name paket tanımlayıcısı olduğu için değiştirilmez, displayName veya plugin.json güncellenir
                pass
        
        cur_desc = data.get("description", "")
        tr_desc = get_tr_desc(clean_pid, cur_desc) or get_tr_desc(pid, cur_desc)
        if tr_desc and tr_desc != cur_desc:
            data["description"] = tr_desc
            changed = True

        for i18n_key in ["descriptionI18n", "description_i18n"]:
            if i18n_key in data and isinstance(data[i18n_key], dict):
                if tr_desc:
                    data[i18n_key]["tr-TR"] = tr_desc
                    data[i18n_key]["tr"] = tr_desc
                    data[i18n_key]["en-US"] = tr_desc
                    data[i18n_key]["en"] = tr_desc
                    data[i18n_key]["zh-CN"] = tr_desc
                    changed = True

    if changed:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    return False

def main():
    target_dirs = [
        r"C:\Program Files\ZCode\resources\glm\packages",
        os.path.expanduser(r"~/.zcode/cli/plugins/cache"),
        os.path.expanduser(r"~/.zcode/cli/plugins/marketplaces")
    ]

    total_patched = 0
    for tdir in target_dirs:
        if not os.path.exists(tdir):
            continue
        for root, _, files in os.walk(tdir):
            for f in files:
                if f in ["plugin.json", "package.json", "marketplace.json", "cdn-marketplace.json", "bundled-marketplace.json"]:
                    full_p = os.path.join(root, f)
                    if patch_json_file(full_p):
                        total_patched += 1
                        print(f"Patched: {full_p}")

    print(f"\nToplam {total_patched} JSON dosyası başarıyla Türkçeleştirildi!")

if __name__ == "__main__":
    main()
