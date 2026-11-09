#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPG 台标库构建脚本

从 EPG（XMLTV）读取频道清单与 <icon src="...">，把每个频道的台标保存成
logos/{display-name}.png，并生成 index.json / logos.json / index.html。

台标文件名 == EPG 里的 <display-name> 原文，保证与 EPG 名称一一对应。
"""

import io
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree

# ---------------------------------------------------------------- 配置
EPG_URLS = [
    "https://myeth-epg.github.io/public/epg.a.xml",
]

REPO = os.environ.get("REPO_SLUG", "Ivan8794/epg-logos")
BRANCH = os.environ.get("REPO_BRANCH", "main")
PAGES_BASE = "https://ivan8794.github.io/epg-logos/logos/"
RAW_BASE = "https://raw.githubusercontent.com/%s/%s/logos/" % (REPO, BRANCH)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_DIR = os.path.join(ROOT, "logos")
UA = "Mozilla/5.0 (compatible; epg-logos-builder/1.0)"
WORKERS = 12
TIMEOUT = 40
RETRIES = 2

CST = timezone(timedelta(hours=8))


# ---------------------------------------------------------------- 网络
def safe_url(url):
    """把含中文等非 ASCII 字符的 URL 做百分号编码。"""
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~-._")


def fetch(url, retries=RETRIES, timeout=TIMEOUT):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                safe_url(url),
                headers={"User-Agent": UA, "Accept": "*/*"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


# ---------------------------------------------------------------- EPG 解析
def load_epg(url):
    data, _ = fetch(url)
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    text = data.decode("utf-8", "replace")
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, count=1)

    channels = []
    for event, el in ElementTree.iterparse(io.BytesIO(text.encode("utf-8")), events=("end",)):
        if el.tag != "channel":
            continue
        dn = el.find("display-name")
        ic = el.find("icon")
        name = (dn.text or "").strip() if dn is not None else ""
        icon = (ic.get("src") or "").strip() if ic is not None else ""
        if name:
            channels.append(
                {
                    "name": name,
                    "channel_id": (el.get("id") or "").strip(),
                    "group": (el.get("group-title") or "").strip(),
                    "icon": icon,
                }
            )
        el.clear()
    return channels


# ---------------------------------------------------------------- 文件名
_ILLEGAL_FS = {"/": "／", "\\": "＼"}


def safe_name(name):
    """只替换文件系统层面无法承载的字符，其余保持 EPG 原文。"""
    out = "".join(_ILLEGAL_FS.get(ch, ch) for ch in name if ord(ch) >= 32)
    return out.strip(" ")


# ---------------------------------------------------------------- 图片
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def to_png(body):
    """返回标准 PNG 字节；不合法则返回 None。"""
    if body[:8] == PNG_SIG:
        return body
    try:
        from PIL import Image  # 延迟导入，本地无 Pillow 时仅跳过转换

        img = Image.open(io.BytesIO(body))
        img.load()
        if img.mode in ("P", "LA", "L"):
            img = img.convert("RGBA")
        elif img.mode not in ("RGBA", "RGB"):
            img = img.convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None


def download_icon(url):
    body, ctype = fetch(url)
    png = to_png(body)
    if png is None:
        raise ValueError("不是可转换的图片: %s (%s)" % (url, ctype))
    return png


# ---------------------------------------------------------------- 主流程
def main():
    os.makedirs(LOGO_DIR, exist_ok=True)

    # 1) 读取所有 EPG，按 display-name 合并
    by_name = {}
    order = []
    conflict = {}
    for url in EPG_URLS:
        try:
            channels = load_epg(url)
        except Exception as e:  # noqa: BLE001
            print("[warn] 读取 EPG 失败 %s: %s" % (url, e))
            continue
        for ch in channels:
            name = ch["name"]
            if name not in by_name:
                by_name[name] = dict(ch)
                order.append(name)
            else:
                old = by_name[name]
                if not old["icon"] and ch["icon"]:
                    old["icon"] = ch["icon"]
                elif ch["icon"] and old["icon"] and ch["icon"] != old["icon"]:
                    conflict.setdefault(name, set()).update({old["icon"], ch["icon"]})
                for k in ("group", "channel_id"):
                    if not old[k] and ch[k]:
                        old[k] = ch[k]

    print("EPG 频道条目合并后：%d 个名称" % len(order))

    # 2) 下载唯一的台标（同一 icon 只下一次）
    unique_icons = sorted({by_name[n]["icon"] for n in order if by_name[n]["icon"]})
    print("需要下载的台标：%d 个" % len(unique_icons))

    blob = {}
    failed_src = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(download_icon, u): u for u in unique_icons}
        done = 0
        for fut in as_completed(futures):
            src = futures[fut]
            done += 1
            try:
                blob[src] = fut.result()
            except Exception as e:  # noqa: BLE001
                failed_src[src] = str(e)[:200]
            if done % 100 == 0:
                print("  下载进度 %d/%d" % (done, len(unique_icons)))

    print("下载成功 %d，失败 %d" % (len(blob), len(failed_src)))

    # 3) 落盘：文件名 = display-name
    written, unchanged = 0, 0
    for name in order:
        src = by_name[name]["icon"]
        if not src or src not in blob:
            continue
        fname = safe_name(name)
        path = os.path.join(LOGO_DIR, fname + ".png")
        data = blob[src]
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    if f.read() == data:
                        unchanged += 1
                        continue
            except OSError:
                pass
        with open(path, "wb") as f:
            f.write(data)
        written += 1
    print("写入 %d 个台标，未变化 %d 个" % (written, unchanged))

    # 4) 索引
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    entries = []
    no_icon, dl_failed = [], []
    for name in order:
        src = by_name[name]["icon"]
        fname = safe_name(name)
        if not src:
            no_icon.append(name)
            continue
        if src not in blob:
            dl_failed.append(name)
            continue
        quoted = urllib.parse.quote(fname + ".png", safe="-_.!~*'()")
        entries.append(
            {
                "name": name,
                "file": "logos/" + fname + ".png",
                "url": PAGES_BASE + quoted,
                "raw_url": RAW_BASE + quoted,
                "group": by_name[name]["group"],
                "channel_id": by_name[name]["channel_id"],
                "source_icon": src,
            }
        )

    index = {
        "updated": now,
        "timezone": "UTC+8",
        "epg": EPG_URLS,
        "base_url": PAGES_BASE,
        "count": len(entries),
        "logos": entries,
    }
    with open(os.path.join(ROOT, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)

    # name -> url 的简表，方便客户端直接查
    with open(os.path.join(ROOT, "logos.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {
                "updated": now,
                "base_url": PAGES_BASE,
                "logos": {e["name"]: e["url"] for e in entries},
            },
            f,
            ensure_ascii=False,
            indent=1,
        )

    with open(os.path.join(ROOT, "missing.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {
                "updated": now,
                "no_icon_in_epg": no_icon,
                "download_failed": dl_failed,
                "failed_sources": {k: v for k, v in sorted(failed_src.items())},
                "name_conflicts": {k: sorted(v) for k, v in sorted(conflict.items())},
            },
            f,
            ensure_ascii=False,
            indent=1,
        )

    write_html(entries, now)
    print("索引完成：%d 个可用台标，%d 个无图标，%d 个下载失败" % (len(entries), len(no_icon), len(dl_failed)))


HTML_HEAD = """<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EPG 台标库</title>
<style>
:root{color-scheme:light dark}
body{margin:0;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#0f1115;color:#e6e8eb}
header{position:sticky;top:0;z-index:9;background:rgba(15,17,21,.92);backdrop-filter:blur(8px);padding:14px 20px;border-bottom:1px solid #23262d;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0 8px 0 0;font-weight:600}
input{flex:1;min-width:220px;padding:8px 12px;border-radius:8px;border:1px solid #2c3038;background:#171a20;color:#e6e8eb;outline:none}
input:focus{border-color:#4c7dff}
.meta{opacity:.6;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;padding:18px 20px 60px}
.card{background:#171a20;border:1px solid #23262d;border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:8px}
.card img{width:100%;height:72px;object-fit:contain;background:#0b0d11;border-radius:6px}
.card .n{font-size:12px;word-break:break-all;opacity:.85}
.card .g{font-size:11px;opacity:.45}
.hide{display:none}
</style></head><body>
"""


def write_html(entries, updated):
    lines = [HTML_HEAD]
    lines.append('<header><h1>EPG 台标库</h1>')
    lines.append('<input id="q" placeholder="搜索频道名称…" autocomplete="off">')
    lines.append(
        '<span class="meta">%d 个台标 · 更新 %s</span></header><div class="grid">' % (len(entries), updated)
    )
    for e in entries:
        lines.append(
            '<div class="card" data-n="%s"><img loading="lazy" src="%s" alt=""><div class="n">%s</div>'
            '<div class="g">%s</div></div>'
            % (
                (e["name"].lower().replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")),
                e["url"],
                (
                    e["name"]
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                ),
                (e["group"] or "").replace("<", "&lt;"),
            )
        )
    lines.append("</div><script>")
    lines.append(
        "const q=document.getElementById('q');q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();"
        "document.querySelectorAll('.card').forEach(c=>{c.classList.toggle('hide',v&&!c.dataset.n.includes(v))}) });"
    )
    lines.append("</script></body></html>")
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
