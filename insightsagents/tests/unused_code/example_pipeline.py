# Example ML Pipeline Code
# This file demonstrates the pipeline code format that the PipelineCodeGenerator can process

# Step 1: Data Selection
result = (
    MetricsPipe.from_dataframe("Purchase Orders Data")
    | Select(selectors=['Date', 'Region', 'Project', 'Source', 'Transactional value'])
    ).to_df()

# Step 2: Daily Aggregation of Transactional Values
result = (
    TrendsPipe.from_dataframe(result)
    | aggregate_by_time(group_by=['Date', 'Region', 'Project', 'Source'], aggregation={'mean': 'Transactional value'})
    ).to_df()

# Step 3: Distribution Analysis of Mean Daily Transactional Values
result = (
    TimeSeriesPipe.from_dataframe(result)
    | distribution_analysis(data='mean daily transactional values', group_by=['Region', 'Project', 'Source'])
    ).to_df()

# Step 4: Additional Analysis (Optional)
# result = (
#     AnalyticsPipe.from_dataframe(result)
#     | correlation_analysis(features=['mean', 'count'], group_by=['Region'])
#     ).to_df()
