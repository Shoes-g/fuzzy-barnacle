import pandas as pd
import numpy as np
import scipy.stats as stats

# --- CONFIGURATION ---
COLS_TO_DROP = ['Surname', 'Forename']
IMD_COLS = [
    'Postcode', 
    'LSOA containing postcode - Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)'
]

def load_imd_data(filepath):
    """Loads and standardizes the IMD reference data."""
    try:
        df_imd = pd.read_csv(filepath, usecols=IMD_COLS)
        df_imd.rename(columns={
            'Postcode': 'Postcode_Gov',
            'LSOA containing postcode - Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)': 'IMD_Decile'
        }, inplace=True)
        df_imd['Join_Key'] = df_imd['Postcode_Gov'].astype(str).str.upper().str.replace(' ', '')
        return df_imd
    except Exception as e:
        print(f"Error loading IMD data: {e}")
        return pd.DataFrame()

def map_quintile(decile):
    """Maps IMD Decile (1-10) to Quintile (1-5)."""
    if pd.isna(decile): return 'Unknown'
    if decile <= 2: return '1 - Most Deprived'
    if decile <= 4: return '2'
    if decile <= 6: return '3'
    if decile <= 8: return '4'
    return '5 - Least Deprived'

def load_and_clean_pain_data(filepath):
    """Load and perform initial cleaning of pain data."""
    df = pd.read_excel(filepath, header=4)
    df.columns = df.columns.str.strip()
    df = df.drop(columns=[c for c in COLS_TO_DROP if c in df.columns], errors='ignore')
    return df

def create_join_keys(df):
    """Create join keys for merging with IMD data."""
    df['Join_Key'] = df['Postcode'].astype(str).str.upper().str.replace(' ', '')
    return df

def merge_with_imd_data(df, imd_df):
    """Merge main data with IMD information."""
    if imd_df is not None and not imd_df.empty:
        df = df.merge(imd_df[['Join_Key', 'IMD_Decile']], on='Join_Key', how='left')
        df['IMD_Quintile'] = df['IMD_Decile'].apply(map_quintile)
        df = df.drop(columns=['Postcode', 'Join_Key', 'Postcode_Gov'], errors='ignore')
    else:
        df['IMD_Quintile'] = 'Unknown'
    return df

def process_monthly_data(filepath, imd_df):
    """Main function to process monthly pain data."""
    try:
        # Load and clean data
        df = load_and_clean_pain_data(filepath)
        
        # Convert date columns
        date_cols = ['Arrival DTTM', 'Triage DTTM', 'First Pain Score DTTM', 
                    'First Analgesia DTTM', 'Second Pain Score DTTM']
        df = convert_date_columns(df, date_cols)
        
        # Create join keys
        df = create_join_keys(df)
        
        # Merge with IMD data
        df = merge_with_imd_data(df, imd_df)
        
        # Calculate time intervals
        df = calculate_time_intervals(df)
        
        # Return the processed DataFrame
        return df
        
    except Exception as e:
        print(f"Error processing data: {e}")
        return None
    
def convert_date_columns(df, date_cols):
    """Convert specified columns to datetime."""
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format='%d-%b-%y %H:%M', errors='coerce')
    return df

def calculate_time_intervals(df):
    """Calculate time intervals between key events."""
    # Check if required columns exist
    required_date_cols = ['Arrival DTTM', 'Triage DTTM', 'First Pain Score DTTM', 
                         'First Analgesia DTTM', 'Second Pain Score DTTM']
    
    # Verify all required date columns exist
    missing_cols = [col for col in required_date_cols if col not in df.columns]
    if missing_cols:
        print(f"Warning: Missing date columns: {missing_cols}")
        return df
    
    if 'Arrival DTTM' in df.columns:
        df['Time_to_Triage_Mins'] = (df['Triage DTTM'] - df['Arrival DTTM']).dt.total_seconds() / 60
        df['Time_to_PS1_Mins'] = (df['First Pain Score DTTM'] - df['Arrival DTTM']).dt.total_seconds() / 60
        df['Time_to_A1_Mins'] = (df['First Analgesia DTTM'] - df['Arrival DTTM']).dt.total_seconds() / 60
        df['Time_to_PS2_Mins'] = (df['Second Pain Score DTTM'] - df['Arrival DTTM']).dt.total_seconds() / 60
        df['A1_to_PS2_Mins'] = (df['Second Pain Score DTTM'] - df['First Analgesia DTTM']).dt.total_seconds() / 60
        df['PS2_to_A1_Mins'] = (df['First Analgesia DTTM'] - df['Second Pain Score DTTM']).dt.total_seconds() / 60
    return df

