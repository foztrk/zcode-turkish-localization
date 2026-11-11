# -*- coding: utf-8 -*-
import json
import os
import sys

sys.path.insert(0, r"C:\Users\Work-D\zcode-turkish-localization")
from v3180_translations_part1 import V3180_TRANSLATIONS
from v3180_translations_part2 import V3180_TRANSLATIONS_PART2

BASE_DIR = r"C:\Users\Work-D\zcode-turkish-localization"
DICT_PATH = os.path.join(BASE_DIR, "tr_dictionary_zcode.json")
TS_PATH = os.path.join(BASE_DIR, "tr-TR.ts")

# 1. Load existing dictionary
with open(DICT_PATH, "r", encoding="utf-8") as f:
    tr_dict = json.load(f)

print(f"Mevcut anahtar sayısı: {len(tr_dict)}")

# 2. Merge v3180 translations
v3180_merged = {}
v3180_merged.update(V3180_TRANSLATIONS)
v3180_merged.update(V3180_TRANSLATIONS_PART2)

added_count = 0
for k, v in v3180_merged.items():
    if k not in tr_dict:
        added_count += 1
    tr_dict[k] = v

print(f"Eklenen yeni anahtar sayısı: {added_count}")
print(f"Yeni toplam anahtar sayısı: {len(tr_dict)}")

# 3. Save JSON
with open(DICT_PATH, "w", encoding="utf-8") as f:
    json.dump(tr_dict, f, ensure_ascii=False, indent=2)

# 4. Save TypeScript file
ts_content = "export default " + json.dumps(tr_dict, ensure_ascii=False, indent=2) + ";\n"
with open(TS_PATH, "w", encoding="utf-8") as f:
    f.write(ts_content)

print(f"[OK] tr_dictionary_zcode.json ve tr-TR.ts başarıyla güncellendi ({len(tr_dict)} anahtar)!")
