# How to Run the Project in VS Code

Follow these steps once. After that, only `streamlit run app/streamlit_app.py` is needed each time.

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

## 6. Run the Event Order System (the app)
Do these two steps once, and again whenever you add new event-order Excel files:
```bash
python src/event_system/build_master_data.py data/raw data/master
python src/event_system/train_attendance.py data/processed/events_clean.csv models/attendance_quantreg.json
```
- The first one reads all the Excel files and builds the recipe book, dish list and item list in `data/master/` (about 5 minutes).
- The second one trains the guest-count model (a few seconds).

Then start the app:
```bash
streamlit run app/streamlit_app.py
```
The browser opens at `http://localhost:8501`. Press **Ctrl+C** in the terminal to stop the app.

How to use it:
1. **Left side:** fill in the event (date, day or night, hall, type, event no, food serving time, booked pax, customer town) and choose the safety level.
2. **Party Menu tab:** choose the dishes for each section, or start from a past event's menu. Set the bite divisors (kg = guests / divisor, like the Excel) and the glasses for Ice Coffee and other counted items.
3. **Guest forecast tab:** see how many guests to cook for and what each safety level would have done on past events. A manager can type their own number.
4. **Stock Balance tab:** the raw materials for the event, in Fresh, Dry and Meat groups.
5. **Kitchen recipes tab:** the ingredients for each dish.
6. **Print & save tab:** download the Party Menu PDF (kitchen notice board), the Stock Balance PDF (for the chef), the kitchen recipes PDF, or all sheets in one Excel file. **Save order** keeps the order in `data/orders/`.

The old category demo (dummy data) still runs with `streamlit run app/category_forecast_demo.py`.

## Common problems
| Problem | Fix |
|---|---|
| `python` is not recognised | Install Python 3.11 or newer from python.org and tick "Add Python to PATH" |
| `ModuleNotFoundError` | The venv is not active. Run the activate command from step 3 again |
| `FileNotFoundError: events_clean.csv` | Run the two commands in step 5 first, and check that the Excel files are in `data/raw/` |
| The app says "No master data" | Run `python src/event_system/build_master_data.py data/raw data/master` |
| The forecast tab says "Attendance model not found" | Run `python src/event_system/train_attendance.py` |
