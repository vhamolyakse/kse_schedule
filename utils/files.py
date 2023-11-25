import os
import pandas as pd
from loguru import logger
from io import StringIO

def convert_df_to_csv(df):
    # Convert DataFrame to CSV
    output = StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()

def process_file(uploaded_file, save_dir):
    # Create a directory to save files
    os.makedirs(save_dir, exist_ok=True)

    # Read the Excel file (all sheets)
    with pd.ExcelFile(uploaded_file) as xls:
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name)
            
            # Construct the filename for each sheet
            save_path = os.path.join(save_dir, f"{sheet_name}.csv")
            
            # Save each sheet as a CSV file
            df.to_csv(save_path, index=False)
            logger.debug(f"Saved {sheet_name} to {save_path}")