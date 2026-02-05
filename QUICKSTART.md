# Quick Start Guide

## Installation

```bash
cd /Users/rileygriffith/sports-betting-tracker
pip install -r requirements.txt
streamlit run app.py
```

The app will open at `http://localhost:8501`

## First Time Setup

1. **Open the app** - You'll land on the Dashboard (currently empty)
2. **Go to Enter Bets** - Use the sidebar to navigate
3. **Choose your entry mode**:
   - **Book P&L**: If you have daily P&L totals
   - **Individual Bets**: If you want to log single bets with odds
4. **Enter your first bet**
5. **Return to Dashboard** - See your stats appear!

## Entry Mode Decision

### Use "Book P&L" Mode If:
- You track bets at the daily summary level
- You know your total profit/loss for each book per day
- You want fast, aggregate entry
- Example: "DraftKings, $50 risked, $65 won today"

### Use "Individual Bets" Mode If:
- You want granular, per-bet tracking
- You have American odds for each bet
- You want to track bets before they settle
- Example: "Bet $50 on Lakers ML at -110, result: won/lost"

**You can use BOTH modes simultaneously** - they're tracked separately but both feed into analytics.

## American Odds Reference

| Odds | Type | Example |
|------|------|---------|
| -110 | Favorite | Standard point spread bet |
| -120 | Favorite | Stronger favorite |
| +100 | Underdog | Equal payout |
| +150 | Underdog | Higher payout |
| -200 | Heavy Favorite | Smaller payout |
| +300 | Heavy Underdog | Larger payout |

**Formula:**
- Positive: `Profit = Stake × (Odds / 100)` → e.g., $100 @ +150 = +$150
- Negative: `Profit = Stake / (-Odds / 100)` → e.g., $100 @ -110 = +$90.91

## Keyboard Tips

- Tab through form fields for quick entry
- Press Enter to submit (or click button)
- Form clears automatically after submission

## Common Workflows

### Scenario 1: Logging an Unsettled Parlay
1. Go to **Enter Bets** → **Individual Bets**
2. Enter bet details: Date, Book, Description, Amount, Odds
3. Select Status: **"open"**
4. Submit
5. Later, go to **Ledger** → **Individual Bets Tab**
6. Update status to "won" or "lost" (P&L auto-calculates)

### Scenario 2: End-of-Day Summary
1. Go to **Enter Bets** → **Book P&L**
2. Enter each book's daily total
3. Example:
   - DraftKings: $100 risked, $120 won
   - FanDuel: $50 risked, $40 won
4. Both entries appear in Analytics

### Scenario 3: Fixing a Mistake
1. Go to **Ledger** → relevant tab
2. Edit the entry directly in the table or delete it
3. Click **Sync Changes** (for Transactions) or **Update** (for Bets)

## Dashboard Interpretation

### P&L Metrics
- **Green**: Profit ✅
- **Red**: Loss ❌

### Cumulative Chart
- Shows running total P&L over time
- Useful to spot trends (upward = winning, downward = losing)

### Book Performance Chart
- Horizontal bars, red for losses, green for profits
- Quickly identify which books are +/- overall

## Tips for Best Results

1. **Be Consistent**: Decide between Book P&L or Individual Bets (or both)
2. **Enter Promptly**: Log bets shortly after placing them
3. **Mark as Open**: If a bet hasn't settled, mark it "open"
4. **Update Status**: Come back and update "open" bets when they settle
5. **Review Weekly**: Check the dashboard at week's end to spot patterns
6. **Use Descriptions**: Give bets meaningful descriptions (e.g., "Lakers ML", "Sunday Parlay")

## Troubleshooting

**Q: Why isn't my data showing?**
- Make sure you submitted the form (check for success message)
- Refresh the page or rerun the app

**Q: Can I edit data after submitting?**
- Yes! Go to Ledger and use the data editor or update individual bets

**Q: What if I enter the wrong date?**
- Go to Ledger, edit the date in the table, click "Sync Changes"

**Q: Will open bets show in my P&L?**
- No, only settled bets (won/lost) count toward P&L

**Q: Can I delete everything and start over?**
- Yes, but it's risky. Better to just keep going. If needed:
  1. Go to **Ledger** → **Transactions Tab**
  2. Click **Delete All Data** button
  3. Same for Individual Bets if needed

## Need Help?

Check the README.md for detailed documentation of all features.