def calculate_pain_scores(df):
    """Calculate numeric pain scores and improvements."""
    score_map = {'No Pain': 0, 'Mild Pain': 1, 'Mod Pain': 2, 'Sev Pain': 3}
    df['First_Score_Num'] = df['First Pain Score'].map(score_map)
    df['Second_Score_Num'] = df['Second Pain Score'].map(score_map)
    df['Pain_Score_Improvement'] = df['Second_Score_Num'] - df['First_Score_Num']
    return df

def create_age_groups(df):
    """Create age group categories."""
    df['Age'] = pd.to_numeric(df['Age'], errors='coerce')
    age_bins = [0, 15, 25, 35, 45, 55, 65, 75, 85, 95, 150]
    age_labels = ['0-15', '15-25', '25-35', '35-45', '45-55', '55-65', '65-75', '75-85', '85-95', '95+']
    df['Age_Group'] = pd.cut(df['Age'], bins=age_bins, labels=age_labels, right=False)
    return df

def calculate_best_practice(df):
    """Calculate best practice compliance based on clinical guidelines."""
    # "Yes" if:
    # (PS1 <= 15) AND
    # ( (Mod Pain AND A1 <= 15 AND PS2_diff <= 30) OR (Sev Pain AND A1 <= 15 AND PS2_diff <= 15) )
    condition_mod = (
        (df['First Pain Score'] == 'Mod Pain') & 
        (df['Time_to_A1_Mins'] <= 15) & 
        (df['A1_to_PS2_Mins'] <= 30) & 
        (df['A1_to_PS2_Mins'] > 0)
    )
    condition_sev = (
        (df['First Pain Score'] == 'Sev Pain') & 
        (df['Time_to_A1_Mins'] <= 15) & 
        (df['A1_to_PS2_Mins'] <= 15) & 
        (df['A1_to_PS2_Mins'] > 0)
    )
    
    df['Best_Practice'] = np.where(
        (df['Time_to_PS1_Mins'] <= 15) & (condition_mod | condition_sev),
        'Yes', 'No'
    )
    
    # Calculate statistics for Sankey chart
    total_patients = len(df)
    ps1_15_mins = len(df[df['Time_to_PS1_Mins'] <= 15])
    severe_ps1_15_mins = len(df[(df['First Pain Score'] == 'Sev Pain') & (df['Time_to_PS1_Mins'] <= 15)])
    moderate_ps1_15_mins = len(df[(df['First Pain Score'] == 'Mod Pain') & (df['Time_to_PS1_Mins'] <= 15)])
    
    # Calculate best practice compliance
    best_practice_yes = len(df[df['Best_Practice'] == 'Yes'])
    best_practice_no = len(df[df['Best_Practice'] == 'No'])
    
    # Calculate PS1 & A1 compliance
    ps1_a1_15_mins = len(df[(df['Time_to_PS1_Mins'] <= 15) & (df['Time_to_A1_Mins'] <= 15)])
    severe_ps1_a1_15_mins = len(df[(df['First Pain Score'] == 'Sev Pain') & (df['Time_to_PS1_Mins'] <= 15) & (df['Time_to_A1_Mins'] <= 15)])
    moderate_ps1_a1_15_mins = len(df[(df['First Pain Score'] == 'Mod Pain') & (df['Time_to_PS1_Mins'] <= 15) & (df['Time_to_A1_Mins'] <= 15)])
    
    # Calculate best practice compliance
    severe_best_practice = len(df[(df['First Pain Score'] == 'Sev Pain') & (df['Best_Practice'] == 'Yes')])
    moderate_best_practice = len(df[(df['First Pain Score'] == 'Mod Pain') & (df['Best_Practice'] == 'Yes')])
    
    # Create Sankey data
    labels = [
        f"Total Patients ({total_patients})", # 0
        f"PS1 <= 15 Mins ({ps1_15_mins})", # 1
        f"PS1 > 15 Mins ({total_patients - ps1_15_mins})",  # 2
        f"Severe Pain (PS1 <= 15 Mins) ({severe_ps1_15_mins})", # 3
        f"Moderate Pain (PS1 <= 15 Mins) ({moderate_ps1_15_mins})", # 4
        f"Sev Pain (PS1 & A1 <= 15 Mins) ({severe_ps1_a1_15_mins})", # 5
        f"Mod Pain (PS1 & A1 <= 15 Mins) ({moderate_ps1_a1_15_mins})", # 6
        f"Sev Pain (PS1&A1>15Mins) ({severe_ps1_15_mins - severe_ps1_a1_15_mins})", # 7
        f"Mod Pain (PS1&A1>15Mins) ({moderate_ps1_15_mins - moderate_ps1_a1_15_mins})", # 8
        f"Severe Pain Best Practice ({severe_best_practice})", # 9
        f"Moderate Pain Best Practice ({moderate_best_practice})", # 10
        f"Sev Pain (No Best Practice) ({severe_ps1_a1_15_mins - severe_best_practice})", # 11
        f"Mod Pain (No Best Practice) ({moderate_ps1_a1_15_mins - moderate_best_practice})" # 12
    ]

    source = [0, 0, 1, 1, 3, 3, 4, 4, 5, 5, 6, 6]
    target = [1, 2, 3, 4, 5, 7, 6, 8, 9, 11, 10, 12]
    value = [
        ps1_15_mins,
        total_patients - ps1_15_mins,
        severe_ps1_15_mins,
        moderate_ps1_15_mins,
        severe_ps1_a1_15_mins,
        severe_ps1_15_mins - severe_ps1_a1_15_mins,
        moderate_ps1_a1_15_mins,
        moderate_ps1_15_mins - moderate_ps1_a1_15_mins,
        severe_best_practice,
        severe_ps1_a1_15_mins - severe_best_practice,
        moderate_best_practice,
        moderate_ps1_a1_15_mins - moderate_best_practice
    ]

    # Return both the dataframe and Sankey data
    return df, {
        'labels': labels,
        'source': source,
        'target': target,
        'value': value,
        'total_patients': total_patients,
        'best_practice_yes': best_practice_yes,
        'best_practice_no': best_practice_no
    }

