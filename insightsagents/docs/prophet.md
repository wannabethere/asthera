Looking at the Prophet configuration, the choice between `growth='linear'` vs `growth='logistic'` is a fundamental modeling decision. Let me explain how to determine which one to use:

## Linear Growth (`growth='linear'`)
**Use when:**
- The time series can grow indefinitely without natural limits
- The trend is expected to continue at a relatively constant rate
- There's no carrying capacity or saturation point

**Examples:**
- Revenue (can theoretically grow forever)
- Population in early growth phases
- Website traffic (without infrastructure constraints)
- Sales volume (without market saturation)

## Logistic Growth (`growth='logistic'`)
**Use when:**
- There's a natural upper limit or carrying capacity
- Growth rate slows down as it approaches a maximum
- The series follows an S-curve pattern

**Examples:**
- User adoption (limited by total addressable market)
- Market penetration (can't exceed 100%)
- Population growth (limited by resources/space)
- Technology adoption curves

## Key Indicators in Your Data

**Choose Linear if:**
```python
# Trend continues at steady rate
# No signs of saturation
# Growth rate remains relatively constant
```

**Choose Logistic if:**
```python
# Growth rate is slowing down over time
# You can identify a realistic maximum value
# Data shows S-curve characteristics (slow start, rapid growth, then leveling off)
```

## Data Requirements

Looking at the code, you can see the key difference in the forecasting functions:

```python
# For logistic growth, the model requires a 'cap' column
if model.growth == 'logistic':
    if 'cap' in new_pipe.data.columns:
        cap_value = new_pipe.data['cap'].iloc[-1]
        future['cap'] = cap_value
    else:
        raise ValueError("Logistic growth requires 'cap' column in data")
```

## Decision Process

1. **Analyze your domain knowledge**: Is there a theoretical maximum?
2. **Examine the trend**: Is growth rate decreasing over time?
3. **Consider business context**: Are you approaching market saturation?
4. **Data availability**: Do you have or can you estimate carrying capacity values?

**For logistic growth, you must:**
- Add a `'cap'` column to your data with the carrying capacity values
- These can be constant or time-varying
- The values should represent realistic upper bounds

The code handles this automatically - you just need to ensure your data has the required `'cap'` column when using logistic growth.


I'll explain the evaluation methodologies for Prophet predictions based on the code implementation, with practical examples.

## 1. Time Series Cross-Validation

### How it Works
Prophet uses **time-aware cross-validation** that respects the temporal order of data, unlike regular k-fold CV.

```python
pipe | cross_validate_model(
    initial='730 days',    # Initial training period
    period='180 days',     # Gap between cutoffs  
    horizon='365 days',    # Forecast horizon
    model_name='prophet_model'
)
```

### Visual Example
```
Historical Data: |-------|-------|-------|-------|-------|
                 2020    2021    2022    2023    2024    2025

CV Fold 1: Train |-------|       Test |-------|
CV Fold 2: Train |-------|-------|     Test |-------|  
CV Fold 3: Train |-------|-------|-------|   Test |-------|
```

### Parameters Explained
- **`initial='730 days'`**: Must have at least 2 years of data to start training
- **`period='180 days'`**: Each new fold adds 6 months of training data
- **`horizon='365 days'`**: Test forecasts for 1 year ahead each time

## 2. Forecast Accuracy Metrics

### Implementation
```python
pipe | calculate_forecast_metrics(
    forecast_name='my_forecast',
    actual_column='y',
    cutoff_date='2024-01-01'  # Split point between training/test
)
```

### Metrics Calculated

**Mean Absolute Error (MAE)**
```python
mae = np.mean(np.abs(y_true - y_pred))
```
- **Interpretation**: Average absolute difference between actual and predicted
- **Example**: MAE = 150 means predictions are off by 150 units on average
- **Good for**: Understanding typical error magnitude

**Mean Absolute Percentage Error (MAPE)**
```python
mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
```
- **Interpretation**: Average percentage error
- **Example**: MAPE = 12% means predictions are typically 12% off
- **Good for**: Comparing across different scales

**Root Mean Square Error (RMSE)**
```python
rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
```
- **Interpretation**: Standard deviation of prediction errors
- **Example**: RMSE = 200 means ~68% of errors are within ±200 units
- **Good for**: Penalizing large errors more heavily

**Coverage Percentage**
```python
coverage = np.mean(
    (actual >= forecast_lower) & (actual <= forecast_upper)
) * 100
```
- **Interpretation**: How often actual values fall within prediction intervals
- **Example**: Coverage = 85% means 85% of actuals are within the confidence bands
- **Good for**: Validating uncertainty estimates

## 3. Practical Evaluation Examples

### Example 1: E-commerce Sales Forecasting
```python
# Scenario: Predicting monthly sales
# Data: 3 years of historical sales data

evaluation_pipe = (
    sales_pipe
    | cross_validate_model(
        initial='365 days',     # 1 year initial training
        period='90 days',       # Quarterly evaluation
        horizon='180 days',     # 6-month forecasts
        model_name='sales_model'
    )
    | calculate_forecast_metrics(
        forecast_name='sales_forecast',
        cutoff_date='2024-01-01'
    )
    | print_forecast_metrics('sales_forecast')
)

# Expected Output:
# === Forecast Metrics for sales_forecast ===
# MAE: 15,432.50     (Average error: $15K)
# MAPE: 8.5%         (Typical % error: 8.5%)
# RMSE: 22,156.75    (Standard error: $22K)
# Coverage: 87.5%    (87.5% within confidence intervals)
```

### Example 2: Website Traffic Prediction
```python
# Scenario: Daily website visits
# Challenge: Strong weekly seasonality

traffic_evaluation = (
    traffic_pipe
    | cross_validate_model(
        initial='90 days',      # 3 months initial
        period='14 days',       # Bi-weekly evaluation
        horizon='30 days',      # 1-month forecasts
        model_name='traffic_model'
    )
)

# Interpretation:
# - Short initial period due to daily data frequency
# - Frequent evaluation to catch seasonal changes
# - 30-day horizon for monthly planning
```

## 4. Hyperparameter Tuning Evaluation

### Grid Search with Cross-Validation
```python
param_grid = {
    'changepoint_prior_scale': [0.01, 0.05, 0.1, 0.5],
    'seasonality_prior_scale': [1.0, 10.0, 20.0],
    'holidays_prior_scale': [1.0, 10.0, 20.0]
}

tuned_pipe = pipe | hyperparameter_tuning(
    param_grid=param_grid,
    cv_initial='180 days',
    cv_period='30 days', 
    cv_horizon='90 days',
    metric='mape'  # Optimize for MAPE
)
```

### How It Works
1. **Generate all combinations**: 4 × 3 × 3 = 36 parameter combinations
2. **For each combination**:
   - Train model with those parameters
   - Run cross-validation
   - Calculate average MAPE across folds
3. **Select best**: Parameters with lowest average MAPE
4. **Retrain**: Final model with optimal parameters

## 5. Evaluation Best Practices

### Choosing Evaluation Windows
```python
# For different business contexts:

# Financial forecasting (quarterly reports)
cross_validate_model(
    initial='730 days',    # 2 years baseline
    period='90 days',      # Quarterly evaluation
    horizon='365 days'     # Annual planning
)

# Inventory management (weekly restocking)
cross_validate_model(
    initial='56 days',     # 8 weeks baseline  
    period='7 days',       # Weekly evaluation
    horizon='28 days'      # Monthly inventory
)

# Marketing campaigns (daily optimization)
cross_validate_model(
    initial='30 days',     # 1 month baseline
    period='1 days',       # Daily evaluation  
    horizon='7 days'       # Weekly campaigns
)
```

### Metric Selection Guidelines

| Business Context | Primary Metric | Reason |
|-----------------|----------------|---------|
| Financial Planning | MAPE | Percentage errors matter more than absolute |
| Inventory Management | MAE | Absolute quantities matter for stock levels |
| SLA Monitoring | Coverage | Need reliable prediction intervals |
| Outlier Detection | RMSE | Want to penalize large misses heavily |

### Validation Strategies

**Holdout Validation**
```python
# Reserve last 20% for final testing
cutoff_date = data['ds'].quantile(0.8)

train_pipe = data[data['ds'] <= cutoff_date]
test_pipe = data[data['ds'] > cutoff_date]
```

**Walk-Forward Validation**
```python
# Continuously retrain as new data arrives
for month in forecast_months:
    train_data = data[data['ds'] <= month]
    test_month = month + pd.DateOffset(months=1)
    # Train, predict, evaluate, then add month to training
```

This evaluation framework ensures your Prophet models are robust and reliable for production forecasting scenarios.