import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import data_utils as du  # Importing your module (ensure file is named data_utils.py or change this import)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="ED Pain Audit Dashboard", layout="wide")

st.title("🏥 Emergency Department Pain Management Audit")
st.markdown("### Monthly Quality Improvement Report")

# --- CONFIG & UPLOAD ---
HISTORY_FOLDER = r"C:\Users\sthug\Documents\PainQIP Local\History_Data"
IMD_PATH = r"C:\Users\sthug\Documents\PainQIP Local\Data\Indices_of_Deprivation-2025-data_download-file-postcode_join.csv"

# --- 1. LOAD DATA ---
@st.cache_data
def get_all_history(folder, _imd_df):
    return du.load_history_from_folder(folder, _imd_df)

# Load IMD Reference
try:
    imd_df = du.load_imd_data(IMD_PATH)
except:
    imd_df = None

# Load History
with st.spinner("Loading Audit History..."):
    history_df = get_all_history(HISTORY_FOLDER, imd_df)

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Audit Controls")
    
    # A. Upload New Data
    st.subheader("1. Input Data")
    uploaded_file = st.file_uploader("Upload Monthly Export", type=['xlsx'])
    
    # B. Combine Data Sources
    # We start with the history dataframe
    full_df = history_df.copy() if not history_df.empty else pd.DataFrame()
    
    # If user uploads a file, process it and append it to full_df
    if uploaded_file:
        with st.spinner("Processing upload..."):
            new_df = du.process_monthly_data(uploaded_file, imd_df)
            
            if new_df is not None:
                # Add source tag to identify where data came from
                new_df['_source'] = 'upload' 
                history_df['_source'] = 'history'
                
                # Combine
                full_df = pd.concat([full_df, new_df], ignore_index=True)
                
                # OPTIONAL: Save to history button
                if st.button("💾 Save Upload to History"):
                    save_path = os.path.join(HISTORY_FOLDER, uploaded_file.name)
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success("Saved! Reload app to see it in history.")
                    st.cache_data.clear() # Clear cache so next reload picks up the new file

    # C. "Time Machine" Selector
    st.subheader("2. Select Report Month")
    
    if not full_df.empty:
        # Get unique months from the 'Report_Month' column created in data_utils
        # Format usually 'YYYY-MM'
        available_months = sorted(full_df['Report_Month'].unique(), reverse=True)
        
        # The dropdown defaults to the latest month (index 0)
        selected_month_str = st.selectbox("View Dashboard For:", available_months)
    else:
        selected_month_str = None
        st.warning("No data found. Upload a file or check history folder.")

