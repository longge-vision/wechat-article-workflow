---
name: wechat-article-workflow
description: 自动化完成从论文到微信公众号文章的完整流程，包括下载论文 PDF、提取图表、整理资料、可选发送到 Coze / 扣子生成初稿、生成公众号文章、生成口播字幕、发布到公众号草稿箱。Use when users ask to run or update the WeChat article workflow, publish paper articles to WeChat drafts, or combine paper2wechat with Coze first-draft writing.
---

# 公众号文章工作流

Use this skill for the full paper-to-WeChat workflow. Prefer the newer `paper2wechat` skill for paper parsing and article writing details, and use this skill as the orchestration checklist.

## Core Workflow

1. Parse/download the paper and extract figures.
2. Build the paper material package: title, authors, abstract, method, experiments, figure list, citation, and resource links.
3. Write the article directly with Codex, or use the optional Coze / 扣子 first-draft stage below.
4. Normalize the article into WeChat markdown: attractive Chinese title, production-pain opening, technical explanation, paper figures only, citation note, and no direct resource links when keyword auto-reply is used.
5. Append clickable related historical WeChat articles.
6. Publish the final markdown to the WeChat draft box through the existing fixed-IP server workflow.
7. If resources exist, update WeChat backend keyword auto-reply.
8. Optionally generate short-video script/subtitles from the final article.

## Coze / 扣子 First-Draft Stage

Use this stage when the user asks to let Coze / 扣子 write the first draft.

Default Coze task page:

`https://www.coze.cn/task/7582896497852383515`

Run the handoff script after paper parsing:

```powershell
py -3 C:\Users\User\.codex\skills\paper2wechat\scripts\coze_article_handoff.py `
  ".paper2wechat\<paper_id>\parsed\<paper_id>.json" `
  --workspace "F:\program\公众号" `
  --keyword "<RESOURCE_KEYWORD>" `
  --copy --open
```

The script generates:

- `.paper2wechat/<paper_id>/outputs/<paper_id>.coze_material.md`: paste-ready material for Coze.
- `.paper2wechat/<paper_id>/outputs/<paper_id>.coze_material.coze.md`: expected file path for the Coze returned draft.

After the user manually downloads or copies the Coze result, import it before normalization:

```powershell
py -3 C:\Users\User\.codex\skills\paper2wechat\scripts\import_coze_draft.py `
  --material ".paper2wechat\<paper_id>\outputs\<paper_id>.coze_material.md" `
  --input "C:\path\to\coze_download.md"
```

If the user copied the Coze article to the clipboard, use `--clipboard` instead of `--input`.

Important rules:

- Coze output is only a first draft. Do not publish it verbatim.
- Codex must re-check all claims, metrics, datasets, and method descriptions against the parsed paper/material.
- Use only figures extracted from the paper or supplied in the verified material package.
- Remove direct paper/PDF/code/project links from the public article body when resources should be delivered by keyword auto-reply.
- Add public CTA text such as `后台回复关键词「XXX」获取论文与相关资料链接`.
- Add/rebuild clickable historical article recommendations after the final article is normalized.

## Publishing Rules

- Prefer `F:\program\公众号\tools\one_click_wechat_publish.py` for draft publishing so publication goes through the configured fixed-IP Tencent Cloud server.
- Do not expose paper/code links in the article body when a keyword auto-reply resource file is available.
- Keep citation/source notes in the article. Citation is not the same as a resource download link.
- After publishing, update keyword auto-reply with `tools\wechat_backend_auto_reply.py` when needed.
- Before final publish, verify images resolve, title is Chinese and attractive, no long English paragraphs remain, and no tool-wrapper artifacts are present.

## Short Video Follow-Up

After the article is finalized, use the short-video skills to produce:

- 45-90 second voiceover script.
- Subtitle lines.
- Shot plan using article/paper figures.
- Optional vertical video edit.
