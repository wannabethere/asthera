# Random Forest Pipeline Examples

from rf_pipeline import (
    RFPipe, 
    generate_numerical_features, 
    generate_categorical_features,
    generate_interaction_features,
    create_binary_labels,
    create_multiclass_labels,
    select_features,
    train_random_forest,
    predict,
    calculate_metrics,
    print_metrics,
    save_model
)
import pandas as pd
import numpy as np

# Example 1: Basic Binary Classification Pipeline
def example_customer_churn_prediction():
    """
    Predict customer churn using various customer features
    """
    # Load customer data (example)
    customer_data = pd.DataFrame({
        'customer_id': range(1000),
        'age': np.random.randint(18, 80, 1000),
        'monthly_spend': np.random.gamma(2, 50, 1000),
        'tenure_months': np.random.randint(1, 60, 1000),
        'support_tickets': np.random.poisson(2, 1000),
        'plan_type': np.random.choice(['basic', 'premium', 'enterprise'], 1000),
        'total_revenue': np.random.gamma(3, 100, 1000)
    })
    
    # Create churn prediction pipeline
    churn_pipeline = (
        RFPipe.from_dataframe(customer_data)
        
        # Generate additional numerical features
        | generate_numerical_features(
            columns=['monthly_spend', 'tenure_months'], 
            operations=['log', 'sqrt']
        )
        
        # Encode categorical features
        | generate_categorical_features(
            columns=['plan_type'], 
            encoding_type='onehot'
        )
        
        # Create interaction features
        | generate_interaction_features(
            column_pairs=[('age', 'tenure_months'), ('monthly_spend', 'support_tickets')],
            operations=['multiply', 'divide']
        )
        
        # Create binary churn labels (customers with low revenue are "churned")
        | create_binary_labels(
            column='total_revenue',
            condition='<200',  # Low revenue threshold
            label_column='churned'
        )
        
        # Select top 15 features
        | select_features(method='kbest', k=15)
        
        # Train Random Forest
        | train_random_forest(
            test_size=0.2,
            n_estimators=200,
            max_depth=10,
            model_name='churn_model'
        )
        
        # Make predictions
        | predict(model_name='churn_model', data_split='test')
        
        # Calculate metrics
        | calculate_metrics(model_name='churn_model')
        
        # Print results
        | print_metrics(model_name='churn_model')
    )
    
    return churn_pipeline


# Example 2: Multiclass Classification with Feature Engineering
def example_customer_segmentation():
    """
    Segment customers into value tiers based on behavior
    """
    # Generate customer behavior data
    np.random.seed(42)
    customer_behavior = pd.DataFrame({
        'user_id': range(2000),
        'session_count': np.random.poisson(10, 2000),
        'page_views': np.random.poisson(50, 2000),
        'time_on_site': np.random.gamma(2, 15, 2000),
        'purchases': np.random.poisson(3, 2000),
        'revenue': np.random.gamma(2, 100, 2000),
        'device_type': np.random.choice(['mobile', 'desktop', 'tablet'], 2000),
        'acquisition_channel': np.random.choice(['organic', 'paid', 'referral', 'direct'], 2000),
        'days_since_signup': np.random.randint(1, 365, 2000)
    })
    
    # Customer segmentation pipeline
    segmentation_pipeline = (
        RFPipe.from_dataframe(customer_behavior)
        
        # Generate engagement features
        | generate_numerical_features(
            columns=['session_count', 'page_views', 'time_on_site'],
            operations=['log', 'sqrt'],
            prefix='engagement_'
        )
        
        # Generate revenue features
        | generate_numerical_features(
            columns=['revenue', 'purchases'],
            operations=['log', 'square'],
            prefix='revenue_'
        )
        
        # Encode categorical features
        | generate_categorical_features(
            columns=['device_type', 'acquisition_channel'],
            encoding_type='onehot'
        )
        
        # Create interaction features for engagement
        | generate_interaction_features(
            column_pairs=[
                ('session_count', 'time_on_site'),
                ('page_views', 'purchases'),
                ('revenue', 'days_since_signup')
            ],
            operations=['multiply', 'divide']
        )
        
        # Create customer value segments (multiclass)
        | create_multiclass_labels(
            column='revenue',
            bins=[0, 50, 200, 500, float('inf')],
            labels=['Low', 'Medium', 'High', 'Premium'],
            label_column='customer_segment'
        )
        
        # Feature selection
        | select_features(method='mutual_info', k=20)
        
        # Train model
        | train_random_forest(
            test_size=0.25,
            n_estimators=300,
            max_depth=15,
            min_samples_split=5,
            model_name='segmentation_model'
        )
        
        # Predict and evaluate
        | predict(model_name='segmentation_model', data_split='test')
        | calculate_metrics(model_name='segmentation_model', average='macro')
        | print_metrics(model_name='segmentation_model')
        
        # Save the model
        | save_model(model_name='segmentation_model')
    )
    
    return segmentation_pipeline


