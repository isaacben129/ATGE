# GitHub Hosting Guide: ATG Engine

This document provides step-by-step instructions to host your Autonomous Twitter Growth Engine on GitHub.

## Prerequisites

- A GitHub account ([sign up](https://github.com/signup) if needed)
- Git installed on your computer (check with `git --version`)
- Your project ready with no secrets committed

---

## Step 1: Pre-flight Check

Before pushing to GitHub, verify that sensitive files are not tracked:

### 1.1 Verify `.env` is ignored

Your `.env` file should already be in `.gitignore`. Double-check:

```bash
git status
```

**Expected:** `.env` should NOT appear in the list of files. If it does, it means it was previously tracked. Contact support for help removing it from Git history.

### 1.2 (Optional) Keep persona file private

If you don't want `persona_mila.json` to be public on GitHub, add it to `.gitignore`:

```bash
echo "persona_mila.json" >> .gitignore
```

Or to ignore all persona files:
```bash
echo "persona_*.json" >> .gitignore
```

**Note:** The project already includes `atg_engine/config/persona_config.example.json` as a generic example, so others can still see the format.

### 1.3 (Optional) Add a LICENSE file

If you want to specify how others can use your code, add a LICENSE file. Common choices:
- **MIT License** - Permissive, allows commercial use
- **Apache 2.0** - Permissive with patent protection
- **GPL v3** - Copyleft, requires derivatives to be open source

If you don't add a LICENSE, your code is "all rights reserved" by default.

---

## Step 2: Initialize Git Repository

If you haven't already initialized Git, do so now:

```bash
# Navigate to your project directory
cd "c:\Users\isaac\Downloads\crewai social media"

# Initialize Git repository
git init
```

---

## Step 3: Stage and Commit Files

Add all files and create your first commit:

```bash
# Add all files (respects .gitignore)
git add .

# Verify what will be committed (check that .env is NOT listed)
git status

# Optional: Review the changes before committing
git diff --cached

# Create your first commit
git commit -m "Initial commit: ATG Engine"
```

**Important:** Before committing, scan the `git status` output to ensure:
- ✅ `.env` is NOT listed
- ✅ `*.db` files are NOT listed
- ✅ `__pycache__/` directories are NOT listed
- ✅ `.venv/` or `venv/` are NOT listed

---

## Step 4: Create GitHub Repository

1. Go to [github.com](https://github.com) and sign in
2. Click the **"+"** icon in the top right → **"New repository"**
3. Fill in:
   - **Repository name:** e.g., `atg-engine` or `crewai-social-media`
   - **Description:** (optional) e.g., "Autonomous Twitter Growth Engine using CrewAI"
   - **Visibility:** Choose **Public** or **Private**
   - **DO NOT** check "Add a README file" (you already have one)
   - **DO NOT** check "Add .gitignore" (you already have one)
   - **DO NOT** select a license here (add it manually if desired)
4. Click **"Create repository"**

---

## Step 5: Connect Local Repository to GitHub

After creating the repository, GitHub will show you setup instructions. Use these commands:

```bash
# Add GitHub as remote (replace YOUR_USERNAME and YOUR_REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Or if you prefer SSH (requires SSH key setup):
# git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git

# Rename default branch to 'main' (if not already)
git branch -M main

# Push your code to GitHub
git push -u origin main
```

**Note:** If you're prompted for credentials:
- For HTTPS: Use a [Personal Access Token](https://github.com/settings/tokens) (not your password)
- For SSH: Ensure your SSH key is added to GitHub

---

## Step 6: After Pushing

### 6.1 Verify Upload

Visit your repository on GitHub and confirm:
- ✅ All files are present
- ✅ `.env` is NOT visible (it's ignored)
- ✅ README.md displays correctly

### 6.2 Set Up Secrets for Deployment

**CRITICAL:** Never commit real API keys or secrets to GitHub. When deploying (Railway, Fly.io, etc.):

1. Set all environment variables in your deployment platform's dashboard
2. Use the values from your local `.env` file
3. Never put secrets in GitHub Actions, GitHub Secrets (unless for CI/CD), or any committed files

Required environment variables (see `.env.example`):
- `GROQ_API_KEY`
- `TWITTER_BEARER_TOKEN`
- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_SECRET`
- `DATABASE_URL` (for production, use Supabase or PostgreSQL)

### 6.3 (Optional) Set Up GitHub Actions

If you want CI/CD (automated testing, deployment), you can add GitHub Actions workflows later. See GitHub Actions documentation.

---

## Troubleshooting

### "fatal: remote origin already exists"
If you already added the remote, update it:
```bash
git remote set-url origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
```

### "Permission denied" when pushing
- **HTTPS:** Use a Personal Access Token instead of password
- **SSH:** Ensure your SSH key is added to GitHub (Settings → SSH and GPG keys)

### ".env file is showing on GitHub"
If `.env` was accidentally committed:
1. Remove it from Git tracking: `git rm --cached .env`
2. Commit: `git commit -m "Remove .env from tracking"`
3. Push: `git push`
4. If it contains real secrets, rotate all API keys immediately

---

## Next Steps

- **Deploy to Railway/Fly.io:** See the [README.md](README.md) "Deploying" section
- **Set up Supabase:** Follow the Supabase setup instructions in README.md
- **Run locally:** `pip install -e .` then configure `.env`

---

## Summary Checklist

- [ ] Verified `.env` is not tracked (`git status`)
- [ ] (Optional) Added `persona_mila.json` to `.gitignore` if keeping private
- [ ] (Optional) Added LICENSE file
- [ ] Initialized Git repository (`git init`)
- [ ] Staged all files (`git add .`)
- [ ] Verified no secrets in commit (`git status`, `git diff --cached`)
- [ ] Created first commit (`git commit`)
- [ ] Created GitHub repository (no README, no .gitignore)
- [ ] Added remote (`git remote add origin`)
- [ ] Renamed branch to main (`git branch -M main`)
- [ ] Pushed to GitHub (`git push -u origin main`)
- [ ] Verified files on GitHub (no `.env` visible)
- [ ] Set up environment variables in deployment platform (when ready)

---

**Remember:** Your `.env` file stays local. All secrets are configured in your deployment platform's environment variables, never in the repository.
