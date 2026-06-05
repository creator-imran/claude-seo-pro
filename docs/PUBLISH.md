# Publishing to GitHub (creator-imran)

The build machine used to create this repo had **no `git` and no `gh` CLI**, so it
could not push for you. Here's the exact path to get it onto
`github.com/creator-imran/claude-seo-pro`. Two options.

## Option A — one command (recommended)

On a machine where you can install software:

```powershell
# 1. Install the tools (Windows)
winget install --id Git.Git -e
winget install --id GitHub.cli -e

# 2. Authenticate as creator-imran
gh auth login        # choose GitHub.com > HTTPS > login with browser

# 3. From the claude-seo-pro folder, run the helper
cd "C:\Users\Imran Shaikh\claude-seo-pro"
powershell -ExecutionPolicy Bypass -File publish-to-github.ps1
```

The helper inits git, stages files (secrets excluded by `.gitignore`), runs a
**secret-leak guard** on what's staged, commits, then creates the **private** repo
and pushes. Use `-Public` to make it public, or `-Repo "org/name"` to change the
target.

## Option B — manual

```bash
cd claude-seo-pro
git init -b main
git add .
git commit -m "Claude SEO Pro v1.0.0"
gh repo create creator-imran/claude-seo-pro --private --source=. --remote=origin --push
# or, without gh: create the empty repo in the GitHub web UI, then:
#   git remote add origin https://github.com/creator-imran/claude-seo-pro.git
#   git push -u origin main
```

## Before you push — quick checklist

- [ ] `git status` shows **no** `*-api.json`, `.env`, `client_secret*`,
      `service_account*`, or `oauth-token.json` staged. (The `.gitignore` and the
      helper's leak-guard both cover these, but eyeball it.)
- [ ] `NOTICE` and `LICENSE` are present (MIT attribution to upstream).
- [ ] You're authenticated as the right account: `gh auth status`.

## Granting a client access (private repo)

- Per-seat: **GitHub → repo → Settings → Collaborators → Add people**, or
  `gh repo edit creator-imran/claude-seo-pro` / the API.
- For multiple clients, consider moving the repo into a dedicated GitHub **org**
  and managing access by team.

## Releasing a version

```bash
git tag -a v1.0.0 -m "Claude SEO Pro v1.0.0"
git push origin v1.0.0
gh release create v1.0.0 --title "v1.0.0" --notes-file CHANGELOG.md
```
