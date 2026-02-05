# Changelog - v2.0

## Major Changes

### 1. **Dashboard-First UI**
- App now opens to the Dashboard page showing performance metrics
- Sidebar navigation replaces top-level tabs
- Dashboard displays KPIs for Today, This Week, and This Month

### 2. **New Database Schema**
- Added `bets` table for individual bet tracking
- `bets` table includes:
  - `id`: Auto-increment primary key
  - `event_date`: Date bet was placed
  - `book`: Sportsbook name
  - `description`: Bet description (optional)
  - `amount_risked`: Stake amount
  - `american_odds`: Odds in American format (e.g., -110, +150)
  - `status`: "open", "won", or "lost"
  - `pnl`: Calculated profit/loss
  - `last_updated`: Timestamp

### 3. **Two Data Entry Modes**
- **Book P&L Mode**: Enter daily profit/loss for an entire book (original functionality)
  - Input: Event Date, Book, Total Risked, Total Won
  - Uses UPSERT logic to aggregate by date and book
  
- **Individual Bets Mode**: Log single bets with American odds
  - Input: Bet Date, Book, Description, Amount Risked, American Odds, Status
  - Automatically calculates payout based on:
    - Positive Odds: `Profit = Amount × (Odds / 100)`
    - Negative Odds: `Profit = Amount / (-Odds / 100)`
    - Loss: `-Amount Risked`
  - Support for "open" (unsettled) bets

### 4. **Enhanced Analytics**
- Timeframe-based stats: Today, This Week, This Month
- Combined analytics from both transactions and settled bets
- Open bets excluded from P&L calculations
- Cumulative P&L chart across all bet types
- Book performance charts

### 5. **Data Management**
- Two-tab Ledger system:
  - **Transactions Tab**: Edit/delete daily book P&L entries
  - **Individual Bets Tab**: Update bet status, edit details, delete
- Update bet status from "open" to "won"/"lost" with auto P&L calculation

## API Changes

### New Functions
- `calculate_pnl_from_odds()` - Calculate payout from American odds
- `insert_bet()` - Add individual bet
- `get_all_bets()` - Fetch all bets
- `update_bet()` - Update bet status/PnL
- `delete_bet()` - Remove bet
- `get_today_stats()` - Get today's metrics
- `get_week_stats()` - Get week's metrics
- `get_month_stats()` - Get month's metrics

### Existing Functions (Unchanged)
- `init_db()` - Now creates both tables
- `upsert_transaction()` - Still works as before
- `get_all_transactions()` - Still works as before
- `delete_transaction()` - Still works as before
- `update_transaction()` - Still works as before

## UI Structure

### Sidebar Navigation
```
Navigate
├── 📊 Dashboard
├── 📝 Enter Bets
└── 📋 Ledger

About Section
```

### Dashboard Page
- KPI cards (Today/Week/Month)
- Cumulative P&L chart
- Book performance chart

### Enter Bets Page
- Radio selector for entry mode
- Book P&L form (original rapid entry)
- Individual Bets form (new)
- Recent entries preview for both types

### Ledger Page
- Tab 1: Transactions Management
- Tab 2: Individual Bets Management

## Backward Compatibility

- Existing `transactions` table is preserved
- All historical Book P&L data remains intact
- `get_all_transactions()` queries work unchanged
- Original UPSERT logic unchanged

## Database Migration

No migration needed. The app automatically creates the `bets` table on first run if it doesn't exist.

## File Structure

```
sports-betting-tracker/
├── app.py                 # Main app (updated)
├── requirements.txt       # Dependencies (unchanged)
├── README.md             # Documentation (updated)
├── CHANGELOG.md          # This file
└── bet_tracker.db        # SQLite database (now has 2 tables)
```

## Next Steps / Future Enhancements

- [ ] Import CSV functionality
- [ ] Export analytics as PDF
- [ ] Bet stats by day of week / sport type
- [ ] Parlay tracking and breakdown
- [ ] Mobile-responsive design improvements
- [ ] Database backup/restore functionality
