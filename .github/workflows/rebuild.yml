name: Auto-Rebuild FedEx Weather Alert Page

on:
  # Run every day at 6 AM and 12 PM Central (11 AM and 5 PM UTC)
  schedule:
    - cron: '0 11 * * *'   # 6 AM CDT daily
    - cron: '0 17 * * *'   # 12 PM CDT daily
  # Also allow manual trigger from GitHub Actions tab
  workflow_dispatch:

permissions:
  contents: write

jobs:
  rebuild:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Fetch NOAA data and rebuild page
        run: python rebuild.py

      - name: Commit and push updated index.html
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add index.html
          # Only commit if something actually changed
          git diff --staged --quiet || git commit -m "Auto-rebuild: $(date -u '+%Y-%m-%d %H:%M UTC')"
          git push
