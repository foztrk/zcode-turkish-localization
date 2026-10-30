# -*- coding: utf-8 -*-
import json, os, struct, subprocess, tempfile

def test_patched_js_syntax():
    base_dir = r"C:\Users\Work-D\zcode-turkish-localization"
    patched_asar = os.path.join(base_dir, "app.asar.patched")

    with open(patched_asar, "rb") as f:
        u1, str_len, u2, json_len = struct.unpack("<IIII", f.read(16))
        header = json.loads(f.read(json_len).decode("utf-8"))
        base_offset = 8 + str_len

        renderer_assets = header["files"]["out"]["files"]["renderer"]["files"]["assets"]["files"]
        intl_file = [k for k in renderer_assets.keys() if k.startswith("IntlProvider-")][0]
        styles_file = [k for k in renderer_assets.keys() if k.startswith("styles-")][0]

        intl_node = renderer_assets[intl_file]
        styles_node = renderer_assets[styles_file]

        f.seek(base_offset + int(intl_node["offset"]))
        intl_data = f.read(int(intl_node["size"]))

        f.seek(base_offset + int(styles_node["offset"]))
        styles_data = f.read(int(styles_node["size"]))

    print(f"IntlProvider data size: {len(intl_data)}, first 30 bytes: {intl_data[:30]}")
    print(f"Styles data size: {len(styles_data)}, first 30 bytes: {styles_data[:30]}")

    with tempfile.NamedTemporaryFile("wb", suffix=".js", delete=False) as tf1:
        tf1.write(intl_data)
        p1 = tf1.name

    with tempfile.NamedTemporaryFile("wb", suffix=".js", delete=False) as tf2:
        tf2.write(styles_data)
        p2 = tf2.name

    try:
        r1 = subprocess.run(["node", "--check", p1], capture_output=True)
        err1 = r1.stderr.decode("utf-8", errors="replace")
        print(f"IntlProvider check: returncode={r1.returncode}")
        if r1.returncode != 0:
            print("IntlProvider Error:\n", err1[:500])

        r2 = subprocess.run(["node", "--check", p2], capture_output=True)
        err2 = r2.stderr.decode("utf-8", errors="replace")
        print(f"Styles check: returncode={r2.returncode}")
        if r2.returncode != 0:
            print("Styles Error:\n", err2[:500])

        if r1.returncode == 0 and r2.returncode == 0:
            print(">>> MÜKEMMEL! HER İKİ DOSYA DA %100 GEÇERLİ JAVASCRIPT! <<<")
    finally:
        os.remove(p1)
        os.remove(p2)

if __name__ == "__main__":
    test_patched_js_syntax()
