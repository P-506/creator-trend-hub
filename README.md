# Creator Weekly Trend Hub

Static one-page trend hub for the Thailand Creator Program.

## Local preview

Run a local static server from this folder:

```powershell
python -m http.server 4173
```

Then open:

```text
http://localhost:4173
```

## Update trend data

The page reads:

```text
data/trends.json
```

Generate it with:

```powershell
python scripts/fetch_trends.py --out data/trends.json --keep-existing
```

The script uses:
- Google Trends RSS for Thailand trend signals
- GDELT DOC API for recent Thailand news signals

If all external feeds fail, `--keep-existing` leaves the latest JSON untouched.

## Deploy to GitHub Pages

This folder is ready to be pushed as its own GitHub repository.

1. Create a new GitHub repository, for example `creator-trend-hub`.
2. Push the contents of this folder to the repository's `main` branch.
3. In GitHub, go to `Settings` -> `Pages`.
4. Set `Source` to `GitHub Actions`.
5. Run the `Deploy Creator Trend Hub` workflow, or push to `main`.

The deployed site will be available at:

```text
https://<username>.github.io/creator-trend-hub/
```