def process_monthly_data(pain_data_file, imd_df=None):
    """
    Main function to load, clean, merge, and calculate all audit fields.
    """
    try:
        # 1. Load and clean data
        df = load_and_clean_pain_data(pain_data_file)
        
        # 2. Create join keys
        df = create_join_keys(df)
        
        # 3. Merge with IMD
        df = merge_with_imd_data(df, imd_df)
        
        # 4. Date conversion
        date_cols = ['Arrival DTTM', 'Triage DTTM', 'First Pain Score DTTM', 
                     'First Analgesia DTTM', 'Second Pain Score DTTM']
        df = convert_date_columns(df, date_cols)
        
        # 5. Basic calculations
        if 'Arrival DTTM' in df.columns:
            # Add Report Month for historical comparison
            df['Report_Month'] = df['Arrival DTTM'].dt.to_period('M').astype(str)
            
            # Time intervals
            df = calculate_time_intervals(df)
            
            # Pain scores
            df = calculate_pain_scores(df)
            
            # Age groups
            df = create_age_groups(df)
            
            # Best practice logic
            df = calculate_best_practice(df)

        return df

    except Exception as e:
        print(f"Error processing file: {e}")
        return None

def calculate_stats(df, group_col, target_col='Time_to_A1_Mins'):
    """
    Performs statistical tests (Kruskal-Wallis or Mann-Whitney) dynamically.
    Returns a dictionary with p-value and interpretation.
    """
    try:
        groups = df[group_col].dropna().unique()
        group_data = [df[df[group_col] == g][target_col].dropna() for g in groups]
        
        if len(groups) < 2:
            return {'p_value': None, 'msg': "Insufficient groups"}
            
        # Kruskal-Wallis for multiple groups, Mann-Whitney for 2
        if len(groups) == 2:
            stat, p = stats.mannwhitneyu(group_data[0], group_data[1])
            test_name = "Mann-Whitney U"
        else:
            stat, p = stats.kruskal(*group_data)
            test_name = "Kruskal-Wallis"
            
        is_sig = p < 0.05
        msg = "Statistically Significant Difference" if is_sig else "No Significant Difference"
        
        return {'test': test_name, 'p_value': p, 'significant': is_sig, 'message': msg}
    except:
        return {'p_value': None, 'msg': "Error calculating stats"}