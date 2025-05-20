import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Load the CSV file into a DataFrame
file_path = '/root/yProv4SQA/export.csv'
df = pd.read_csv(file_path)

# Preprocess the data:
# 1. Remove the percentage symbol from the 'PercentagePassed' column and convert it to numeric
df['PercentagePassed'] = df['PercentagePassed'].replace('%', '', regex=True)  # Remove '%' symbol
df['PercentagePassed'] = pd.to_numeric(df['PercentagePassed'], errors='coerce')  # Convert to numeric

# 2. Convert the 'CommitDate' column to datetime format (ISO 8601 format)
df['CommitDate'] = pd.to_datetime(df['CommitDate'], format='%Y-%m-%dT%H:%M:%SZ')

# Display the cleaned data to verify the preprocessing
print(df.head())

# Step 2: Reshape the DataFrame to have each quality criterion as a separate column
# We'll pivot the data to create a table where each quality criterion is a separate column
df_pivot = df.pivot(index='CommitDate', columns='QualityCriteria', values='PercentagePassed')

# Step 3: Plotting the graph
plt.figure(figsize=(10, 6))

# Plot each quality criterion as a separate line and add data labels for each point
for column in df_pivot.columns:
    plt.plot(df_pivot.index, df_pivot[column], label=column, marker='o')  # Add marker for visibility

    # Add data labels for each point on the line
    for i, value in enumerate(df_pivot[column]):
        plt.text(df_pivot.index[i], value, f'{value:.2f}%', fontsize=8, verticalalignment='bottom', horizontalalignment='right')

# Adding labels and title
plt.xlabel('Commit Date')
plt.ylabel('Percentage Passed')
plt.title('Quality Criteria Progression Over Time')

# Formatting the X-axis to show days as well as months
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))  # Format as Year-Month-Day
plt.gca().xaxis.set_major_locator(mdates.DayLocator())  # Show every day on the x-axis
plt.xticks(rotation=45)  # Rotate the date labels for better readability

# Adding a legend to distinguish between the criteria
plt.legend(title='Quality Criteria')

# Show grid for easier visualization
plt.grid(True)

# Ensure the layout is adjusted before saving the plot
plt.tight_layout()

# Save the plot as a PNG file (optional)
plt.savefig('quality_criteria_progression_with_daily_dates.png')  # Save as an image
plt.show()  # Display the graph
