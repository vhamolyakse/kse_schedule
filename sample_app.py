import streamlit as st
import pandas as pd

# Function to create a table of buttons with highlight toggle
def create_interactive_table(df):
    # Create a dictionary to hold button highlight states
    if 'highlighted_cells' not in st.session_state:
        st.session_state.highlighted_cells = {}

    # Iterate over the DataFrame to create buttons
    for col in df.columns:
        for row in range(len(df)):
            # Create a unique key for each button
            button_key = f"{col}_{row}"

            # If the button hasn't been clicked yet, add it to session state
            if button_key not in st.session_state.highlighted_cells:
                st.session_state.highlighted_cells[button_key] = False

            # Create a button and toggle the highlight state on click
            if st.button(df.at[row, col], key=button_key):
                # Toggle the state
                st.session_state.highlighted_cells[button_key] = not st.session_state.highlighted_cells[button_key]

            # Apply color styling if highlighted
            if st.session_state.highlighted_cells[button_key]:
                # Streamlit currently doesn't support changing the button color directly
                # However, we can display a placeholder or a message to indicate the highlight
                st.markdown(f"`{df.at[row, col]}` is highlighted!", unsafe_allow_html=True)

def main():
    st.title('Interactive Table with Highlightable Cells')

    # Sample data for the table
    data = {
        'Column1': ['1', '2', '3'],
        'Column2': ['4', '5', '6'],
        'Column3': ['7', '8', '9']
    }

    # Create a DataFrame
    df = pd.DataFrame(data)

    # Create an interactive table with highlightable cells
    create_interactive_table(df)

if __name__ == "__main__":
    main()