# --- MAIN DASHBOARD LOGIC ---
if selected_month_str and not full_df.empty:
    
    # 1. Define Dates
    # Convert string (e.g., "2025-10") to a Period object
    selected_period = pd.Period(selected_month_str)
    
    # Calculate the comparison window (The 3 months BEFORE the selected month)
    comp_start = selected_period - 3
    comp_end = selected_period - 1
    
    st.header(f"🏥 Audit Report: {selected_period.strftime('%B %Y')}")
    st.caption(f"Comparing against performance from: {comp_start.strftime('%b %Y')} - {comp_end.strftime('%b %Y')}")

    # 2. Filter Data
    # Current Data: Matches the selected month
    current_df = full_df[full_df['Report_Month'] == selected_month_str].copy()
    
    # Historical Data: Matches the 3-month window
    # We look for strings that fall into our calculated range
    # (Using Period objects for comparison is safer than strings)
    full_df['Period_Obj'] = full_df['Report_Month'].apply(pd.Period)
    
    history_window_df = full_df[
        (full_df['Period_Obj'] >= comp_start) & 
        (full_df['Period_Obj'] <= comp_end)
    ].copy()

    # 3. Calculate Comparisons
    # Calculate baselines from the history window
    if not history_window_df.empty:
        baseline_triage = history_window_df['Time_to_Triage_Mins'].median()
        baseline_analgesia = history_window_df['Time_to_A1_Mins'].median()
        baseline_pct_15 = (len(history_window_df[history_window_df['Time_to_A1_Mins'] < 15]) / len(history_window_df)) * 100
        has_baseline = True
    else:
        baseline_triage = 0
        baseline_analgesia = 0
        baseline_pct_15 = 0
        has_baseline = False

    # 4. Render Tabs (Updated to include Data Summary)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Headlines", 
        "⏱️ Time Analysis", 
        "👥 Demographics", 
        "⭐ Best Practice", 
        "📈 Trends",
        "📋 Data Summary"
    ])

    with tab1:
        st.subheader("Key Performance Indicators")
        col1, col2, col3, col4 = st.columns(4)
        
        # Calculate Current Stats
        curr_triage = current_df['Time_to_Triage_Mins'].median()
        curr_analgesia = current_df['Time_to_A1_Mins'].median()
        curr_pct_15 = (len(current_df[current_df['Time_to_A1_Mins'] < 15]) / len(current_df)) * 100
        
        # Render Metrics with Comparisons
        col1.metric("Total Patients", len(current_df))
        
        col2.metric("Median Triage", f"{curr_triage:.0f} m", 
                    f"{curr_triage - baseline_triage:.1f} m" if has_baseline else None, 
                    delta_color="inverse")
                    
        col3.metric("Median Analgesia", f"{curr_analgesia:.0f} m", 
                    f"{curr_analgesia - baseline_analgesia:.1f} m" if has_baseline else None, 
                    delta_color="inverse")
                    
        col4.metric("% Analgesia < 15m", f"{curr_pct_15:.1f}%", 
                    f"{curr_pct_15 - baseline_pct_15:.1f}%" if has_baseline else None)
        
        st.divider()
        st.info("Data displayed in other tabs reflects the **Selected Month** only. See 'Trends' tab for historical view.")

    # --- TAB 2: TIME ANALYSIS ---
    with tab2:
        st.subheader("Time Interval Distribution")
        
        # Select metric to view
        metric_choice = st.selectbox("Select Time Metric", 
            ['Time_to_Triage_Mins', 'Time_to_PS1_Mins', 'Time_to_A1_Mins', 'A1_to_PS2_Mins'])
        
        # Calculate and display the percentage of patients with valid data for the selected metric
        total_pts = len(current_df)
        if total_pts > 0:
            # Count how many patients have data for the currently selected metric
            valid_count = current_df[metric_choice].notna().sum()
            pct_complete = (valid_count / total_pts) * 100
            
            # Map the database column names to user-friendly labels
            metric_labels = {
                'Time_to_Triage_Mins': 'Patients Triaged',
                'Time_to_PS1_Mins': 'Received 1st Pain Score',
                'Time_to_A1_Mins': 'Received Analgesia',
                'A1_to_PS2_Mins': 'Received 2nd Pain Score'
            }
            display_label = metric_labels.get(metric_choice, 'Data Recorded')
            
            # Display the metric dynamically
            st.metric(display_label, f"{pct_complete:.1f}%", f"{valid_count} of {total_pts} patients", delta_color="off")
            st.divider()
        
        # Create a note about negative values for A1_to_PS2_Mins
        if metric_choice == 'A1_to_PS2_Mins':
            df_filtered = current_df[current_df[metric_choice] >= 0]
            negative_count = current_df[current_df[metric_choice] < 0].shape[0]
            if negative_count > 0:
                st.info(f"Note: {negative_count} records have negative values in {metric_choice}, indicating patients received their first dose of analgesia after their second pain score.")
        else:
            df_filtered = current_df
        
        # Create subplots
        from plotly.subplots import make_subplots
        import plotly.graph_objects as go
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Histogram', 'Box Plot'),
            vertical_spacing=0.2
        )
        
        # Histogram
        if metric_choice == 'A1_to_PS2_Mins':
            # Separate data for moderate vs severe pain
            df_moderate = df_filtered[(df_filtered[metric_choice] >= 0) & (df_filtered['First Pain Score'] == 'Mod Pain')]
            df_severe = df_filtered[(df_filtered[metric_choice] >= 0) & (df_filtered['First Pain Score'] == 'Sev Pain')]
            
            # Create histogram with different colors for pain severity
            hist_moderate = px.histogram(df_moderate, x=metric_choice, nbins=50, 
                                        color_discrete_sequence=['#3366cc'], opacity=0.7)
            hist_severe = px.histogram(df_severe, x=metric_choice, nbins=50, 
                                        color_discrete_sequence=['#ff6666'], opacity=0.7)
            
            # Add traces to the figure
            for trace in hist_moderate.data:
                trace.name = 'Moderate Pain'
                trace.hovertemplate = "<b>%{data.name}</b><br>Minutes: %{x}<br>Count: %{y}<extra></extra>"
                fig.add_trace(trace, row=1, col=1)
            for trace in hist_severe.data:
                trace.name = 'Severe Pain'
                trace.hovertemplate = "<b>%{data.name}</b><br>Minutes: %{x}<br>Count: %{y}<extra></extra>"
                fig.add_trace(trace, row=1, col=1)
        else:
            hist = px.histogram(df_filtered, x=metric_choice, nbins=50, 
                    color_discrete_sequence=['#3366cc'])
            for trace in hist.data:
                trace.hovertemplate = "<b>Minutes: %{x}</b><br>Count: %{y}<extra></extra>"
                fig.add_trace(trace, row=1, col=1)
        
        # Box plot (horizontal orientation)
        if metric_choice == 'A1_to_PS2_Mins':
            # Create box plots for moderate vs severe pain
            box_moderate = px.box(df_moderate, x=metric_choice, color_discrete_sequence=['#3366cc'])
            box_severe = px.box(df_severe, x=metric_choice, color_discrete_sequence=['#ff6666'])
            
            # Add traces to the figure
            for trace in box_moderate.data:
                current_template = trace.hovertemplate if trace.hovertemplate else ""
                trace.hovertemplate = "<b>%{data.name}</b><br>" + current_template
                fig.add_trace(trace, row=2, col=1)
            for trace in box_severe.data:
                current_template = trace.hovertemplate if trace.hovertemplate else ""
                trace.hovertemplate = "<b>%{data.name}</b><br>" + current_template
                fig.add_trace(trace, row=2, col=1)
        else:
            box = px.box(df_filtered, x=metric_choice, color_discrete_sequence=['#3366cc'])
            for trace in box.data:
                fig.add_trace(trace, row=2, col=1)
        
        # Add the 15 min target line to histogram (for severe pain)
        if metric_choice == 'A1_to_PS2_Mins':
            fig.add_vline(x=15, line_dash="dash", line_color="red", annotation_text="15 min Target (Severe)", annotation=dict(textangle=-90), row=1, col=1)
            fig.add_vline(x=30, line_dash="dash", line_color="orange", annotation_text="30 min Target (Moderate)", annotation=dict(textangle=-90), row=1, col=1)
        else:
            fig.add_vline(x=15, line_dash="dash", line_color="red", annotation_text="15 min Target", row=1, col=1)
        
        # Update layout for consistent sizing and x-axis range
        fig.update_layout(
            height=600, 
            showlegend=True, 
            title_text=f"Distribution: {metric_choice}",
            barmode='overlay',
            boxmode='group'
        )
        
        # Get the x-axis range from the filtered data to ensure consistency
        if metric_choice == 'A1_to_PS2_Mins':
            x_range = [0, df_filtered[metric_choice].max()]
        else:
            x_range = [df_filtered[metric_choice].min(), df_filtered[metric_choice].max()]
                    
        # Update axes labels and ranges
        fig.update_xaxes(title_text="Minutes", row=1, col=1, range=x_range)
        fig.update_yaxes(title_text="Count", row=1, col=1)
        fig.update_xaxes(title_text="Minutes", row=2, col=1, range=x_range)
        fig.update_yaxes(title_text="", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)

    # --- TAB 3: DEMOGRAPHICS & EQUITY ---
    try:
        import equity_tab as et
        with tab3:
            et.render_equity_tab(current_df)
    except ImportError:
        with tab3:
            st.warning("Equity analysis module not found. Please ensure 'equity_tab.py' exists.")

    # --- TAB 4: BEST PRACTICE ---
    with tab4:
        st.subheader("Best Practice Compliance")
        
        # Sankey Diagram Data Prep
        bp_counts = current_df['Best_Practice'].value_counts()
        
        col_bp1, col_bp2 = st.columns([1, 2])
        
        with col_bp1:
            st.dataframe(bp_counts)
            st.metric("Compliance Rate", f"{(len(current_df[current_df['Best_Practice']=='Yes'])/len(current_df)*100):.1f}%")

        with col_bp2:
            # Call calculate_best_practice and get both the updated df and sankey data
            df_updated, sankey_data = du.calculate_best_practice(current_df)  # Changed: df_updated instead of df

            # Create Sankey chart
            fig = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=sankey_data['labels'],
                    color="blue"
                ),
                link=dict(
                    source=sankey_data['source'],
                    target=sankey_data['target'],
                    value=sankey_data['value']
                )
            )])

            fig.update_layout(title_text="Patient Flow through Pain Management Best Practice Criteria", font_size=10)
            st.plotly_chart(fig)

    # --- TAB 5: TRENDS ---
    with tab5:
        # Trends Tab: Show the trend line up to the selected month
        st.subheader("Historical Context")
        
        # We might want to see the trend leading UP TO the selected month
        # So filter the full dataset to include everything <= selected_period
        trend_view_df = full_df[full_df['Period_Obj'] <= selected_period].copy()
        
        # Create Trend Chart (same logic as before)
        monthly_stats = trend_view_df.groupby('Report_Month')[['Time_to_Triage_Mins', 'Time_to_PS1_Mins', 'Time_to_A1_Mins']].median().reset_index()
        fig_trend = px.line(monthly_stats, x='Report_Month', y=['Time_to_Triage_Mins','Time_to_PS1_Mins', 'Time_to_A1_Mins'], markers=True)
        st.plotly_chart(fig_trend)

    # --- TAB 6: DATA SUMMARY ---
    with tab6:
        st.subheader("📋 Executive Summary Table")
        st.markdown("A quick tabular overview of the key clinical milestones (median minutes) for the selected month compared to the previous 3-month baseline.")
        
        # Helper function to safely format medians
        def format_median(series):
            val = series.median()
            return f"{val:.1f}" if pd.notna(val) else "N/A"

        # Construct the table data
        summary_data = {
            "Metric": [
                "Time to Triage",
                "Time to First Pain Score",
                "Time to First Analgesia",
                "Time to Second Pain Score"
            ],
            "Selected Month Median (Mins)": [
                format_median(current_df['Time_to_Triage_Mins']),
                format_median(current_df['Time_to_PS1_Mins']),
                format_median(current_df['Time_to_A1_Mins']),
                format_median(current_df['Time_to_PS2_Mins'])
            ]
        }

        # Add baseline data if it exists
        if has_baseline:
            summary_data["Previous 3-Month Median (Mins)"] = [
                format_median(history_window_df['Time_to_Triage_Mins']),
                format_median(history_window_df['Time_to_PS1_Mins']),
                format_median(history_window_df['Time_to_A1_Mins']),
                format_median(history_window_df['Time_to_PS2_Mins'])
            ]
            
            # Optional: Calculate the difference
            summary_data["Difference"] = [
                f"{float(summary_data['Selected Month Median (Mins)'][i]) - float(summary_data['Previous 3-Month Median (Mins)'][i]):+.1f}" 
                if summary_data['Selected Month Median (Mins)'][i] != "N/A" and summary_data['Previous 3-Month Median (Mins)'][i] != "N/A" 
                else "N/A"
                for i in range(4)
            ]

        # Convert to DataFrame and display
        summary_df = pd.DataFrame(summary_data)
        
        # Use st.dataframe for a nice interactive table, or st.table for a completely static one
        st.dataframe(summary_df, hide_index=True, use_container_width=True)
        
        # Add an easy download button for the summary
        csv = summary_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download Summary as CSV",
            data=csv,
            file_name=f"pain_audit_summary_{selected_month_str}.csv",
            mime="text/csv",
        )
else:
    # Landing page content
    st.markdown("""
    ### Welcome
    Please upload your monthly data file from the sidebar to begin analysis.
    
    **Required Columns:**
    * Age
    * Gender
    * Ethnicity
    * Arrival DTTM
    * Triage DTTM
    * First Pain Score DTTM
    * First Analgesia DTTM
    * Second Pain Score DTTM
    * Postcode
    """)
