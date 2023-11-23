import streamlit as st

def main():
    st.title("Welcome to Streamlit!")

    # User input
    name = st.text_input("Enter your name:")

    # Display greeting
    if name:
        st.write(f"Hello, {name}!")

if __name__ == "__main__":
    main()

