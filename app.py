import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

# ============================================================================
# DATABASE INITIALIZATION & UTILITIES
# ============================================================================

DB_PATH = "bet_tracker.db"

def init_db():
    """Initialize SQLite database with transactions table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            event_date DATE NOT NULL,
            book TEXT NOT NULL,
            total_risked REAL NOT NULL DEFAULT 0,
            total_won REAL NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_date, book)
        )
    """)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def upsert_transaction(event_date, book, risked, won):
    """
    Insert or update a transaction using UPSERT logic.
    Increments total_risked and total_won for the given (event_date, book) pair.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO transactions (event_date, book, total_risked, total_won, last_updated)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(event_date, book) DO UPDATE SET
            total_risked = total_risked + ?,
            total_won = total_won + ?,
            last_updated = CURRENT_TIMESTAMP
    """, (event_date, book, risked, won, risked, won))
    
    conn.commit()
    conn.close()

def get_all_transactions():
    """Fetch all transactions from the database as a DataFrame."""
    conn = get_db_connection()
    query = "SELECT event_date, book, total_risked, total_won, last_updated FROM transactions ORDER BY event_date DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        df['event_date'] = pd.to_datetime(df['event_date'])
        df['net_profit'] = df['total_won'] - df['total_risked']
    
    return df

def delete_transaction(event_date, book):
    """Delete a transaction by event_date and book."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions WHERE event_date = ? AND book = ?", (event_date, book))
    
    conn.commit()
    conn.close()

def update_transaction(event_date, book, total_risked, total_won):
    """Update a transaction with new values."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE transactions 
        SET total_risked = ?, total_won = ?, last_updated = CURRENT_TIMESTAMP
        WHERE event_date = ? AND book = ?
    """, (total_risked, total_won, event_date, book))
    
    conn.commit()
    conn.close()

# ============================================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Betting Tracker",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎰 Rapid-Entry Betting Tracker")

# Initialize database on first load
init_db()

# ============================================================================
# TAB 1: RAPID ENTRY FORM
# ============================================================================

tab1, tab2, tab3 = st.tabs(["📝 Rapid Entry", "📊 Analytics", "📋 Ledger"])

with tab1:
    st.header("Quick Bet Entry")
    st.write("Tab through fields and press Enter to submit quickly.")
    
    # Create form for batch submission
    with st.form("bet_entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            event_date = st.date_input(
                "Event Date",
                value=datetime.now().date(),
                label_visibility="collapsed"
            )
            risked_amount = st.number_input(
                "Risked Amount ($)",
                min_value=0.0,
                step=0.01,
                value=0.0,
                label_visibility="collapsed"
            )
        
        with col2:
            book_name = st.text_input(
                "Sportsbook Name",
                placeholder="e.g., DraftKings, FanDuel, BetMGM",
                label_visibility="collapsed"
            )
            won_amount = st.number_input(
                "Won Amount ($)",
                min_value=0.0,
                step=0.01,
                value=0.0,
                label_visibility="collapsed"
            )
        
        # Real-time preview of net profit
        net_profit_preview = won_amount - risked_amount
        if net_profit_preview >= 0:
            st.success(f"**Net Profit: +${net_profit_preview:.2f}**", icon="✅")
        else:
            st.error(f"**Net Loss: ${net_profit_preview:.2f}**", icon="❌")
        
        # Submit button
        submitted = st.form_submit_button("📤 Submit Bet", use_container_width=True)
        
        if submitted:
            if not book_name.strip():
                st.error("Please enter a sportsbook name.")
            elif risked_amount == 0 and won_amount == 0:
                st.error("Please enter at least one amount (Risked or Won).")
            else:
                # Perform UPSERT operation
                upsert_transaction(
                    str(event_date),
                    book_name.strip(),
                    risked_amount,
                    won_amount
                )
                st.success(f"✅ Bet recorded: {book_name} on {event_date}")
    
    # Display recent entries
    st.subheader("Recent Entries")
    recent_df = get_all_transactions()
    
    if not recent_df.empty:
        display_df = recent_df.copy()
        display_df['event_date'] = display_df['event_date'].dt.strftime('%Y-%m-%d')
        display_df = display_df[['event_date', 'book', 'total_risked', 'total_won', 'net_profit']].head(10)
        display_df.columns = ['Date', 'Book', 'Risked ($)', 'Won ($)', 'Net Profit ($)']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No bets recorded yet. Start by entering your first bet above.")

# ============================================================================
# TAB 2: ANALYTICS DASHBOARD
# ============================================================================

with tab2:
    st.header("📊 Analytics Dashboard")
    
    df = get_all_transactions()
    
    if not df.empty:
        # Calculate KPIs
        total_risked = df['total_risked'].sum()
        total_won = df['total_won'].sum()
        total_profit = total_won - total_risked
        roi = (total_profit / total_risked * 100) if total_risked > 0 else 0
        
        # Display KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Risked", f"${total_risked:,.2f}")
        with col2:
            st.metric("Total Won", f"${total_won:,.2f}")
        with col3:
            if total_profit >= 0:
                st.metric("Total Profit", f"${total_profit:,.2f}", delta=f"+{roi:.1f}% ROI")
            else:
                st.metric("Total Loss", f"${total_profit:,.2f}", delta=f"{roi:.1f}% ROI")
        with col4:
            st.metric("ROI %", f"{roi:.2f}%")
        
        st.divider()
        
        # Cumulative PnL Graph
        st.subheader("Cumulative Profit/Loss Over Time")
        
        # Prepare data for cumulative chart
        cumulative_df = df.copy()
        cumulative_df = cumulative_df.sort_values('event_date')
        cumulative_df['cumulative_profit'] = (cumulative_df['total_won'] - cumulative_df['total_risked']).cumsum()
        
        fig_cumulative = go.Figure()
        fig_cumulative.add_trace(go.Scatter(
            x=cumulative_df['event_date'],
            y=cumulative_df['cumulative_profit'],
            mode='lines+markers',
            name='Cumulative Profit',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=6)
        ))
        
        fig_cumulative.update_layout(
            xaxis_title="Date",
            yaxis_title="Cumulative Profit ($)",
            hovermode='x unified',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig_cumulative, use_container_width=True)
        
        # Book Performance Chart
        st.subheader("Performance by Sportsbook")
        
        book_performance = df.groupby('book').agg({
            'total_risked': 'sum',
            'total_won': 'sum'
        }).reset_index()
        book_performance['net_profit'] = book_performance['total_won'] - book_performance['total_risked']
        book_performance = book_performance.sort_values('net_profit', ascending=True)
        
        fig_books = go.Figure()
        
        colors = ['#d62728' if x < 0 else '#2ca02c' for x in book_performance['net_profit']]
        
        fig_books.add_trace(go.Bar(
            y=book_performance['book'],
            x=book_performance['net_profit'],
            orientation='h',
            marker=dict(color=colors),
            text=book_performance['net_profit'].apply(lambda x: f"${x:.2f}"),
            textposition='outside',
            name='Net Profit'
        ))
        
        fig_books.update_layout(
            xaxis_title="Net Profit ($)",
            yaxis_title="Sportsbook",
            hovermode='y',
            template='plotly_white',
            height=400,
            showlegend=False
        )
        
        st.plotly_chart(fig_books, use_container_width=True)
        
        # Detailed Book Statistics
        st.subheader("Detailed Book Statistics")
        
        stats_df = book_performance.copy()
        stats_df['ROI %'] = (stats_df['net_profit'] / stats_df['total_risked'] * 100).round(2)
        stats_df = stats_df[['book', 'total_risked', 'total_won', 'net_profit', 'ROI %']]
        stats_df.columns = ['Book', 'Total Risked ($)', 'Total Won ($)', 'Net Profit ($)', 'ROI (%)']
        
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    else:
        st.info("No data yet. Start recording bets in the Rapid Entry tab to see analytics.")

# ============================================================================
# TAB 3: DATA LEDGER & MANAGEMENT
# ============================================================================

with tab3:
    st.header("📋 Transaction Ledger")
    st.write("View, edit, and manage all recorded bets.")
    
    df = get_all_transactions()
    
    if not df.empty:
        # Display data editor
        st.subheader("Edit Transactions")
        
        edit_df = df.copy()
        edit_df['event_date'] = edit_df['event_date'].dt.strftime('%Y-%m-%d')
        edit_df['net_profit'] = edit_df['total_won'] - edit_df['total_risked']
        
        display_cols = ['event_date', 'book', 'total_risked', 'total_won', 'net_profit']
        edit_df = edit_df[display_cols]
        edit_df.columns = ['Date', 'Book', 'Risked ($)', 'Won ($)', 'Net Profit ($)']
        
        edited_df = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            key="transaction_editor",
            num_rows="fixed"
        )
        
        # Sync changes button
        if st.button("💾 Sync Changes to Database", use_container_width=True):
            try:
                # Clear all transactions and reinsert
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transactions")
                
                for idx, row in edited_df.iterrows():
                    cursor.execute("""
                        INSERT INTO transactions (event_date, book, total_risked, total_won, last_updated)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (row['Date'], row['Book'], row['Risked ($)'], row['Won ($)']))
                
                conn.commit()
                conn.close()
                st.success("✅ Changes saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving changes: {e}")
        
        # Delete functionality
        st.subheader("Delete Transactions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_date_str = st.selectbox(
                "Select Date to Delete",
                options=sorted(edit_df['Date'].unique(), reverse=True),
                key="delete_date_select"
            )
        
        with col2:
            # Filter books by selected date
            books_for_date = edited_df[edited_df['Date'] == selected_date_str]['Book'].unique().tolist()
            selected_book = st.selectbox(
                "Select Book to Delete",
                options=books_for_date,
                key="delete_book_select"
            )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Delete Selected Transaction", use_container_width=True, type="secondary"):
                delete_transaction(selected_date_str, selected_book)
                st.success(f"✅ Deleted transaction for {selected_book} on {selected_date_str}")
                st.rerun()
        
        with col2:
            if st.button("⚠️ Delete All Data", use_container_width=True, type="secondary"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transactions")
                conn.commit()
                conn.close()
                st.success("✅ All data cleared. Starting fresh!")
                st.rerun()
    
    else:
        st.info("No transactions recorded yet. Start by entering bets in the Rapid Entry tab.")

# ============================================================================
# SIDEBAR: INFO & SETTINGS
# ============================================================================

with st.sidebar:
    st.subheader("ℹ️ About This App")
    st.write(
        """
        **Rapid-Entry Betting Tracker**
        
        A lightweight, keyboard-centric tool for tracking your sports bets 
        across multiple sportsbooks.
        
        **Features:**
        - ⚡ Fast, Tab-based entry form
        - 📊 Real-time analytics & ROI tracking
        - 📈 Visual performance charts
        - 💾 Local SQLite database
        
        **How to Use:**
        1. Enter bets quickly in the "Rapid Entry" tab
        2. View analytics in the "Analytics" tab
        3. Manage data in the "Ledger" tab
        """
    )
    
    st.divider()
    
    # Database info
    st.subheader("📁 Database Info")
    
    if Path(DB_PATH).exists():
        db_size_kb = Path(DB_PATH).stat().st_size / 1024
        st.write(f"**Status:** ✅ Active")
        st.write(f"**File:** `{DB_PATH}`")
        st.write(f"**Size:** {db_size_kb:.2f} KB")
    else:
        st.write(f"**Status:** ✅ Ready to create")
    
    # Quick stats
    if not df.empty:
        st.divider()
        st.subheader("📈 Quick Stats")
        total_profit = (df['total_won'] - df['total_risked']).sum()
        total_risked = df['total_risked'].sum()
        roi = (total_profit / total_risked * 100) if total_risked > 0 else 0
        
        st.metric("Overall Profit", f"${total_profit:,.2f}")
        st.metric("Total Risked", f"${total_risked:,.2f}")
        st.metric("ROI", f"{roi:.2f}%")
