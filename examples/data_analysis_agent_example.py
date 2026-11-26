import os

import pandas as pd

from dbgpt.agent import AgentMessage
from dbgpt.agent.expand.data_analysis_agent import DataAnalysisAgent


# Define an example Excel analysis function
def analyze_excel(file_path, query):
    if not os.path.exists(file_path):
        raise FileNotFoundError("Excel file not found.")

    df = pd.read_excel(file_path)
    if query == "columns":
        return df.columns.tolist()
    elif query == "summary":
        return df.describe().to_dict()
    else:
        return "Query not understood."


# Setting up the agent
agent = DataAnalysisAgent()

# Define the file to analyze and the analysis query
excel_file = "/tmp/sample_data.xlsx"  # Replace with actual Excel file path
analysis_query = "columns"

# Save a sample file (optional)
data = {
    "Name": ["Alice", "Bob"],
    "Age": [25, 30],
    "Country": ["US", "Canada"],
}
sample_df = pd.DataFrame(data)
sample_df.to_excel(excel_file, index=False)

# Agent receives a message to analyze the file
received_message = AgentMessage(
    content=f"Analyze file {excel_file} for query: {analysis_query}"
)

# Simulated agent behavior
try:
    analysis_result = analyze_excel(excel_file, analysis_query)
    agent_reply = f"Analysis Result: {analysis_result}"
except Exception as e:
    agent_reply = f"Error: {str(e)}"

# Output the agent's response
print(agent_reply)