# Example 3: Advanced Pipeline with Custom Features
def example_fraud_detection():
    """
    Detect fraudulent transactions using transaction features
    """
    # Generate transaction data
    np.random.seed(123)
    n_transactions = 5000
    
    # Normal transactions
    normal_amount = np.random.lognormal(3, 1, int(n_transactions * 0.95))
    normal_time = np.random.uniform(6, 22, int(n_transactions * 0.95))  # Business hours
    normal_freq = np.random.poisson(2, int(n_transactions * 0.95))  # Transaction frequency
    
    # Fraudulent transactions (5%)
    fraud_amount = np.random.lognormal(5, 1.5, int(n_transactions * 0.05))  # Higher amounts
    fraud_time = np.random.uniform(0, 24, int(n_transactions * 0.05))  # Any time
    fraud_freq = np.random.poisson(8, int(n_transactions * 0.05))  # Higher frequency
    
    # Combine data
    transaction_data = pd.DataFrame({
        'transaction_id': range(n_transactions),
        'amount': np.concatenate([normal_amount, fraud_amount]),
        'hour_of_day': np.concatenate([normal_time, fraud_time]),
        'daily_transaction_count': np.concatenate([normal_freq, fraud_freq]),
        'merchant_category': np.random.choice(['grocery', 'gas', 'restaurant', 'online', 'atm'], n_transactions),
        'card_type': np.random.choice(['credit', 'debit'], n_transactions),
        'location_risk': np.random.uniform(0, 1, n_transactions),
        'is_weekend': np.random.choice([0, 1], n_transactions),
        'is_fraud': np.concatenate([np.zeros(int(n_transactions * 0.95)), np.ones(int(n_transactions * 0.05))])
    })
    
    # Shuffle the data
    transaction_data = transaction_data.sample(frac=1).reset_index(drop=True)
    
    # Fraud detection pipeline
    fraud_pipeline = (
        RFPipe.from_dataframe(transaction_data)
        
        # Generate time-based features
        | generate_numerical_features(
            columns=['hour_of_day'],
            operations=['sqrt'],  # Normalize hour patterns
            prefix='time_'
        )
        
        # Generate amount-based features
        | generate_numerical_features(
            columns=['amount'],
            operations=['log', 'sqrt'],
            prefix='amount_'
        )
        
        # Generate risk features
        | generate_numerical_features(
            columns=['location_risk', 'daily_transaction_count'],
            operations=['square', 'log'],
            prefix='risk_'
        )
        
        # Encode categorical features
        | generate_categorical_features(
            columns=['merchant_category', 'card_type'],
            encoding_type='onehot'
        )
        
        # Create complex interaction features
        | generate_interaction_features(
            column_pairs=[
                ('amount', 'daily_transaction_count'),
                ('location_risk', 'is_weekend'),
                ('hour_of_day', 'amount'),
                ('daily_transaction_count', 'location_risk')
            ],
            operations=['multiply', 'add']
        )
        
        # Set target column (fraud labels already exist)
    )
    
    # Set the target column manually since labels already exist
    fraud_pipeline.target_column = 'is_fraud'
    
    # Continue with the pipeline
    final_pipeline = (
        fraud_pipeline
        
        # Feature selection for fraud detection
        | select_features(method='kbest', k=25)
        
        # Train with balanced parameters for fraud detection
        | train_random_forest(
            test_size=0.3,
            n_estimators=500,
            max_depth=20,
            min_samples_split=10,
            min_samples_leaf=5,
            model_name='fraud_model'
        )
        
        # Predict on both train and test sets
        | predict(model_name='fraud_model', data_split='test')
        | predict(model_name='fraud_model', data_split='train', 
                 prediction_name='fraud_model_train_predictions')
        
        # Calculate metrics
        | calculate_metrics(model_name='fraud_model')
        | calculate_metrics(prediction_name='fraud_model_train_predictions')
        
        # Print results
        | print_metrics(model_name='fraud_model')
    )
    
    return final_pipeline


