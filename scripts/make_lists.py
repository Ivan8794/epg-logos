#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 index.json / missing.json 生成两份 CSV 清单。
链接一律用 EPG 原文名称（中文、英文、符号原样），不做百分号编码；
另附一列 URL 编码版本，供不支持非 ASCII 路径的客户端使用。
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import EPG_URLS, PAGES_BASE, ROOT, load_epg  # noqa: E402


def main():
    epg = {}
    for url in EPG_URLS:
        try:
            for ch in load_epg(url):
                epg.setdefault(ch["name"], {"group": ch["group"], "id": ch["channel_id"], "icon": ch["icon"]})
        except Exception as e:  # noqa: BLE001
            print("[warn] EPG 读取失败 %s: %s" % (url, e))

    with open(os.path.join(ROOT, "index.json"), encoding="utf-8") as f:
        idx = json.load(f)
    with open(os.path.join(ROOT, "missing.json"), encoding="utf-8") as f:
        miss = json.load(f)

    with open(os.path.join(ROOT, "links.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["频道名称（与EPG一致）", "台标链接（原文）", "台标链接（URL编码备用）", "分组", "频道ID"])
        for e in idx["logos"]:
            info = epg.get(e["name"], {})
            w.writerow([
                e["name"],
                PAGES_BASE + e["name"] + ".png",
                e["url"],
                e["group"] or info.get("group", ""),
                e["channel_id"] or info.get("id", ""),
            ])

    fail = miss.get("failed_sources", {})
    with open(os.path.join(ROOT, "missing.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["频道名称（与EPG一致）", "缺失原因", "EPG里的图标源", "分组", "频道ID"])
        for name in miss.get("download_failed", []):
            info = epg.get(name, {})
            src = info.get("icon", "")
            w.writerow([name, "图标源失效：" + fail.get(src, "下载失败").replace("HTTP Error ", "HTTP "),
                        src, info.get("group", ""), info.get("id", "")])
        for name in miss.get("no_icon_in_epg", []):
            info = epg.get(name, {})
            w.writerow([name, "EPG 未提供 <icon>", "", info.get("group", ""), info.get("id", "")])

    print("清单完成：links.csv %d 行，missing.csv %d 行"
          % (len(idx["logos"]), len(miss.get("download_failed", [])) + len(miss.get("no_icon_in_epg", []))),
          flush=True)


if __name__ == "__main__":
    main()
