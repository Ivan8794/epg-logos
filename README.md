# EPG 台标库

按 EPG（XMLTV）里的频道名称自动生成台标库：**每个频道一个 `{name}.png`，`{name}` 与 EPG 的 `<display-name>` 完全一致**，每天自动从 EPG 同步。

- EPG 源：`https://myeth-epg.github.io/public/epg.a.xml`
- 自动更新：GitHub Actions，每天北京时间 11:30（也可在 Actions 页手动 Run workflow）

## 链接格式

```
https://ivan8794.github.io/epg-logos/logos/{name}.png      ← GitHub Pages（推荐）
https://raw.githubusercontent.com/Ivan8794/epg-logos/main/logos/{name}.png  ← 备用直链
```

`{name}` 就是 EPG 里的 `<display-name>` 原文，做 URL 百分号编码后使用。例如：

| EPG 名称 | 链接 |
| --- | --- |
| `[TW-I] 02 NHK` | `https://ivan8794.github.io/epg-logos/logos/%5BTW-I%5D%2002%20NHK.png` |
| `[TW-I] 04 東森新聞 HD` | `https://ivan8794.github.io/epg-logos/logos/%5BTW-I%5D%2004%20%E6%9D%B1%E6%A3%AE%E6%96%B0%E8%81%9E%20HD.png` |
| `[myTV SUPER] 81 翡翠台&#124;H265&#124;字幕` | `https://ivan8794.github.io/epg-logos/logos/%5BmyTV%20SUPER%5D%2081%20%E7%BF%A1%E7%BF%A0%E5%8F%B0%7CH265%7C%E5%AD%97%E5%B9%95.png` |

不想自己拼 URL 的话，直接查索引表：

| 文件 | 用途 |
| --- | --- |
| `logos.json` | `{ "频道名": "完整台标链接" }`，直接按名称取值 |
| `index.json` | 全量结构化清单（名称 / 链接 / 分组 / channel id / 原始图标源） |
| `index.html` | 可视化浏览 + 搜索（Pages 打开即是台标墙） |
| `missing.json` | EPG 里没有图标、或图标源下载失败的频道清单 |
| `logos/` | 全部 `{name}.png` |

## 仓库结构

```
logos/                      # {display-name}.png
scripts/build.py            # 从 EPG 抓取 → 下载图标 → 转 PNG → 生成索引
.github/workflows/update-logos.yml
index.json / logos.json / missing.json / index.html
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

- 当前 EPG 约 2470 条频道条目、2450 个不同名称、1067 个不同图标源；约 520 个频道在 EPG 里本身没有 `<icon>`，这些名称不会生成台标，只在 `missing.json` 的 `no_icon_in_epg` 里列出。
- 同一名称在不同分组指向不同图标时，取先出现的那个，冲突记录在 `missing.json` 的 `name_conflicts`。
- 第三方图标源（tvking、astro、wikia 等）可能失效，失败项记录在 `missing.json` 的 `download_failed`，已成功过的旧文件会保留，不会因为一次失败被删除。
- 名称里的 `|` 在文件名里保留原样，URL 里编码为 `%7C`；如果要把仓库 clone 到 Windows 本地，含 `|` 的文件名无法落盘（GitHub 托管与 Pages 访问不受影响）。
