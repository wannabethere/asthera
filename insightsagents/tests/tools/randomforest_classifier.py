# Random Forest Pipeline Examples

from app.tools.mltools.models.randomforest_classifier import (
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
    save_model,
    save_rf_model,
    load_rf_model,
    add_features,
    retrain_rf_model,
    predict_on_new_data,
    get_new_prediction_results,
    print_rf_summary
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




# Example 6: Model Management - Save and Load
def example_model_management():
    """
    Demonstrate model saving and loading functionality
    """
    # Generate sample data
    np.random.seed(42)
    n_samples = 1000
    
    management_data = pd.DataFrame({
        'customer_id': range(n_samples),
        'age': np.random.randint(18, 80, n_samples),
        'income': np.random.lognormal(10, 0.5, n_samples),
        'credit_score': np.random.normal(700, 100, n_samples),
        'payment_history': np.random.choice(['excellent', 'good', 'fair', 'poor'], n_samples),
        'loan_amount': np.random.gamma(2, 50000, n_samples),
        'employment_length': np.random.randint(0, 20, n_samples),
        'debt_to_income': np.random.uniform(0.1, 0.8, n_samples),
        'default_risk': np.random.choice([0, 1], n_samples, p=[0.8, 0.2])
    })
    
    # Create and save model
    print("Creating and saving model...")
    saved_model = (
        RFPipe.from_dataframe(management_data)
        
        # Generate features
        | generate_numerical_features(
            columns=['age', 'income', 'credit_score', 'loan_amount', 'employment_length', 'debt_to_income'],
            operations=['log', 'sqrt']
        )
        
        | generate_categorical_features(
            columns=['payment_history'],
            encoding_type='onehot'
        )
        
        | generate_interaction_features(
            column_pairs=[('income', 'loan_amount'), ('credit_score', 'debt_to_income')],
            operations=['multiply', 'divide']
        )
        
        # Set target
        | create_binary_labels(
            column='default_risk',
            condition='==1',
            label_column='default'
        )
        
        # Feature selection
        | select_features(method='kbest', k=15)
        
        # Train model
        | train_random_forest(
            test_size=0.2,
            n_estimators=200,
            max_depth=10,
            model_name='management_model'
        )
        
        # Make predictions
        | predict(model_name='management_model', data_split='test')
        
        # Calculate metrics
        | calculate_metrics(model_name='management_model')
        
        # Save model with preprocessing
        | save_rf_model(
            model_name='management_model',
            filepath='test_management_rf_model.joblib',
            include_preprocessing=True
        )
    )
    
    # Load model in new pipeline
    print("\nLoading model in new pipeline...")
    
    # Load the model first
    loaded_model = (
        RFPipe.from_dataframe(management_data.head(100))  # Use first 100 samples as new data
        
        # Load saved model
        | load_rf_model(
            filepath='test_management_rf_model.joblib',
            model_name='loaded_management_model'
        )
    )
    
    # Make predictions on new data (the predict_on_new_data function will handle missing features)
    loaded_model = (
        loaded_model
        | predict_on_new_data(
            model_name='loaded_management_model',
            new_data=management_data.head(100),  # Use raw data, let the function handle preprocessing
            prediction_name='loaded_model_predictions'
        )
        
        # Print summary
        | print_rf_summary('loaded_management_model')
    )
    
    # Get prediction results separately (since it returns a dict, not a pipe)
    prediction_results = get_new_prediction_results('loaded_model_predictions')(loaded_model)
    
    # Compare original and loaded models
    print("\nComparing original and loaded models...")
    original_metrics = saved_model.metrics.get('management_model_test_predictions', {})
    loaded_results = loaded_model.new_predictions.get('loaded_model_predictions', {})
    
    if original_metrics and loaded_results:
        print(f"Original model accuracy: {original_metrics.get('accuracy', 'N/A')}")
        print(f"Loaded model predictions: {len(loaded_results.get('predictions', []))}")
    
    return loaded_model


# Example 7: Feature Management and Addition
def example_feature_management():
    """
    Demonstrate adding new features to Random Forest models
    """
    # Generate sample data with multiple features
    np.random.seed(123)
    n_samples = 1500
    
    feature_data = pd.DataFrame({
        'customer_id': range(n_samples),
        'age': np.random.randint(18, 75, n_samples),
        'income': np.random.lognormal(10, 0.6, n_samples),
        'credit_score': np.random.normal(650, 120, n_samples),
        'payment_history': np.random.choice(['excellent', 'good', 'fair', 'poor'], n_samples),
        'loan_amount': np.random.gamma(2, 60000, n_samples),
        'employment_length': np.random.randint(0, 25, n_samples),
        'debt_to_income': np.random.uniform(0.1, 0.9, n_samples),
        'education_level': np.random.choice(['high_school', 'bachelor', 'master', 'phd'], n_samples),
        'home_ownership': np.random.choice(['own', 'rent', 'mortgage'], n_samples),
        'loan_purpose': np.random.choice(['home', 'car', 'education', 'business', 'personal'], n_samples),
        'default_risk': np.random.choice([0, 1], n_samples, p=[0.75, 0.25])
    })
    
    # Feature management pipeline
    print("Creating model with initial features...")
    feature_model = (
        RFPipe.from_dataframe(feature_data)
        
        # Generate initial numerical features
        | generate_numerical_features(
            columns=['age', 'income', 'credit_score'],
            operations=['log', 'sqrt'],
            prefix='initial_'
        )
        
        # Generate initial categorical features
        | generate_categorical_features(
            columns=['payment_history'],
            encoding_type='onehot'
        )
        
        # Set target
        | create_binary_labels(
            column='default_risk',
            condition='==1',
            label_column='default'
        )
        
        # Train initial model
        | train_random_forest(
            test_size=0.2,
            n_estimators=150,
            max_depth=8,
            model_name='initial_feature_model'
        )
        
        # Evaluate initial model
        | predict(model_name='initial_feature_model', data_split='test')
        | calculate_metrics(model_name='initial_feature_model')
    )
    
    print("\nAdding new features...")
    
    # Create derived features first
    feature_model.data['income_to_loan_ratio'] = feature_model.data['income'] / (feature_model.data['loan_amount'] + 1e-8)
    feature_model.data['credit_age_ratio'] = feature_model.data['credit_score'] / (feature_model.data['age'] + 1e-8)
    
    # Add new features
    feature_model = (
        feature_model
        
        # Add new numerical features
        | add_features(
            feature_columns=['loan_amount', 'employment_length', 'debt_to_income'],
            feature_type='classification',
            feature_name='additional_numerical'
        )
        
        # Add new categorical features
        | add_features(
            feature_columns=['education_level', 'home_ownership', 'loan_purpose'],
            feature_type='classification',
            feature_name='additional_categorical'
        )
        
        # Add derived features (computed from existing features)
        | add_features(
            feature_columns=['income_to_loan_ratio', 'credit_age_ratio'],
            feature_type='derived',
            feature_name='derived_features'
        )
        
        # Add auxiliary features (for analysis but not classification)
        | add_features(
            feature_columns=['customer_id'],
            feature_type='auxiliary',
            feature_name='auxiliary_data'
        )
    )
    
    print("\nRetraining model with enhanced features...")
    # Retrain with enhanced features
    feature_model = (
        feature_model
        
        # Generate features for new columns
        | generate_numerical_features(
            columns=['loan_amount', 'employment_length', 'debt_to_income', 'income_to_loan_ratio', 'credit_age_ratio'],
            operations=['log', 'sqrt'],
            prefix='enhanced_'
        )
        
        | generate_categorical_features(
            columns=['education_level', 'home_ownership', 'loan_purpose'],
            encoding_type='onehot'
        )
        
        # Feature selection
        | select_features(method='kbest', k=20)
        
        # Train enhanced model
        | train_random_forest(
            test_size=0.2,
            n_estimators=200,
            max_depth=12,
            model_name='enhanced_feature_model'
        )
        
        # Evaluate enhanced model
        | predict(model_name='enhanced_feature_model', data_split='test')
        | calculate_metrics(model_name='enhanced_feature_model')
        
        # Compare models
        | print_metrics(model_name='initial_feature_model')
        | print_metrics(model_name='enhanced_feature_model')
        
        # Print comprehensive summary
        | print_rf_summary()
    )
    
    return feature_model


# Example 8: Model Retraining and Updates
def example_model_retraining():
    """
    Demonstrate model retraining with new data and updated configurations
    """
    # Generate initial training data
    np.random.seed(456)
    initial_samples = 800
    
    initial_data = pd.DataFrame({
        'customer_id': range(initial_samples),
        'age': np.random.randint(18, 70, initial_samples),
        'income': np.random.lognormal(10, 0.5, initial_samples),
        'credit_score': np.random.normal(700, 100, initial_samples),
        'payment_history': np.random.choice(['excellent', 'good', 'fair'], initial_samples),
        'loan_amount': np.random.gamma(2, 50000, initial_samples),
        'employment_length': np.random.randint(1, 15, initial_samples),
        'debt_to_income': np.random.uniform(0.1, 0.6, initial_samples),
        'default_risk': np.random.choice([0, 1], initial_samples, p=[0.85, 0.15])
    })
    
    # Create initial model
    print("Creating initial model...")
    retrain_model = (
        RFPipe.from_dataframe(initial_data)
        
        # Generate features
        | generate_numerical_features(
            columns=['age', 'income', 'credit_score', 'loan_amount', 'employment_length', 'debt_to_income'],
            operations=['log', 'sqrt']
        )
        
        | generate_categorical_features(
            columns=['payment_history'],
            encoding_type='onehot'
        )
        
        # Set target
        | create_binary_labels(
            column='default_risk',
            condition='==1',
            label_column='default'
        )
        
        # Feature selection
        | select_features(method='kbest', k=12)
        
        # Train initial model
        | train_random_forest(
            test_size=0.2,
            n_estimators=100,
            max_depth=8,
            model_name='initial_model'
        )
        
        # Evaluate initial model
        | predict(model_name='initial_model', data_split='test')
        | calculate_metrics(model_name='initial_model')
    )
    
    # Generate new data with different patterns
    print("\nGenerating new data with updated patterns...")
    new_samples = 600
    
    new_data = pd.DataFrame({
        'customer_id': range(initial_samples, initial_samples + new_samples),
        'age': np.random.randint(20, 75, new_samples),  # Slightly different age distribution
        'income': np.random.lognormal(10.2, 0.6, new_samples),  # Higher income trend
        'credit_score': np.random.normal(720, 110, new_samples),  # Higher credit scores
        'payment_history': np.random.choice(['excellent', 'good', 'fair', 'poor'], new_samples, p=[0.4, 0.3, 0.2, 0.1]),
        'loan_amount': np.random.gamma(2.2, 55000, new_samples),  # Higher loan amounts
        'employment_length': np.random.randint(0, 20, new_samples),
        'debt_to_income': np.random.uniform(0.15, 0.7, new_samples),  # Higher debt ratios
        'default_risk': np.random.choice([0, 1], new_samples, p=[0.8, 0.2])  # Slightly higher default rate
    })
    
    # Create the target column for new data (same as in training)
    new_data['default'] = (new_data['default_risk'] == 1).astype(int)
    
    # Retrain with new data
    print("\nRetraining model with new data...")
    retrain_model = (
        retrain_model
        
        # Retrain with new data
        | retrain_rf_model(
            model_name='initial_model',
            new_data=new_data,
            retrain_name='retrained_model'
        )
        
        # Evaluate retrained model
        | calculate_metrics('retrained_model_predictions')
    )
    
    # Retrain with updated configuration
    print("\nRetraining with updated configuration...")
    retrain_model = (
        retrain_model
        
        # Retrain with updated parameters
        | retrain_rf_model(
            model_name='retrained_model',
            update_config={
                'n_estimators': 300,  # More trees
                'max_depth': 15,      # Deeper trees
                'min_samples_split': 5,  # More conservative splitting
                'min_samples_leaf': 3    # More conservative leaf size
            },
            retrain_name='optimized_model'
        )
        
        # Evaluate optimized model
        | calculate_metrics('optimized_model_predictions')
        
        # Compare all models
        | print_metrics(model_name='initial_model')
        | print_metrics('retrained_model_predictions')
        | print_metrics('optimized_model_predictions')
        
        # Print comprehensive summary
        | print_rf_summary()
    )
    
    return retrain_model


# Example 9: Advanced Prediction on New Data
def example_advanced_prediction():
    """
    Demonstrate advanced prediction capabilities with different scenarios
    """
    # Generate comprehensive dataset
    np.random.seed(789)
    n_samples = 2000
    
    prediction_data = pd.DataFrame({
        'customer_id': range(n_samples),
        'age': np.random.randint(18, 80, n_samples),
        'income': np.random.lognormal(10, 0.7, n_samples),
        'credit_score': np.random.normal(650, 150, n_samples),
        'payment_history': np.random.choice(['excellent', 'good', 'fair', 'poor'], n_samples),
        'loan_amount': np.random.gamma(2.5, 70000, n_samples),
        'employment_length': np.random.randint(0, 30, n_samples),
        'debt_to_income': np.random.uniform(0.05, 0.9, n_samples),
        'education_level': np.random.choice(['high_school', 'bachelor', 'master', 'phd'], n_samples),
        'home_ownership': np.random.choice(['own', 'rent', 'mortgage'], n_samples),
        'loan_purpose': np.random.choice(['home', 'car', 'education', 'business', 'personal'], n_samples),
        'default_risk': np.random.choice([0, 1], n_samples, p=[0.7, 0.3])
    })
    
    # Create comprehensive model
    print("Creating comprehensive prediction model...")
    prediction_model = (
        RFPipe.from_dataframe(prediction_data)
        
        # Generate comprehensive features
        | generate_numerical_features(
            columns=['age', 'income', 'credit_score', 'loan_amount', 'employment_length', 'debt_to_income'],
            operations=['log', 'sqrt', 'square']
        )
        
        | generate_categorical_features(
            columns=['payment_history', 'education_level', 'home_ownership', 'loan_purpose'],
            encoding_type='onehot'
        )
        
        | generate_interaction_features(
            column_pairs=[
                ('income', 'loan_amount'),
                ('credit_score', 'debt_to_income'),
                ('age', 'employment_length'),
                ('income', 'credit_score')
            ],
            operations=['multiply', 'divide']
        )
        
        # Set target
        | create_binary_labels(
            column='default_risk',
            condition='==1',
            label_column='default'
        )
        
        # Feature selection
        | select_features(method='mutual_info', k=25)
        
        # Train model
        | train_random_forest(
            test_size=0.2,
            n_estimators=300,
            max_depth=15,
            min_samples_split=5,
            model_name='prediction_model'
        )
        
        # Evaluate on test set
        | predict(model_name='prediction_model', data_split='test')
        | calculate_metrics(model_name='prediction_model')
    )
    
    # Scenario 1: Basic prediction on new data
    print("\nScenario 1: Basic prediction on new data...")
    new_data_1 = prediction_data.sample(n=200, random_state=100)
    
    prediction_model = (
        prediction_model
        
        | predict_on_new_data(
            model_name='prediction_model',
            new_data=new_data_1,
            prediction_name='basic_new_predictions'
        )
    )
    
    # Scenario 2: Prediction with feature subset
    print("\nScenario 2: Prediction with feature subset...")
    new_data_2 = prediction_data.sample(n=150, random_state=200)
    feature_subset = ['age', 'income', 'credit_score', 'loan_amount', 'debt_to_income']
    
    prediction_model = (
        prediction_model
        
        | predict_on_new_data(
            model_name='prediction_model',
            new_data=new_data_2,
            feature_subset=feature_subset,
            prediction_name='subset_predictions'
        )
    )
    
    # Scenario 3: Prediction on high-risk customers
    print("\nScenario 3: Prediction on high-risk customers...")
    high_risk_data = prediction_data[
        (prediction_data['credit_score'] < 600) | 
        (prediction_data['debt_to_income'] > 0.7) |
        (prediction_data['payment_history'] == 'poor')
    ].sample(n=100, random_state=300)
    
    prediction_model = (
        prediction_model
        
        | predict_on_new_data(
            model_name='prediction_model',
            new_data=high_risk_data,
            prediction_name='high_risk_predictions'
        )
    )
    
    # Print comprehensive summary
    prediction_model = prediction_model | print_rf_summary('prediction_model')
    
    # Get and analyze prediction results separately (since get_new_prediction_results returns a dict)
    print("\nAnalyzing prediction results...")
    basic_results = get_new_prediction_results('basic_new_predictions')(prediction_model)
    subset_results = get_new_prediction_results('subset_predictions')(prediction_model)
    high_risk_results = get_new_prediction_results('high_risk_predictions')(prediction_model)
    
    # Analyze prediction distributions
    print("\nPrediction Analysis:")
    for pred_name in ['basic_new_predictions', 'subset_predictions', 'high_risk_predictions']:
        if pred_name in prediction_model.new_predictions:
            pred_data = prediction_model.new_predictions[pred_name]
            predictions = pred_data['predictions']
            # Convert predictions to integers for proper counting
            predictions_int = [int(p) for p in predictions]
            print(f"\n{pred_name}:")
            print(f"  Total predictions: {len(predictions)}")
            print(f"  Default predictions: {sum(predictions_int)}")
            print(f"  Default rate: {sum(predictions_int)/len(predictions):.3f}")
            print(f"  Average confidence: {np.mean(pred_data['probabilities'].max(axis=1)):.3f}")
    
    return prediction_model


# Example 10: Complete Model Lifecycle
def example_complete_lifecycle():
    """
    Demonstrate complete model lifecycle from creation to deployment
    """
    # Generate comprehensive dataset
    np.random.seed(999)
    n_samples = 3000
    
    lifecycle_data = pd.DataFrame({
        'customer_id': range(n_samples),
        'age': np.random.randint(18, 85, n_samples),
        'income': np.random.lognormal(10, 0.8, n_samples),
        'credit_score': np.random.normal(650, 160, n_samples),
        'payment_history': np.random.choice(['excellent', 'good', 'fair', 'poor'], n_samples),
        'loan_amount': np.random.gamma(3, 80000, n_samples),
        'employment_length': np.random.randint(0, 35, n_samples),
        'debt_to_income': np.random.uniform(0.05, 0.95, n_samples),
        'education_level': np.random.choice(['high_school', 'bachelor', 'master', 'phd'], n_samples),
        'home_ownership': np.random.choice(['own', 'rent', 'mortgage'], n_samples),
        'loan_purpose': np.random.choice(['home', 'car', 'education', 'business', 'personal'], n_samples),
        'default_risk': np.random.choice([0, 1], n_samples, p=[0.65, 0.35])
    })
    
    print("=== Complete Random Forest Model Lifecycle Demo ===")
    
    # Step 1: Initial Model Development
    print("\nStep 1: Initial Model Development")
    lifecycle_model = (
        RFPipe.from_dataframe(lifecycle_data)
        
        # Basic feature engineering
        | generate_numerical_features(
            columns=['age', 'income', 'credit_score', 'loan_amount', 'employment_length', 'debt_to_income'],
            operations=['log', 'sqrt']
        )
        
        | generate_categorical_features(
            columns=['payment_history', 'education_level'],
            encoding_type='onehot'
        )
        
        # Set target
        | create_binary_labels(
            column='default_risk',
            condition='==1',
            label_column='default'
        )
        
        # Feature selection
        | select_features(method='kbest', k=15)
        
        # Train initial model
        | train_random_forest(
            test_size=0.2,
            n_estimators=200,
            max_depth=10,
            model_name='lifecycle_model'
        )
        
        # Initial evaluation
        | predict(model_name='lifecycle_model', data_split='test')
        | calculate_metrics(model_name='lifecycle_model')
    )
    
    # Step 2: Model Enhancement
    print("\nStep 2: Model Enhancement")
    lifecycle_model = (
        lifecycle_model
        
        # Add more features
        | add_features(
            feature_columns=['home_ownership', 'loan_purpose'],
            feature_type='classification',
            feature_name='additional_features'
        )
        
        # Generate features for new columns
        | generate_categorical_features(
            columns=['home_ownership', 'loan_purpose'],
            encoding_type='onehot'
        )
        
        | generate_interaction_features(
            column_pairs=[
                ('income', 'loan_amount'),
                ('credit_score', 'debt_to_income'),
                ('age', 'employment_length')
            ],
            operations=['multiply', 'divide']
        )
        
        # Retrain with enhanced features
        | retrain_rf_model(
            model_name='lifecycle_model',
            update_config={
                'n_estimators': 300,
                'max_depth': 15,
                'min_samples_split': 5
            },
            retrain_name='enhanced_lifecycle_model'
        )
        
        # Enhanced evaluation
        | predict(model_name='enhanced_lifecycle_model', data_split='all')
        | calculate_metrics(prediction_name='enhanced_lifecycle_model_all_predictions')
    )
    
    # Step 3: Model Optimization
    print("\nStep 3: Model Optimization")
    
    # Test different configurations
    configs = [
        {'n_estimators': 200, 'max_depth': 12, 'min_samples_split': 3},
        {'n_estimators': 400, 'max_depth': 18, 'min_samples_split': 7},
        {'n_estimators': 300, 'max_depth': 15, 'min_samples_split': 5}
    ]
    
    best_accuracy = 0
    best_config = None
    best_model_name = None
    
    for i, config in enumerate(configs):
        model_name = f'optimized_model_{i}'
        
        lifecycle_model = (
            lifecycle_model
            
            | retrain_rf_model(
                model_name='enhanced_lifecycle_model',
                update_config=config,
                retrain_name=model_name
            )
            
            | predict(model_name=model_name, data_split='all')
            | calculate_metrics(prediction_name=f'{model_name}_all_predictions')
        )
        
        # Check if this is the best model
        metrics = lifecycle_model.metrics.get(f'{model_name}_all_predictions', {})
        accuracy = metrics.get('accuracy', 0)
        
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_config = config
            best_model_name = model_name
    
    print(f"Best model: {best_model_name} with accuracy: {best_accuracy:.4f}")
    
    # Step 4: Model Deployment
    print("\nStep 4: Model Deployment")
    lifecycle_model = (
        lifecycle_model
        
        # Save optimized model
        | save_rf_model(
            model_name=best_model_name,
            filepath='deployed_lifecycle_rf_model.joblib',
            include_preprocessing=True
        )
    )
    
    # Step 5: Model Monitoring and Updates
    print("\nStep 5: Model Monitoring and Updates")
    
    # Simulate new data arrival
    new_samples = 500
    new_data = pd.DataFrame({
        'customer_id': range(n_samples, n_samples + new_samples),
        'age': np.random.randint(20, 80, new_samples),
        'income': np.random.lognormal(10.3, 0.8, new_samples),  # Slightly higher income
        'credit_score': np.random.normal(670, 150, new_samples),  # Higher credit scores
        'payment_history': np.random.choice(['excellent', 'good', 'fair', 'poor'], new_samples, p=[0.35, 0.35, 0.2, 0.1]),
        'loan_amount': np.random.gamma(3.2, 85000, new_samples),  # Higher loan amounts
        'employment_length': np.random.randint(0, 30, new_samples),
        'debt_to_income': np.random.uniform(0.1, 0.9, new_samples),
        'education_level': np.random.choice(['high_school', 'bachelor', 'master', 'phd'], new_samples),
        'home_ownership': np.random.choice(['own', 'rent', 'mortgage'], new_samples),
        'loan_purpose': np.random.choice(['home', 'car', 'education', 'business', 'personal'], new_samples),
        'default_risk': np.random.choice([0, 1], new_samples, p=[0.6, 0.4])  # Higher default rate
    })
    
    # Create the target column for new data (same as in training)
    new_data['default'] = (new_data['default_risk'] == 1).astype(int)
    
    # Update model with new data
    lifecycle_model = (
        lifecycle_model
        
        # Retrain with new data
        | retrain_rf_model(
            model_name=best_model_name,
            new_data=new_data,
            retrain_name='updated_lifecycle_model'
        )
        
        # Make predictions on new data
        | predict_on_new_data(
            model_name='updated_lifecycle_model',
            new_data=new_data.sample(n=100, random_state=400),
            prediction_name='monitoring_predictions'
        )
        
        # Final evaluation
        | calculate_metrics('updated_lifecycle_model_predictions')
        | print_metrics('updated_lifecycle_model_predictions')
        
        # Comprehensive summary
        | print_rf_summary()
    )
    
    print("\n=== Model Lifecycle Completed Successfully ===")
    
    return lifecycle_model

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
    
    print("\n" + "="*50)
    print("Example 6: Model Management - Save and Load")
    print("="*50)
    model_management_example = example_model_management()
    
    print("\n" + "="*50)
    print("Example 7: Feature Management and Addition")
    print("="*50)
    feature_management_example = example_feature_management()
    
    print("\n" + "="*50)
    print("Example 8: Model Retraining and Updates")
    print("="*50)
    retraining_example = example_model_retraining()
    
    print("\n" + "="*50)
    print("Example 9: Advanced Prediction on New Data")
    print("="*50)
    prediction_example = example_advanced_prediction()
    
    print("\n" + "="*50)
    print("Example 10: Complete Model Lifecycle")
    print("="*50)
    lifecycle_example = example_complete_lifecycle()
    
    print("\nAll examples completed successfully!")