# Example 4: Model Comparison Pipeline
def example_model_comparison():
    """
    Compare different Random Forest configurations
    """
    # Generate sample data
    np.random.seed(456)
    data = pd.DataFrame({
        'feature1': np.random.normal(0, 1, 1000),
        'feature2': np.random.normal(2, 1.5, 1000),
        'feature3': np.random.gamma(2, 2, 1000),
        'category': np.random.choice(['A', 'B', 'C'], 1000),
        'target_value': np.random.gamma(3, 2, 1000)
    })
    
    # Base pipeline with features
    base_pipeline = (
        RFPipe.from_dataframe(data)
        | generate_numerical_features(['feature1', 'feature2', 'feature3'])
        | generate_categorical_features(['category'])
        | create_binary_labels('target_value', '>5', 'high_value')
    )
    
    # Model 1: Small forest
    model1_pipeline = (
        base_pipeline.copy()
        | train_random_forest(
            n_estimators=50,
            max_depth=5,
            model_name='small_forest'
        )
        | predict(model_name='small_forest')
        | calculate_metrics(model_name='small_forest')
    )
    
    # Model 2: Large forest
    model2_pipeline = (
        base_pipeline.copy()
        | train_random_forest(
            n_estimators=200,
            max_depth=15,
            model_name='large_forest'
        )
        | predict(model_name='large_forest')
        | calculate_metrics(model_name='large_forest')
    )
    
    # Model 3: Deep forest with feature selection
    model3_pipeline = (
        base_pipeline.copy()
        | select_features(k=10)
        | train_random_forest(
            n_estimators=300,
            max_depth=25,
            min_samples_split=10,
            model_name='deep_forest'
        )
        | predict(model_name='deep_forest')
        | calculate_metrics(model_name='deep_forest')
    )
    
    # Compare results
    print("=== Model Comparison ===")
    print(f"Small Forest Accuracy: {model1_pipeline.metrics['small_forest_test_predictions']['accuracy']:.4f}")
    print(f"Large Forest Accuracy: {model2_pipeline.metrics['large_forest_test_predictions']['accuracy']:.4f}")
    print(f"Deep Forest Accuracy: {model3_pipeline.metrics['deep_forest_test_predictions']['accuracy']:.4f}")
    
    return {
        'small': model1_pipeline,
        'large': model2_pipeline, 
        'deep': model3_pipeline
    }


# Example 5: Production Pipeline with Cross-Validation
def example_production_pipeline():
    """
    Complete production-ready pipeline with cross-validation
    """
    # Generate realistic e-commerce data
    np.random.seed(789)
    n_customers = 3000
    
    ecommerce_data = pd.DataFrame({
        'customer_id': range(n_customers),
        'age': np.random.randint(18, 70, n_customers),
        'income': np.random.lognormal(10, 0.5, n_customers),
        'orders_last_month': np.random.poisson(2, n_customers),
        'avg_order_value': np.random.gamma(2, 50, n_customers),
        'days_since_last_order': np.random.exponential(10, n_customers),
        'customer_segment': np.random.choice(['new', 'regular', 'vip'], n_customers),
        'preferred_category': np.random.choice(['electronics', 'clothing', 'home', 'books'], n_customers),
        'marketing_channel': np.random.choice(['email', 'social', 'search', 'direct'], n_customers),
        'lifetime_value': np.random.gamma(3, 200, n_customers)
    })
    
    # Production pipeline
    production_pipeline = (
        RFPipe.from_dataframe(ecommerce_data)
        
        # Comprehensive feature engineering
        | generate_numerical_features(
            columns=['age', 'income', 'avg_order_value', 'days_since_last_order'],
            operations=['log', 'sqrt'],
            prefix='numerical_'
        )
        
        | generate_categorical_features(
            columns=['customer_segment', 'preferred_category', 'marketing_channel'],
            encoding_type='onehot'
        )
        
        | generate_interaction_features(
            column_pairs=[
                ('age', 'income'),
                ('orders_last_month', 'avg_order_value'),
                ('income', 'avg_order_value'),
                ('days_since_last_order', 'orders_last_month')
            ]
        )
        
        # Create high-value customer labels
        | create_binary_labels(
            column='lifetime_value',
            condition='>=500',
            label_column='high_value_customer'
        )
        
        # Feature selection
        | select_features(method='kbest', k=20)
        
        # Train optimized model
        | train_random_forest(
            test_size=0.2,
            n_estimators=300,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            model_name='production_model'
        )
        
        # Full evaluation
        | predict(model_name='production_model', data_split='test')
        | predict(model_name='production_model', data_split='train', 
                 prediction_name='production_model_train_predictions')
        
        | calculate_metrics(model_name='production_model')
        | calculate_metrics(prediction_name='production_model_train_predictions')
        
        | print_metrics(model_name='production_model')
        
        # Save for production use
        | save_model(model_name='production_model', filepath='high_value_customer_model.joblib')
    )
    
    return production_pipeline


if __name__ == "__main__":
    print("Running Random Forest Pipeline Examples...")
    
    print("\n" + "="*50)
    print("Example 1: Customer Churn Prediction")
    print("="*50)
    churn_model = example_customer_churn_prediction()
    
    print("\n" + "="*50)  
    print("Example 2: Customer Segmentation")
    print("="*50)
    segment_model = example_customer_segmentation()
    
    print("\n" + "="*50)
    print("Example 3: Fraud Detection")
    print("="*50)
    fraud_model = example_fraud_detection()
    
    print("\n" + "="*50)
    print("Example 4: Model Comparison")
    print("="*50)
    comparison_results = example_model_comparison()
    
    print("\n" + "="*50)
    print("Example 5: Production Pipeline")
    print("="*50)
    production_model = example_production_pipeline()
    
    print("\nAll examples completed successfully!")