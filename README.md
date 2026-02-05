# 🎰 Rapid-Entry Betting Tracker

A lightweight, keyboard-centric local web application for tracking sports bets across multiple sportsbooks with real-time analytics and ROI tracking.

## Features

✅ **Rapid Entry Form** - Tab through fields and hit Enter to submit  
✅ **UPSERT Database Model** - Automatically aggregates bets by day and book  
✅ **Real-time Net Profit Preview** - See profit/loss as you type  
✅ **Analytics Dashboard** - Track ROI, cumulative profit, and book performance  
✅ **Data Management** - Edit or delete transactions in the ledger  
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

### Tab 1: Rapid Entry 📝

1. **Enter bet details:**
   - **Event Date**: Select the date the games occur (defaults to today)
   - **Sportsbook**: Name of the book (e.g., DraftKings, FanDuel)
   - **Risked Amount**: How much you wagered
   - **Won Amount**: How much you won (0 if you lost)

2. **Keyboard flow:**
   - Use **Tab** to move between fields
   - Press **Enter** (or click "Submit Bet") to record the bet
   - Data is automatically aggregated by date and book

3. **Real-time preview:**
   - Net Profit/Loss updates as you type
   - Indicates immediate outcome before submission

### Tab 2: Analytics 📊

- **KPIs**: Total Risked, Total Won, Total Profit, and Lifetime ROI%
- **Cumulative PnL Graph**: Line chart showing running total over time
- **Book Performance**: Bar chart comparing profit/loss by sportsbook
- **Detailed Statistics**: Table with ROI % breakdown per book

### Tab 3: Ledger 📋

- **View all transactions** in an editable table
- **Edit values** directly in the table
- **Sync changes** to save manual edits back to the database
- **Delete transactions** one at a time or clear all data

## Database Schema

All data is stored in `bet_tracker.db` (SQLite) with a single `transactions` table:

| Column | Type | Notes |
|--------|------|-------|
| `event_date` | DATE | Date games occur |
| `book` | TEXT | Sportsbook name |
| `total_risked` | REAL | Aggregated stake |
| `total_won` | REAL | Aggregated payout |
| `last_updated` | TIMESTAMP | Auto-tracked |
| **Primary Key** | `(event_date, book)` | Composite key for UPSERT |

### UPSERT Logic

When you submit a bet, the app executes:
```sql
INSERT INTO transactions (event_date, book, total_risked, total_won, last_updated)
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(event_date, book) DO UPDATE SET
    total_risked = total_risked + ?,
    total_won = total_won + ?,
    last_updated = CURRENT_TIMESTAMP
```

This means:
- **New entry**: Creates a new row
- **Existing entry**: Increments both amounts by the new values

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
1. **Database Utilities** - Connection, UPSERT, query functions
2. **Streamlit Configuration** - Page setup and styling
3. **Tab 1: Rapid Entry** - High-speed input form with preview
4. **Tab 2: Analytics** - KPIs and charts
5. **Tab 3: Ledger** - Data editor and management
6. **Sidebar** - Info and quick stats

## Tips & Tricks

- **Portable**: The entire app is one file (`app.py`) with a local database. Copy the folder anywhere and it works.
- **Keyboard-First**: Tab navigation is fully supported. Avoid mouse when possible for speed.
- **Aggregation**: Multiple bets on the same book and date are summed automatically.
- **Deletion**: Use the Ledger tab to fix mistakes. You can edit or delete individual transactions.
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
