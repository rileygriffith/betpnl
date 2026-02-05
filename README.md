# 🎰 Betting Tracker

Fast, local sports betting tracker with real-time analytics. Enter daily P&L or individual bets with odds, view cumulative performance, and manage your data.

## Quick Start

### Prerequisites
- Python 3.8+
- `uv` (fast Python package manager) - install with `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Setup & Run

```bash
cd /path/to/sports-betting-tracker
uv sync
uv run streamlit run app.py
```

This launches the app at `http://localhost:8501`.

## Features

- **Dashboard**: Today/Week/Month P&L and cumulative charts
- **Enter Bets**: Two panels for quick data entry
  - Book P&L: Single number P&L per book per day
  - Individual Bets: Bets with American odds (auto-calculates payout)
- **Data Management**: Edit/delete rows directly in the tables
- **Local Storage**: SQLite database - all data stays on your machine

## Data Entry

### Book P&L
- **Date** + **Book** + **P&L Amount** → Done
- Positive = win, negative = loss

### Individual Bets
- **Date** + **Book** + **Amount** + **Odds** + **Status** → Done
- Status: "open" (unsettled), "won", "lost"
- App auto-calculates payout based on American odds
- Duplicate detection for non-round amounts

## Database

Two tables in `bet_tracker.db`:
- **transactions**: Aggregated daily P&L per book
- **bets**: Individual bets with full details

Edit or delete any row directly in the Data page.

## Tips

- Non-round amounts (52.72, 103.50) get duplicate warnings
- Open bets don't count toward P&L until settled
- P&L charts combine both transaction and settled bet data
- All calculations are instant - no sync button needed

## License

Open source. Use freely for personal or commercial purposes.

---

**Happy tracking! 🚀**
