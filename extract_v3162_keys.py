# -*- coding: utf-8 -*-
import struct
import json
import re

ORIG_ASAR = r"C:\Program Files\ZCode\resources\app.asar.orig.v3162"

def parse_asar_header(f):
    header_raw = f.read(16)
    u1, str_len, u2, json_len = struct.unpack("<IIII", header_raw)
    json_bytes = f.read(json_len)
    header = json.loads(json_bytes.decode("utf-8"))
    base_offset = 8 + str_len
    return header, base_offset, str_len

with open(ORIG_ASAR, "rb") as f:
    header, base_offset, str_len = parse_asar_header(f)
    intl_node = header["files"]["out"]["files"]["renderer"]["files"]["assets"]["files"]["IntlProvider-C2IbGUkl.js"]
    f.seek(base_offset + int(intl_node["offset"]))
    intl_raw = f.read(int(intl_node["size"])).decode("utf-8")

# Extract h definition block
idx_map = intl_raw.find('_={"zh-CN":m,"en-US":h}')
idx_h = intl_raw.rfind("h={", 0, idx_map)
h_block = intl_raw[idx_h+2:idx_map]

# Parse key-values
# Pattern: "key":`val` or "key":"val"
pattern = re.compile(r'"([a-zA-Z0-9_\.\-]+)"\s*:\s*(?:`([^`]*)`|"([^"]*)")')
matches = pattern.findall(h_block)

en_dict = {}
for m in matches:
    key = m[0]
    val = m[1] if m[1] != "" else m[2]
    en_dict[key] = val

print(f"Total keys extracted from v3.16.2 en-US: {len(en_dict)}")

# Compare with existing tr_dictionary_zcode.json
with open(r"C:\Users\Work-D\zcode-turkish-localization\tr_dictionary_zcode.json", "r", encoding="utf-8") as f_tr:
    tr_dict = json.load(f_tr)

print(f"Current TR dictionary keys: {len(tr_dict)}")

new_keys = {}
for k, v in en_dict.items():
    if k not in tr_dict:
        new_keys[k] = v

print(f"NEW KEYS in v3.16.2: {len(new_keys)}")

with open(r"C:\Users\Work-D\zcode-turkish-localization\v3162_new_keys.json", "w", encoding="utf-8") as out_f:
    json.dump(new_keys, out_f, ensure_ascii=False, indent=2)

for i, (k, v) in enumerate(list(new_keys.items())[:20]):
    print(f"  {k} -> {v}")
