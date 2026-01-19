# tabs/equity_tab.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import data_utils as du # Importing the file we created for data utilities

def render_equity_tab(df):
    st.subheader("Equity & Demographic Analysis")

    # --- 1. CONTROLS ---
    # Create a row of controls to select what to analyze
    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            # Map friendly names to your actual dataframe columns
            group_map = {
                "Age Group": "Age_Group",
                "Gender": "Gender",
                "Ethnicity": "Ethnicity", 
                "Deprivation (IMD)": "IMD_Quintile"
            }
            selected_group_label = st.selectbox("Select Demographic Group", list(group_map.keys()))
            selected_group_col = group_map[selected_group_label]

        with c2:
            # Map outcomes to dataframe columns
            outcome_map = {
                "Time to Triage (Mins)": "Time_to_Triage_Mins",
                "Time to First Pain Score (Mins)": "Time_to_PS1_Mins",
                "Time to First Analgesia (Mins)": "Time_to_A1_Mins",
                "Time to Second Pain Score after Analgesia (Mins)": "A1_to_PS2_Mins"
            }
            selected_outcome_label = st.selectbox("Select Clinical Outcome", list(outcome_map.keys()))
            selected_outcome_col = outcome_map[selected_outcome_label]

    st.divider()

    # --- 2. VISUALIZATION COLUMNS ---
    col_dist, col_outcome = st.columns(2)

    # --- COLUMN 1: POPULATION DISTRIBUTION ---
    with col_dist:
        st.markdown(f"#### Distribution by {selected_group_label}")
        
        # Prepare data counts
        dist_data = df[selected_group_col].value_counts().reset_index()
        dist_data.columns = [selected_group_col, 'Count']
        
        # Sort logic: if IMD or Age, we usually want them sorted naturally, not by count
        if selected_group_label in ["Age Group", "Deprivation (IMD)"]:
            dist_data = dist_data.sort_values(selected_group_col)
            
            # Logic for Chart Type
            if selected_group_label == "Age Group":
                # Check if there are any patients under 15
                under_15_count = dist_data[dist_data[selected_group_col].str.contains('0-')]['Count'].sum()
                if under_15_count > 0:
                    # Add information bar for patients under 15
                    st.info(f"Note: {under_15_count} patient(s) found in the 0-15 age group.")
                    
                # Bar chart for Age (ordinal data)
                fig_dist = px.bar(
                    dist_data, 
                    x=selected_group_col, 
                    y='Count',
                    text='Count',
                    color=selected_group_col,
                    title=f"Patient Count by {selected_group_label}",
                )
                
            elif selected_group_label == "Deprivation (IMD)":
                # Bar chart for IMD (ordinal data)
                fig_dist = px.bar(
                    dist_data, 
                    x=selected_group_col, 
                    y='Count',
                    text='Count',
                    color=selected_group_col,
                    title=f"Patient Count by {selected_group_label}",
                )
                
        else:
            # Pie chart for nominal data (Gender, Ethnicity, etc.)
            fig_dist = px.pie(
                dist_data, 
                names=selected_group_col, 
                values='Count', 
                hole=0.4,
                title=f"Breakdown by {selected_group_label}"
            )
            fig_dist.update_traces(textposition='inside', textinfo='percent+label')

        st.plotly_chart(fig_dist, use_container_width=True)


    # --- COLUMN 2: EQUITY OUTCOME ANALYSIS ---
    with col_outcome:
        st.markdown(f"#### {selected_outcome_label} Analysis")
        
        # Filter Data: Remove Unknowns/NaNs for cleaner box plots
        clean_mask = (df[selected_group_col] != 'Unknown') & (df[selected_group_col].notna()) & (df[selected_outcome_col].notna())
        plot_data = df[clean_mask].copy()

        # Sort if necessary (essential for Age/IMD to appear in order on x-axis)
        if selected_group_label in ["Age Group", "Deprivation (IMD)"]:
            plot_data = plot_data.sort_values(selected_group_col)

        # Box Plot
        fig_equity = px.box(
            plot_data,
            x=selected_group_col,
            y=selected_outcome_col,
            color=selected_group_col,
            points="outliers", # or 'all' to see distribution
            title=f"{selected_outcome_label} Distribution"
        )
        st.plotly_chart(fig_equity, use_container_width=True)

        # --- STATISTICAL TEST ---
        st.markdown("##### Statistical Significance")
        
        # Calculate stats using the utility
        stats_result = du.calculate_stats(plot_data, selected_group_col, selected_outcome_col)
        
        if stats_result['p_value'] is not None:
            # Dynamic formatting based on result
            col_res, col_pval = st.columns([3, 1])
            
            with col_res:
                if stats_result['significant']:
                    st.error(f"⚠️ {stats_result['message']}")
                    st.caption(f"There is a statistically significant difference in wait times based on {selected_group_label}.")
                else:
                    st.success(f"✅ {stats_result['message']}")
                    st.caption("No evidence of inequality in wait times for this group.")
            
            with col_pval:
                st.metric("P-Value", f"{stats_result['p_value']:.4f}")
                st.caption(f"Test: {stats_result['test']}")
        else:
            st.warning("Insufficient data to run statistical tests.")