# 🎰 Betting Tracker

Fast, local sports betting tracker with real-time analytics. Enter P&L by day, week, month, or year, or log individual bets with American odds.

## Quick Start

```bash
cd sports-betting-tracker
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`

## Features

- **Dashboard**: Today/Week/Month P&L KPIs and cumulative charts
- **Enter Bets**: Two side-by-side panels
  - **Book P&L**: Pick Daily/Weekly/Monthly/Yearly, enter aggregate profit/loss
  - **Individual Bets**: Log single bets with American odds, mark as open/won/lost
- **Data Management**: Edit/delete rows directly in tables
- **Local Storage**: SQLite database - all data stays on your machine
- **Duplicate Detection**: Warns on non-round amounts placed recently

## How It Works

**Book P&L** entries are tracked by timeframe:
- **Daily**: Enter P&L for a specific day
- **Weekly**: Enter P&L for a week starting on a specific date
- **Monthly**: Enter P&L for a specific month/year
- **Yearly**: Enter P&L for a specific year

Analytics are smart about aggregation:
- "Today" shows only daily entries
- "This Week" shows daily + weekly entries
- "This Month" shows daily + weekly + monthly entries

**Individual Bets** are always daily and auto-calculate payouts from American odds.

## Tips

- Non-round amounts (52.72, 103.50) trigger duplicate warnings
- Open bets don't count toward P&L until settled
- All P&L charts combine both transactions and settled bets
- All changes save instantly to `bet_tracker.db`
