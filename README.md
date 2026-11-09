# EPG 台标库

按 EPG（XMLTV）里的频道名称自动生成台标库：**每个频道一个 `{name}.png`，`{name}` 与 EPG 的 `<display-name>` 完全一致**，每天自动从 EPG 同步。

- EPG 源：`https://myeth-epg.github.io/public/epg.a.xml`
- 自动更新：GitHub Actions，每天北京时间 11:30（也可在 Actions 页手动 Run workflow）

## 链接格式

```
https://ivan8794.github.io/epg-logos/logos/{name}.png                      ← 原文名称（推荐）
https://ivan8794.github.io/epg-logos/logos/{name URL编码}.png              ← 编码形式，内容完全相同
https://raw.githubusercontent.com/Ivan8794/epg-logos/main/logos/{name}.png ← 备用直链
```

`{name}` 就是 EPG 里的 `<display-name>` 原文：中文、英文、数字、`[ ]`、`|`、`+`、空格全部原样保留，不做任何改写（文件名与链接一致）。例如：

| EPG 名称 | 台标链接 |
| --- | --- |
| `[TW-I] 02 NHK` | `https://ivan8794.github.io/epg-logos/logos/[TW-I] 02 NHK.png` |
| `[TW-I] 04 東森新聞 HD` | `https://ivan8794.github.io/epg-logos/logos/[TW-I] 04 東森新聞 HD.png` |
| `Channel News Asia HD` | `https://ivan8794.github.io/epg-logos/logos/Channel News Asia HD.png` |

名称里带 `|` 的频道（例：`[myTV SUPER] 81 翡翠台|H265|字幕`）同样原样保留，链接为 `.../logos/[myTV SUPER] 81 翡翠台|H265|字幕.png`。

浏览器和绝大多数客户端会自动解码中文/空格，直接用原文链接即可。若某个客户端不会自动编码（把空格、`[` 原样发出导致 404），改用同一行的 URL 编码形式（`%5B`、`%20`、`%7C`…），指向的是同一个文件。

不想自己拼 URL 的话，直接取现成清单：

| 文件 | 用途 |
| --- | --- |
| `links.csv` | 频道名 → 台标链接，含原文链接与 URL 编码链接两列 |
| `logos.json` | `{ "频道名": "完整台标链接" }`，程序直接按名称取值 |
| `index.json` | 全量结构化清单（名称 / 链接 / 分组 / channel id / 原始图标源） |
| `missing.csv` / `missing.json` | 没有台标的频道：图标源失效、EPG 无图标 |
| `index.html` | 可视化浏览 + 搜索（Pages 打开即是台标墙） |
| `logos/` | 全部 `{name}.png` |

## 仓库结构

```
logos/                      # {display-name}.png
scripts/build.py            # 从 EPG 抓取 → 下载图标 → 转 PNG → 生成索引
scripts/make_lists.py       # 生成 links.csv / missing.csv 清单
.github/workflows/update-logos.yml
index.json / logos.json / missing.json / index.html / links.csv / missing.csv
```

## 更新机制

1. Actions 定时拉取 EPG（`scripts/build.py` 里的 `EPG_URLS`）。
2. 解析 `<channel>` 的 `<display-name>` 与 `<icon src>`，同一图标只下载一次。
3. 非 PNG 的图标（jpeg / webp / gif 等）用 Pillow 转成真正的 PNG。
4. 文件名 = `<display-name>` 原文；除 `/`、`\` 换成全角全等替代字符外不做任何改写。
5. 内容没变化的文件不重写，提交只包含真正变动的台标。

要加第二个 EPG，只改一行：

```python
EPG_URLS = [
    "https://myeth-epg.github.io/public/epg.a.xml",
    "https://example.com/other-epg.xml",
]
```

## 已知情况

- 当前 EPG 约 2470 条频道条目、2450 个不同名称、1067 个不同图标源；约 520 个频道在 EPG 里本身没有 `<icon>`，这些名称不会生成台标，只在 `missing.csv` / `missing.json` 里列出。
- 同一名称在不同分组指向不同图标时，取先出现的那个，冲突记录在 `missing.json` 的 `name_conflicts`。
- 第三方图标源（tvking、astro、wikia 等）可能失效，失败项记录在 `missing.csv` / `missing.json`，已成功过的旧文件会保留，不会因为一次失败被删除。
- 名称里的 `|` 在文件名里保留原样；如果要把仓库 clone 到 Windows 本地，含 `|` 的文件名无法落盘（GitHub 托管与 Pages 访问不受影响）。
