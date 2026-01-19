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

# --- SIDEBAR: CONFIG & UPLOAD ---
with st.sidebar:
    st.header("Upload New Data")
    uploaded_file = st.file_uploader("Upload Monthly Excel Export", type=['xlsx'])
    
    st.divider()
    st.info("Upload the raw Excel export from the ED system. The dashboard will automatically clean and process the data.")

# --- MAIN LOGIC ---
if uploaded_file:
    # 1. Load Reference Data (IMD)
    try:
        # Update this path to where your big CSV actually lives
        imd_path = r"C:\Users\sthug\Documents\PainQIP Local\Data\Indices_of_Deprivation-2025-data_download-file-postcode_join.csv"
        
        with st.spinner("Loading IMD Reference Data..."):
            imd_df = du.load_imd_data(imd_path)
            st.success("✅ IMD Data Loaded Automatically")
            
    except FileNotFoundError:
        imd_df = None
        st.warning("⚠️ IMD file not found at the specified path. Deprivation analysis will be skipped.")

    # 2. Process Main Data
    # We use a spinner so the user knows something is happening
    with st.spinner("Processing data..."):
        df = du.process_monthly_data(uploaded_file, imd_df)
    
    # Ensure df is a pandas DataFrame
    if df is not None:
        if not isinstance(df, pd.DataFrame):
            # If df is a tuple, convert it to DataFrame
            if isinstance(df, tuple):
                # Convert tuple to DataFrame - adjust column names as needed
                df = pd.DataFrame(df[0], columns=df[1])
            else:
                raise TypeError("df must be a pandas DataFrame or a tuple with data and column names")
    
    if df is not None:
        # --- TAB STRUCTURE ---
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Headlines", "⏱️ Time Analysis", "👥 Demographics", "📉 Best Practice"])

        # --- TAB 1: HEADLINES ---
        with tab1:
            st.subheader("Key Performance Indicators")
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_patients = len(df)
            median_triage = df['Time_to_Triage_Mins'].median()
            median_analgesia = df['Time_to_A1_Mins'].median()
            perc_analgesia_15 = (len(df[df['Time_to_A1_Mins'] <= 15]) / total_patients) * 100

            col1.metric("Total Patients", total_patients)
            col2.metric("Median Time to Triage", f"{median_triage:.0f} mins")
            col3.metric("Median Time to Analgesia", f"{median_analgesia:.0f} mins")
            col4.metric("% Analgesia < 15 mins", f"{perc_analgesia_15:.1f}%")

            st.divider()
            
            # Pain Score Improvement (Box Plot)
            st.markdown("#### Pain Score Improvement")
            fig_imp = px.box(df, x='Pain_Score_Improvement', 
                             title="Change in Pain Score (Second - First)",
                             labels={'Pain_Score_Improvement': 'Change in Score'})
            st.plotly_chart(fig_imp, use_container_width=True)

        # --- TAB 2: TIME ANALYSIS ---
        with tab2:
            st.subheader("Time Interval Distribution")
            
            # Select metric to view
            metric_choice = st.selectbox("Select Time Metric", 
                ['Time_to_Triage_Mins', 'Time_to_PS1_Mins', 'Time_to_A1_Mins', 'A1_to_PS2_Mins'])

            # Create a note about negative values for A1_to_PS2_Mins
            if metric_choice == 'A1_to_PS2_Mins':
                df_filtered = df[df[metric_choice] >= 0]
                negative_count = df[df[metric_choice] < 0].shape[0]
                if negative_count > 0:
                    st.info(f"Note: {negative_count} records have negative values in {metric_choice}, indicating patients received their first dose of analgesia after their second pain score.")
            else:
                df_filtered = df
            
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
                x_range = list(hist.layout.xaxis.range) if hist.layout.xaxis.range else [df_filtered[metric_choice].min(), df_filtered[metric_choice].max()]
                        
            # Update axes labels and ranges
            fig.update_xaxes(title_text="Minutes", row=1, col=1, range=x_range)
            fig.update_yaxes(title_text="Count", row=1, col=1)
            fig.update_xaxes(title_text="Minutes", row=2, col=1, range=x_range)
            fig.update_yaxes(title_text="", row=2, col=1)
            
            st.plotly_chart(fig, use_container_width=True)

        # --- TAB 3: DEMOGRAPHICS & EQUITY ---
        import equity_tab as et
        with tab3:
            et.render_equity_tab(df)

        # --- TAB 4: BEST PRACTICE ---
        with tab4:
            st.subheader("Best Practice Compliance")
            
            # Sankey Diagram Data Prep
            bp_counts = df['Best_Practice'].value_counts()
            
            col_bp1, col_bp2 = st.columns([1, 2])
            
            with col_bp1:
                st.dataframe(bp_counts)
                st.metric("Compliance Rate", f"{(len(df[df['Best_Practice']=='Yes'])/len(df)*100):.1f}%")

            with col_bp2:
                # Call calculate_best_practice and get both the updated df and sankey data
                df_updated, sankey_data = calculate_best_practice(df)  # Changed: df_updated instead of df

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

    else:
        st.error("Data processing failed. Please check the file format.")

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