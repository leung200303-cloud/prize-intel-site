# 部署 workflow 範本

唔可以直接放 .github/workflows/（需要 PAT 有 workflow scope）。用時：複製 docs/deploy-workflow.yml 去 .github/workflows/deploy.yml，並喺 repo Settings → Secrets 設 CLOUDFLARE_API_TOKEN 同 CLOUDFLARE_ACCOUNT_ID。
