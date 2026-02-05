# 🎰 Rapid-Entry Betting Tracker

A lightweight, keyboard-centric local web application for tracking sports bets across multiple sportsbooks with real-time analytics and ROI tracking.

## Features

✅ **Dashboard First** - Opens with analytics for today, this week, and this month  
✅ **Two Entry Modes** - Log daily book P&L or individual bets with odds  
✅ **Automatic P&L Calculation** - Input American odds and win/loss status to auto-calculate payout  
✅ **Unsettled Bets** - Mark bets as "open" until they settle  
✅ **Real-time Charts** - Cumulative P&L over time and performance by sportsbook  
✅ **Data Management** - Edit, update, or delete transactions and individual bets  
✅ **Local Storage** - SQLite database persists between app restarts  

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone or navigate to the project directory:**
   ```bash
   cd /path/to/sports-betting-tracker
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Running the App

Start the Streamlit app:

```bash
streamlit run app.py
```

This will launch a local web server (typically at `http://localhost:8501`).

## Usage

### Dashboard (📊)
Opens by default showing performance metrics:
- **KPIs**: P&L, Total Risked, and ROI % for Today, This Week, and This Month
- **Cumulative Chart**: Line graph showing running total P&L over time
- **Book Performance**: Horizontal bar chart comparing profit/loss by sportsbook

### Enter Bets (📝)
Two modes for data entry:

**Mode 1: Book P&L**
- Use when you have the daily profit/loss for an entire book
- Enter: Event Date, Sportsbook Name, Total Risked, Total Won
- Real-time preview shows net P&L
- Data automatically aggregates by date and book using UPSERT logic

**Mode 2: Individual Bets**
- Use to log single bets with American odds
- Enter: Bet Date, Sportsbook, Description, Amount Risked, American Odds
- Mark bet status: "open" (unsettled), "won", or "lost"
- App automatically calculates payout based on odds:
  - **Positive Odds** (e.g., +150): Profit = Risked × (Odds / 100)
  - **Negative Odds** (e.g., -110): Profit = Risked / (-Odds / 100)
  - **Loss**: -Amount Risked
- Open bets tracked separately, can be updated later

### Ledger (📋)
Manage your data with two sections:

**Transactions Tab**
- View all daily book P&L entries in a table
- Edit amounts directly and sync changes
- Delete individual transactions or clear all data

**Individual Bets Tab**
- View all individual bets with description, odds, and status
- Update bet status from "open" to "won"/"lost" (auto-calculates P&L)
- Delete individual bets

### Sidebar Navigation
Left sidebar provides navigation between pages. About section displays app info.

## Database Schema

All data is stored in `bet_tracker.db` (SQLite) with two tables:

### Transactions Table (Daily Book P&L)

| Column | Type | Notes |
|--------|------|-------|
| `event_date` | DATE | Date games occur |
| `book` | TEXT | Sportsbook name |
| `total_risked` | REAL | Aggregated stake |
| `total_won` | REAL | Aggregated payout |
| `last_updated` | TIMESTAMP | Auto-tracked |
| **Primary Key** | `(event_date, book)` | Composite key for UPSERT |

### Bets Table (Individual Bets)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | Auto-increment primary key |
| `event_date` | DATE | Date bet was placed |
| `book` | TEXT | Sportsbook name |
| `description` | TEXT | Bet description (optional) |
| `amount_risked` | REAL | Bet stake |
| `american_odds` | REAL | Odds (e.g., -110, +150) |
| `status` | TEXT | "open", "won", or "lost" |
| `pnl` | REAL | Profit/loss (calculated when won/lost) |
| `last_updated` | TIMESTAMP | Auto-tracked |

### UPSERT Logic (Transactions Table)

When you submit a Book P&L entry, the app executes:
```sql
INSERT INTO transactions (event_date, book, total_risked, total_won, last_updated)
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(event_date, book) DO UPDATE SET
    total_risked = total_risked + ?,
    total_won = total_won + ?,
    last_updated = CURRENT_TIMESTAMP
```

This means multiple entries for the same book on the same day are **incremented** rather than replaced.

## File Structure

```
sports-betting-tracker/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── bet_tracker.db        # SQLite database (created on first run)
```

## Architecture Overview

### Single `app.py` Organization:
1. **Database Utilities** - Connection, CRUD operations for both tables
2. **Bet Utilities** - American odds calculation, individual bet management
3. **Analytics Utilities** - KPI calculations for today/week/month
4. **Sidebar Navigation** - Page routing (Dashboard, Enter Bets, Ledger)
5. **Dashboard Page** - Opens by default with performance metrics
6. **Enter Bets Page** - Two-mode data entry (Book P&L or Individual Bets)
7. **Ledger Page** - Two-tab data management (Transactions & Individual Bets)

## Tips & Tricks

- **Dashboard First**: App opens with performance analytics—switch to Enter Bets or Ledger as needed
- **Two Entry Types**: Use Book P&L for daily summaries, Individual Bets for granular tracking
- **American Odds**: 
  - Positive odds (e.g., +150) = underdog
  - Negative odds (e.g., -110) = favorite
  - Always enter the exact odds (including the sign)
- **Open Bets**: Mark bets as "open" to track them before settlement, then update status later
- **Unsettled Bets Don't Count**: Open bets are excluded from analytics and total P&L calculations
- **Portable**: The entire app is one file (`app.py`) with a local database. Copy the folder anywhere and it works.
- **Aggregation**: Multiple Book P&L entries on the same book and date are summed automatically.
- **Deletion**: Use the Ledger tab to fix mistakes. You can edit or delete individual transactions/bets.
- **Export**: Open `bet_tracker.db` with any SQLite client to export data as CSV or JSON if needed.

## Troubleshooting

**App won't start:**
```bash
pip install --upgrade -r requirements.txt
```

**Database errors:**
- Delete `bet_tracker.db` to reset (data will be lost)
- App will recreate a fresh database on next run

**Slow performance:**
- Database is fast even with thousands of records
- If sluggish, check if Streamlit auto-rerun is enabled (reload the page)

## License

Open source. Use freely for personal or commercial purposes.

---

**Happy tracking! 🚀**
