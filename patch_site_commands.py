# -*- coding: utf-8 -*-
import os, sys, re

sys.stdout.reconfigure(encoding="utf-8")

PACKAGES_DIR = r"C:\Program Files\ZCode\resources\glm\packages"

SITE_COMMANDS_TR = {
    "site-badge.md": {
        "description": "Bağlı ZCode Sites sitesinde ZCode rozetini gizleyin veya gösterin.",
        "argument-hint": "gizle | göster"
    },
    "site-deploy.md": {
        "description": "Bu projeyi ZCode Sites'a dağıtın veya bağlı siteyi yeniden dağıtın.",
        "argument-hint": "[site id veya notlar]"
    },
    "site-logs.md": {
        "description": "Bir ZCode Sites dağıtımının günlüklerini gösterin ve olası hataları açıklayın.",
        "argument-hint": "[dağıtım id]"
    },
    "site-offline.md": {
        "description": "Bağlı ZCode Sites sitesini çevrimdışı duruma getirin.",
        "argument-hint": "[site id]"
    },
    "site-online.md": {
        "description": "Bağlı ZCode Sites sitesini tekrar çevrimiçi duruma getirin.",
        "argument-hint": "[site id]"
    },
    "site-status.md": {
        "description": "Bu projeye bağlı ZCode Sites sitesini gösterin.",
        "argument-hint": "[site id]"
    },
    "site-usage.md": {
        "description": "ZCode Sites kullanımını ve plan sınırlarını gösterin.",
        "argument-hint": ""
    }
}

def patch_site_commands():
    cmds_dir = os.path.join(PACKAGES_DIR, "zcode-site-plugin", "commands")
    if not os.path.exists(cmds_dir):
        print(f"Uyarı: {cmds_dir} bulunamadı!")
        return

    for fname, meta in SITE_COMMANDS_TR.items():
        fpath = os.path.join(cmds_dir, fname)
        if not os.path.exists(fpath):
            continue

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Frontmatter replace
        for k, v in meta.items():
            if not v and k == "argument-hint":
                content = re.sub(r'argument-hint:\s*".*?"', '', content)
                content = re.sub(r'argument-hint:\s*[^\n]+', '', content)
            elif v:
                content = re.sub(rf'{k}:\s*".*?"', f'{k}: "{v}"', content)
                content = re.sub(rf'{k}:\s*[^\n]+', f'{k}: "{v}"', content, count=1)

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Güncellendi: {fname} -> {meta['description']}")

if __name__ == "__main__":
    patch_site_commands()
    print("ZCode Sites komutları başarıyla Türkçeleştirildi!")
