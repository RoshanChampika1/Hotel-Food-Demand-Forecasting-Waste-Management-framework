# How to Run the Project in VS Code

Follow these steps once. After that, only steps 5 and 6 are needed each time.

## 1. Get the latest code

**If GitHub is connected and the branch has been pushed:**
```bash
git fetch origin
git checkout real-data-analysis
```

**If the branch is not on GitHub yet,** use the bundle file `real-data-analysis.bundle` from the project files. Download it, then run this inside your project folder:
```bash
git fetch "C:/path/to/real-data-analysis.bundle" real-data-analysis:real-data-analysis
git checkout real-data-analysis
```
(Replace the path with wherever you saved the file. On Mac it is something like `~/Downloads/real-data-analysis.bundle`.)

## 2. Open the folder in VS Code
1. **File → Open Folder** and choose the project folder (the one with `README.md`, `src/` and `app/`).
2. Install the **Python** extension from Microsoft, if VS Code asks.
3. Open a terminal with **Terminal → New Terminal**.

## 3. Create a virtual environment and install the libraries
**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
If `activate` shows a "running scripts is disabled" error, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Mac or Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
You should now see `(.venv)` at the start of the terminal line. Press **Ctrl+Shift+P → Python: Select Interpreter** and choose the `.venv` one.

## 4. Put the private data in place (not in GitHub)
- Copy all the **event-order Excel files** into `data/raw/`
- Copy **town_distance.csv** into `data/inputs/`

These folders are git-ignored, so the hotel's data never goes to GitHub.

## 5. Run the real-data research pipeline
```bash
python src/event_orders/extract_events.py data/raw data/processed
python src/event_orders/build_dataset.py data/raw data/processed
python src/attendance_models.py data/processed/events_clean.csv results/attendance
```
- The first two commands take about 1 minute and build `data/processed/events_clean.csv` (54 usable events).
- The last command takes **about 5–10 minutes**. It tests all 13 methods, event by event.
- Results appear in `results/attendance/`: `results_loeo.csv`, `tradeoff.csv`, the two charts (`fig1_attendance_ratio.png`, `fig2_tradeoff.png`), and the explanation in `RESULTS.md`.

## 6. Run the original pipeline and the app
```bash
python src/generate_dummy_data.py
python src/train.py
streamlit run app/streamlit_app.py
```
The browser opens at `http://localhost:8501`. Press **Ctrl+C** in the terminal to stop the app.

Note: the app still uses the models trained on **dummy data**. It will be updated to use the real-data results.

## Common problems
| Problem | Fix |
|---|---|
| `python` is not recognised | Install Python 3.11 or newer from python.org and tick "Add Python to PATH" |
| `ModuleNotFoundError` | The venv is not active. Run the activate command from step 3 again |
| `FileNotFoundError: events_clean.csv` | Run the two commands in step 5 first, and check that the Excel files are in `data/raw/` |
| The app says "No trained models found" | Run `python src/train.py` first |
