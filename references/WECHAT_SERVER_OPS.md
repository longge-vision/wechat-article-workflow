# Tencent Cloud WeChat Ops

Use the Tencent Cloud server as the fixed-IP caller for WeChat Official Account APIs.

Server:

- User: `deploy`
- Host: `175.178.71.163`
- Domain: `ni-vision.cn`
- Remote script: `/home/deploy/wechat-publisher/tools/wechat_ops.py`

Local wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 <command> [args...]
```

The wrapper passes local `WECHAT_APP_ID` and `WECHAT_APP_SECRET` to the remote command for the current run.
It does not write the secret into the server script.

## Common Commands

Check server public IP:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 ip
```

Check access token:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 token
```

List recent drafts:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 draft-list --count 10
```

Get one draft:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 draft-get <media_id>
```

Update publish-related settings on an existing draft:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 draft-update-settings <media_id> --author LabVIEW --clear-source-url --need-open-comment 1 --only-fans-can-comment 0
```

Delete one draft:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 draft-delete <media_id> --yes
```

Find duplicate-title drafts:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 draft-duplicates --count 50
```

Delete duplicate-title drafts, keeping the newest draft for each title:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 draft-delete-duplicates --count 50 --limit 5 --yes
```

Send a draft preview to a WeChat ID:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 preview <media_id> --wxname <wechat_id>
```

List follower OpenIDs:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 user-list --sample 10
```

Get follower details:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 user-info <openid1> <openid2>
```

Get material library counts:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 material-count
```

List permanent materials:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 material-list image --count 20
```

List published articles:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 publish-list --count 10
```

Get a published article:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 publish-article <article_id>
```

Submit a draft for publishing:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 publish-submit <media_id>
```

Check publishing status:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 publish-status <publish_id>
```

Delete a published article:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 publish-delete <article_id> --yes
```

Get basic stats:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 stats user-summary --begin 2026-06-10 --end 2026-06-10
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 stats article-summary --begin 2026-06-10 --end 2026-06-10
```

Get current custom menu:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 menu-get
```

Create or delete custom menu:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 menu-create menu.json --yes
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 menu-delete --yes
```

Generate daily operations report:

```powershell
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 daily-report
powershell -ExecutionPolicy Bypass -File F:\program\公众号\tools\server_wechat.ps1 daily-report --date 2026-06-10
```

One-click publish a local Markdown article to WeChat draft box through the fixed-IP server:

```powershell
python F:\program\公众号\tools\one_click_wechat_publish.py path\to\article.md
```

Default settings are read from:

```powershell
F:\program\公众号\tools\wechat_publish_settings.json
```

Default publish settings:

- Theme: `phycat`
- Author: `LabVIEW`
- Footnotes: disabled
- `source_url`: cleared by default
- Comments: enabled by default
- Only fans can comment: disabled by default
- Draft settings update: enabled by default after upload
- Original declaration: required, but must be confirmed in the WeChat backend
- Ad insertion: required, but must be confirmed in the WeChat backend
- API formal publishing is blocked until backend-only settings are manually confirmed
- Paper/PDF/GitHub/HuggingFace links: stripped from the article body by default
- Resource prompt: appended as `关注公众号后，在后台回复关键词「xxx」`
- Resource links: saved beside the article as `*.resources.json`
- Resource links are also imported to the server keyword resource store automatically after publishing.
- Publish checklist: saved beside the article as `*.publish_checklist.md`

Settings that still require manual confirmation in the WeChat Official Account backend:

- Original declaration / 原创声明
- Ad insertion / 流量主广告、文中广告
- Appreciation / 赞赏
- Cover crop and cover display / 封面裁剪和展示
- Collection, topic, album / 合集、话题、专辑
- Final publisher/operator / 最终发布操作人

These backend-only items are included in the generated publish checklist.

Set resource keyword explicitly:

```powershell
python F:\program\公众号\tools\one_click_wechat_publish.py path\to\article.md --keyword REF
```

Dry run without publishing:

```powershell
python F:\program\公众号\tools\one_click_wechat_publish.py path\to\article.md --dry-run --keyword REF
```

Publish to draft box and send a preview:

```powershell
python F:\program\公众号\tools\one_click_wechat_publish.py path\to\article.md --preview-wxname <wechat_id>
```

Submit for formal publishing after draft upload. This requires explicit confirmation:

```powershell
python F:\program\公众号\tools\one_click_wechat_publish.py path\to\article.md --submit --yes --manual-publish-confirmed
```

By default, footnote references are disabled to avoid repeated link citations. Add `--footnote` only when footnotes are wanted.

Because original declaration and ad insertion are backend-only checks, `--submit --yes` is intentionally blocked unless `--manual-publish-confirmed` is also provided after the backend settings are checked.

## Keyword Auto Reply

### Option B: Fill WeChat Backend Keyword Reply With Browser Automation

This uses the WeChat Official Account web backend, not the Official Account API. The first run opens a visible browser. Scan/login manually once; the login state is saved under:

```powershell
F:\program\公众号\.wechat_backend_browser
```

Login only:

```powershell
py -3 F:\program\公众号\tools\wechat_backend_auto_reply.py --login-only --keep-open
```

Preview the reply text that will be written:

```powershell
py -3 F:\program\公众号\tools\wechat_backend_auto_reply.py --file path\to\article.md.publish.json --print-text
```

Fill a keyword reply rule in the WeChat backend. By default this fills the form but does not save, so the operator can confirm it in the browser:

```powershell
py -3 F:\program\公众号\tools\wechat_backend_auto_reply.py --file path\to\article.md.publish.json --pause
```

After the selectors are verified on the current backend UI, it can save automatically:

```powershell
py -3 F:\program\公众号\tools\wechat_backend_auto_reply.py --file path\to\article.md.publish.json --save --pause
```

If browser startup fails, install Playwright's bundled browser once:

```powershell
py -3 -m playwright install chromium
```

Because the WeChat backend UI changes over time, this path should be treated as assisted automation. If it cannot locate a button or input, it pauses and asks the operator to navigate/click the right form, then continues filling the content.

### Option A: Self-Hosted Reply Server

Reply server script on Tencent Cloud:

```bash
python3 /home/deploy/wechat-publisher/tools/wechat_reply_server.py serve --host 127.0.0.1 --port 9088 --token <wechat-server-token>
```

Import resources generated by one-click publishing:

```bash
python3 /home/deploy/wechat-publisher/tools/wechat_reply_server.py import-resources /path/to/article.md.resources.json --keyword REF --title REF-CFA
```

Current resource store:

```bash
/home/deploy/wechat-publisher/keyword_resources.json
```

Current imported keyword:

- `REF`: CVPR 2026 REF+CFA paper page, PDF, and GitHub code.

To enable public auto-reply, configure the WeChat Official Account server URL to point to an HTTPS endpoint on `ni-vision.cn` that proxies to this service, and set the same token in `WECHAT_REPLY_TOKEN`.

## Notes

- The server IP `175.178.71.163` must stay in the WeChat Official Account IP whitelist.
- Destructive commands require `--yes`.
- Publishing to all followers should still require manual confirmation.
