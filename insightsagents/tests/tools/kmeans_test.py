# K-means Clustering Pipeline Examples

from app.tools.mltools.models.kmeans_clustering import (
    KMeansPipe,
    prepare_clustering_data,
    engineer_clustering_features,
    reduce_dimensions,
    configure_kmeans,
    configure_minibatch_kmeans,
    fit_kmeans,
    evaluate_clustering,
    profile_clusters,
    find_optimal_k,
    plot_clusters_2d,
    plot_cluster_profiles,
    plot_elbow_curve,
    plot_silhouette_scores,
    save_kmeans_model,
    print_cluster_summary,
    load_kmeans_model,
    add_features,
    retrain_kmeans_model,
    predict_clusters,
    get_prediction_results
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# Example 1: Customer Segmentation for E-commerce
def example_customer_segmentation():
    """
    Customer segmentation based on purchasing behavior and demographics
    """
    # Generate realistic customer data
    np.random.seed(42)
    n_customers = 3000
    
    # Create different customer archetypes
    segments = ['Budget Conscious', 'Frequent Buyer', 'Premium Customer', 'Occasional Shopper']
    true_segments = np.random.choice(segments, n_customers, p=[0.3, 0.25, 0.15, 0.3])
    
    # Generate features based on segments
    customer_data = []
    for i, segment in enumerate(true_segments):
        if segment == 'Budget Conscious':
            age = np.random.normal(35, 8)
            income = np.random.normal(45000, 10000)
            monthly_spend = np.random.gamma(2, 50)
            order_frequency = np.random.poisson(2)
            avg_order_value = np.random.gamma(1.5, 25)
        elif segment == 'Frequent Buyer':
            age = np.random.normal(42, 10)
            income = np.random.normal(65000, 15000)
            monthly_spend = np.random.gamma(3, 80)
            order_frequency = np.random.poisson(8)
            avg_order_value = np.random.gamma(2, 40)
        elif segment == 'Premium Customer':
            age = np.random.normal(48, 12)
            income = np.random.normal(90000, 20000)
            monthly_spend = np.random.gamma(5, 120)
            order_frequency = np.random.poisson(5)
            avg_order_value = np.random.gamma(4, 80)
        else:  # Occasional Shopper
            age = np.random.normal(38, 15)
            income = np.random.normal(55000, 18000)
            monthly_spend = np.random.gamma(1.5, 30)
            order_frequency = np.random.poisson(1)
            avg_order_value = np.random.gamma(2, 35)
        
        customer_data.append({
            'customer_id': f'CUST_{i:04d}',
            'age': max(18, age),
            'income': max(20000, income),
            'monthly_spend': max(0, monthly_spend),
            'order_frequency': max(0, order_frequency),
            'avg_order_value': max(10, avg_order_value),
            'days_since_last_purchase': np.random.exponential(30),
            'total_purchases': np.random.poisson(order_frequency * 12),
            'website_sessions': np.random.poisson(order_frequency * 3),
            'email_open_rate': np.random.beta(2, 3),
            'preferred_category': np.random.choice(['Electronics', 'Fashion', 'Home', 'Sports', 'Books']),
            'device_type': np.random.choice(['Mobile', 'Desktop', 'Tablet'], p=[0.6, 0.3, 0.1]),
            'true_segment': segment  # For validation
        })
    
    customer_df = pd.DataFrame(customer_data)
    
    # Customer segmentation pipeline
    segmentation_model = (
        KMeansPipe.from_dataframe(customer_df)
        
        # Prepare clustering data
        | prepare_clustering_data(
            feature_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'days_since_last_purchase', 'total_purchases',
                'website_sessions', 'email_open_rate'
            ],
            scaling_method='standard',
            handle_missing='mean',
            remove_outliers=True,
            outlier_method='iqr'
        )
        
        # Engineer clustering features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency'),
                ('website_sessions', 'total_purchases')
            ],
            polynomial_features=['monthly_spend', 'income']
        )
        
        # Find optimal number of clusters
        | find_optimal_k(
            k_range=(2, 10),
            method='both',
            analysis_name='customer_segments'
        )
        
        # Plot optimal k analysis
        | plot_elbow_curve('customer_segments')
        | plot_silhouette_scores('customer_segments')
        
        # Configure K-means with optimal parameters
        | configure_kmeans(
            n_clusters=4,  # Based on elbow/silhouette analysis
            init='k-means++',
            n_init=20,
            model_name='customer_kmeans'
        )
        
        # Fit the clustering model
        | fit_kmeans('customer_kmeans')
        
        # Evaluate clustering performance
        | evaluate_clustering('customer_kmeans')
        
        # Create detailed cluster profiles
        | profile_clusters(
            'customer_kmeans',
            profile_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'preferred_category', 'device_type'
            ]
        )
        
        # Visualize clusters
        | plot_clusters_2d('customer_kmeans', 'monthly_spend', 'avg_order_value')
        | plot_cluster_profiles('customer_kmeans', 'numerical', top_k_features=8)
        | plot_cluster_profiles('customer_kmeans', 'categorical', top_k_features=3)
        
        # Print comprehensive summary
        | print_cluster_summary('customer_kmeans')
        
        # Save the model
        | save_kmeans_model('customer_kmeans', 'customer_segmentation_model.joblib')
    )
    
    # Validate against true segments
    cluster_col = segmentation_model.cluster_assignments['customer_kmeans']['cluster_column']
    validation_df = segmentation_model.data[[cluster_col, 'true_segment']].copy()
    print("\n=== Validation Against True Segments ===")
    print(pd.crosstab(validation_df[cluster_col], validation_df['true_segment'], normalize='columns') * 100)
    
    return segmentation_model


# Example 2: Market Research - Consumer Preference Clustering
def example_market_research():
    """
    Cluster consumers based on product preferences and lifestyle factors
    """
    # Generate consumer survey data
    np.random.seed(123)
    n_consumers = 2500
    
    # Lifestyle and preference dimensions
    health_consciousness = np.random.beta(2, 2, n_consumers) * 10
    price_sensitivity = np.random.beta(3, 2, n_consumers) * 10
    brand_loyalty = np.random.beta(2, 3, n_consumers) * 10
    tech_savviness = np.random.beta(2, 2, n_consumers) * 10
    environmental_concern = np.random.beta(2.5, 1.5, n_consumers) * 10
    
    # Shopping behavior
    online_shopping_freq = np.random.poisson(5, n_consumers)
    impulse_buying = np.random.beta(2, 3, n_consumers) * 10
    research_before_purchase = np.random.beta(3, 2, n_consumers) * 10
    social_media_influence = np.random.beta(2, 2, n_consumers) * 10
    
    # Demographics
    age_groups = np.random.choice(['18-25', '26-35', '36-45', '46-55', '56+'], n_consumers)
    income_levels = np.random.choice(['Low', 'Medium', 'High'], n_consumers, p=[0.3, 0.5, 0.2])
    education = np.random.choice(['High School', 'Bachelor', 'Graduate'], n_consumers, p=[0.4, 0.4, 0.2])
    
    market_research_data = pd.DataFrame({
        'consumer_id': [f'CONS_{i:04d}' for i in range(n_consumers)],
        'health_consciousness': health_consciousness,
        'price_sensitivity': price_sensitivity,
        'brand_loyalty': brand_loyalty,
        'tech_savviness': tech_savviness,
        'environmental_concern': environmental_concern,
        'online_shopping_frequency': online_shopping_freq,
        'impulse_buying_tendency': impulse_buying,
        'research_before_purchase': research_before_purchase,
        'social_media_influence': social_media_influence,
        'age_group': age_groups,
        'income_level': income_levels,
        'education_level': education
    })
    
    # Market research clustering pipeline
    market_segments = (
        KMeansPipe.from_dataframe(market_research_data)
        
        # Prepare data for clustering
        | prepare_clustering_data(
            feature_columns=[
                'health_consciousness', 'price_sensitivity', 'brand_loyalty',
                'tech_savviness', 'environmental_concern', 'online_shopping_frequency',
                'impulse_buying_tendency', 'research_before_purchase', 'social_media_influence'
            ],
            scaling_method='minmax',  # Scale to 0-1 for better interpretation
            remove_outliers=True,
            outlier_threshold=2.5
        )
        
        # Create meaningful feature combinations
        | engineer_clustering_features(
            interaction_features=False,  # Keep interpretability high
            ratio_features=[
                ('health_consciousness', 'price_sensitivity'),
                ('tech_savviness', 'social_media_influence'),
                ('brand_loyalty', 'impulse_buying_tendency')
            ]
        )
        
        # Dimensionality reduction for visualization
        | reduce_dimensions(method='pca', n_components=2, reducer_name='pca_viz')
        | reduce_dimensions(method='tsne', n_components=2, reducer_name='tsne_viz')
        
        # Find optimal clusters
        | find_optimal_k(k_range=(3, 8), method='both', analysis_name='market_segments')
        | plot_elbow_curve('market_segments')
        | plot_silhouette_scores('market_segments')
        
        # Configure clustering
        | configure_kmeans(
            n_clusters=5,
            init='k-means++',
            n_init=15,
            model_name='market_kmeans'
        )
        
        # Fit and evaluate
        | fit_kmeans('market_kmeans')
        | evaluate_clustering('market_kmeans')
        
        # Comprehensive profiling
        | profile_clusters(
            'market_kmeans',
            profile_columns=[
                'health_consciousness', 'price_sensitivity', 'brand_loyalty',
                'tech_savviness', 'environmental_concern', 'online_shopping_frequency',
                'age_group', 'income_level', 'education_level'
            ]
        )
        
        # Visualizations
        | plot_clusters_2d('market_kmeans', 'pca_dim_1', 'pca_dim_2')
        | plot_clusters_2d('market_kmeans', 'health_consciousness', 'price_sensitivity')
        | plot_cluster_profiles('market_kmeans', 'numerical', top_k_features=10)
        | plot_cluster_profiles('market_kmeans', 'categorical')
        
        # Summary and insights
        | print_cluster_summary('market_kmeans')
    )
    
    return market_segments


# Example 3: Operational Analytics - Delivery Route Optimization
def example_delivery_optimization():
    """
    Cluster delivery locations for route optimization
    """
    # Generate delivery location data for a metropolitan area
    np.random.seed(456)
    n_locations = 1500
    
    # Create geographic clusters (representing different neighborhoods)
    n_neighborhoods = 8
    neighborhood_centers = np.random.uniform(-50, 50, (n_neighborhoods, 2))
    
    delivery_data = []
    for i in range(n_locations):
        # Assign to neighborhood
        neighborhood = np.random.randint(n_neighborhoods)
        center_x, center_y = neighborhood_centers[neighborhood]
        
        # Add noise around neighborhood center
        location_x = center_x + np.random.normal(0, 5)
        location_y = center_y + np.random.normal(0, 5)
        
        # Generate delivery characteristics
        avg_delivery_time = np.random.gamma(2, 15)  # minutes
        delivery_frequency = np.random.poisson(8)  # per week
        package_size = np.random.gamma(2, 2)  # cubic meters
        delivery_urgency = np.random.uniform(1, 5)  # 1=standard, 5=urgent
        access_difficulty = np.random.uniform(1, 5)  # 1=easy, 5=difficult
        
        delivery_data.append({
            'location_id': f'LOC_{i:04d}',
            'latitude': location_y,
            'longitude': location_x,
            'avg_delivery_time': avg_delivery_time,
            'delivery_frequency_per_week': delivery_frequency,
            'avg_package_size': package_size,
            'delivery_urgency_score': delivery_urgency,
            'access_difficulty_score': access_difficulty,
            'neighborhood_type': np.random.choice(['Residential', 'Commercial', 'Industrial']),
            'true_neighborhood': neighborhood  # For validation
        })
    
    delivery_df = pd.DataFrame(delivery_data)
    
    # Delivery optimization clustering pipeline
    route_optimization = (
        KMeansPipe.from_dataframe(delivery_df)
        
        # Prepare geographic and operational features
        | prepare_clustering_data(
            feature_columns=[
                'latitude', 'longitude', 'avg_delivery_time', 
                'delivery_frequency_per_week', 'avg_package_size',
                'delivery_urgency_score', 'access_difficulty_score'
            ],
            scaling_method='standard',
            remove_outliers=True,
            outlier_method='zscore',
            outlier_threshold=3.0
        )
        
        # Engineer route-relevant features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('avg_delivery_time', 'access_difficulty_score'),
                ('delivery_frequency_per_week', 'avg_package_size'),
                ('delivery_urgency_score', 'avg_delivery_time')
            ],
            polynomial_features=['delivery_frequency_per_week']
        )
        
        # Find optimal number of delivery zones
        | find_optimal_k(k_range=(5, 15), method='both', analysis_name='delivery_zones')
        | plot_elbow_curve('delivery_zones')
        | plot_silhouette_scores('delivery_zones')
        
        # Configure clustering for route zones
        | configure_kmeans(
            n_clusters=10,  # 10 delivery zones
            init='k-means++',
            n_init=25,
            max_iter=500,
            model_name='route_kmeans'
        )
        
        # Fit and evaluate
        | fit_kmeans('route_kmeans')
        | evaluate_clustering('route_kmeans')
        
        # Profile delivery zones
        | profile_clusters(
            'route_kmeans',
            profile_columns=[
                'latitude', 'longitude', 'avg_delivery_time',
                'delivery_frequency_per_week', 'avg_package_size',
                'delivery_urgency_score', 'access_difficulty_score', 'neighborhood_type'
            ]
        )
        
        # Geographic visualization
        | plot_clusters_2d('route_kmeans', 'longitude', 'latitude')
        | plot_clusters_2d('route_kmeans', 'avg_delivery_time', 'access_difficulty_score')
        
        # Operational profiles
        | plot_cluster_profiles('route_kmeans', 'numerical', top_k_features=8)
        | plot_cluster_profiles('route_kmeans', 'categorical')
        
        | print_cluster_summary('route_kmeans')
        | save_kmeans_model('route_kmeans', 'delivery_route_optimization.joblib')
    )
    
    return route_optimization


# Example 4: MiniBatch K-means for Large Dataset
def example_large_scale_clustering():
    """
    Demonstrate MiniBatch K-means for large-scale user behavior clustering
    """
    # Generate large user behavior dataset
    np.random.seed(789)
    n_users = 50000  # Large dataset
    
    # Simulate user behavior patterns
    user_data = []
    behavior_types = ['Light User', 'Moderate User', 'Heavy User', 'Power User']
    
    for i in range(n_users):
        behavior_type = np.random.choice(behavior_types, p=[0.4, 0.3, 0.2, 0.1])
        
        if behavior_type == 'Light User':
            sessions_per_week = np.random.poisson(2)
            avg_session_duration = np.random.gamma(1, 10)
            pages_per_session = np.random.poisson(3)
            features_used = np.random.poisson(1)
        elif behavior_type == 'Moderate User':
            sessions_per_week = np.random.poisson(8)
            avg_session_duration = np.random.gamma(2, 15)
            pages_per_session = np.random.poisson(8)
            features_used = np.random.poisson(3)
        elif behavior_type == 'Heavy User':
            sessions_per_week = np.random.poisson(20)
            avg_session_duration = np.random.gamma(3, 20)
            pages_per_session = np.random.poisson(15)
            features_used = np.random.poisson(6)
        else:  # Power User
            sessions_per_week = np.random.poisson(35)
            avg_session_duration = np.random.gamma(4, 25)
            pages_per_session = np.random.poisson(25)
            features_used = np.random.poisson(10)
        
        user_data.append({
            'user_id': f'USER_{i:05d}',
            'sessions_per_week': sessions_per_week,
            'avg_session_duration_minutes': avg_session_duration,
            'pages_per_session': pages_per_session,
            'unique_features_used': features_used,
            'mobile_usage_ratio': np.random.beta(2, 2),
            'weekend_activity_ratio': np.random.beta(2, 2),
            'error_rate': np.random.beta(1, 10),
            'support_tickets_per_month': np.random.poisson(1),
            'true_behavior_type': behavior_type
        })
    
    large_dataset = pd.DataFrame(user_data)
    
    # Large-scale clustering pipeline
    large_scale_model = (
        KMeansPipe.from_dataframe(large_dataset)
        
        # Efficient data preparation
        | prepare_clustering_data(
            feature_columns=[
                'sessions_per_week', 'avg_session_duration_minutes',
                'pages_per_session', 'unique_features_used', 'mobile_usage_ratio',
                'weekend_activity_ratio', 'error_rate', 'support_tickets_per_month'
            ],
            scaling_method='robust',  # Robust to outliers
            remove_outliers=False  # Skip for large datasets
        )
        
        # Minimal feature engineering for efficiency
        | engineer_clustering_features(
            interaction_features=False,
            ratio_features=[
                ('pages_per_session', 'avg_session_duration_minutes'),
                ('sessions_per_week', 'mobile_usage_ratio')
            ]
        )
        
        # Quick optimal k estimation (smaller range for efficiency)
        | find_optimal_k(k_range=(3, 8), method='elbow', analysis_name='large_scale')
        | plot_elbow_curve('large_scale')
        
        # Configure MiniBatch K-means for scalability
        | configure_minibatch_kmeans(
            n_clusters=4,
            batch_size=2000,
            max_iter=200,
            max_no_improvement=15,
            model_name='large_scale_kmeans'
        )
        
        # Fit and evaluate
        | fit_kmeans('large_scale_kmeans')
        | evaluate_clustering('large_scale_kmeans')
        
        # Profile user behavior clusters
        | profile_clusters('large_scale_kmeans')
        
        # Efficient visualizations (sample for plotting)
        | plot_clusters_2d('large_scale_kmeans', 'sessions_per_week', 'avg_session_duration_minutes')
        | plot_cluster_profiles('large_scale_kmeans', 'numerical')
        
        | print_cluster_summary('large_scale_kmeans')
        | save_kmeans_model('large_scale_kmeans', 'large_scale_user_clusters.joblib')
    )
    
    # Performance comparison
    print(f"\n=== Large Scale Clustering Performance ===")
    print(f"Dataset size: {len(large_dataset):,} users")
    print(f"Features: {len(large_scale_model.feature_columns)} dimensions")
    
    # Validate against true behavior types
    cluster_col = large_scale_model.cluster_assignments['large_scale_kmeans']['cluster_column']
    validation_sample = large_scale_model.data.sample(n=1000)  # Sample for validation display
    print("\nValidation (Sample of 1000 users):")
    print(pd.crosstab(
        validation_sample[cluster_col], 
        validation_sample['true_behavior_type'], 
        normalize='columns'
    ) * 100)
    
    return large_scale_model


# Example 5: Advanced Clustering with Feature Engineering
def example_advanced_feature_engineering():
    """
    Advanced clustering with comprehensive feature engineering for financial data
    """
    # Generate financial customer data
    np.random.seed(999)
    n_customers = 4000
    
    # Create customer financial profiles
    financial_data = []
    for i in range(n_customers):
        # Base demographics
        age = np.random.normal(42, 15)
        income = np.random.lognormal(10.8, 0.7)
        
        # Account information
        account_age_months = np.random.exponential(36)
        num_products = np.random.poisson(2) + 1
        
        # Transaction behavior
        monthly_transactions = np.random.gamma(2, 15)
        avg_transaction_amount = np.random.gamma(2, 100)
        
        # Credit behavior
        credit_utilization = np.random.beta(2, 3)
        payment_history_score = np.random.normal(0.85, 0.15)
        
        # Investment behavior
        investment_portfolio_size = np.random.gamma(1.5, 5000)
        risk_tolerance = np.random.uniform(1, 10)
        
        # Digital engagement
        mobile_app_usage = np.random.poisson(20)
        online_banking_frequency = np.random.poisson(8)
        
        # Life events indicators
        recent_large_purchase = np.random.choice([0, 1], p=[0.8, 0.2])
        recent_income_change = np.random.choice([-1, 0, 1], p=[0.1, 0.8, 0.1])
        
        financial_data.append({
            'customer_id': f'FIN_{i:04d}',
            'age': max(18, min(80, age)),
            'annual_income': max(20000, income),
            'account_age_months': max(1, account_age_months),
            'num_products': num_products,
            'monthly_transactions': monthly_transactions,
            'avg_transaction_amount': avg_transaction_amount,
            'credit_utilization_ratio': np.clip(credit_utilization, 0, 1),
            'payment_history_score': np.clip(payment_history_score, 0, 1),
            'investment_portfolio_size': investment_portfolio_size,
            'risk_tolerance_score': risk_tolerance,
            'mobile_app_sessions_per_month': mobile_app_usage,
            'online_banking_logins_per_month': online_banking_frequency,
            'recent_large_purchase': recent_large_purchase,
            'recent_income_change': recent_income_change
        })
    
    financial_df = pd.DataFrame(financial_data)
    
    # Advanced financial clustering pipeline
    financial_clusters = (
        KMeansPipe.from_dataframe(financial_df)
        
        # Comprehensive data preparation
        | prepare_clustering_data(
            feature_columns=[
                'age', 'annual_income', 'account_age_months', 'num_products',
                'monthly_transactions', 'avg_transaction_amount', 'credit_utilization_ratio',
                'payment_history_score', 'investment_portfolio_size', 'risk_tolerance_score',
                'mobile_app_sessions_per_month', 'online_banking_logins_per_month'
            ],
            scaling_method='robust',
            remove_outliers=True,
            outlier_method='iqr'
        )
        
        # Extensive feature engineering
        | engineer_clustering_features(
            interaction_features=True,
            polynomial_features=['annual_income', 'investment_portfolio_size'],
            ratio_features=[
                ('investment_portfolio_size', 'annual_income'),
                ('avg_transaction_amount', 'monthly_transactions'),
                ('mobile_app_sessions_per_month', 'age'),
                ('credit_utilization_ratio', 'payment_history_score')
            ],
            binning_features={
                'age': 5,
                'annual_income': 6,
                'account_age_months': 4
            }
        )
        
        # Dimensionality reduction for high-dimensional data
        | reduce_dimensions(method='pca', n_components=3, reducer_name='financial_pca')
        
        # Optimal k analysis
        | find_optimal_k(k_range=(4, 12), method='both', analysis_name='financial_segments')
        | plot_elbow_curve('financial_segments')
        | plot_silhouette_scores('financial_segments')
        
        # Configure advanced K-means
        | configure_kmeans(
            n_clusters=6,
            init='k-means++',
            n_init=30,
            max_iter=500,
            tol=1e-6,
            model_name='financial_kmeans'
        )
        
        # Fit and comprehensive evaluation
        | fit_kmeans('financial_kmeans')
        | evaluate_clustering(
            'financial_kmeans',
            metrics=['silhouette', 'calinski_harabasz', 'davies_bouldin', 'inertia']
        )
        
        # Detailed financial profiling
        | profile_clusters(
            'financial_kmeans',
            profile_columns=[
                'age', 'annual_income', 'account_age_months', 'num_products',
                'monthly_transactions', 'avg_transaction_amount', 'credit_utilization_ratio',
                'payment_history_score', 'investment_portfolio_size', 'risk_tolerance_score',
                'mobile_app_sessions_per_month', 'online_banking_logins_per_month',
                'recent_large_purchase', 'recent_income_change'
            ],
            include_categorical=True
        )
        
        # Multiple visualizations
        | plot_clusters_2d('financial_kmeans', 'annual_income', 'investment_portfolio_size')
        | plot_clusters_2d('financial_kmeans', 'pca_dim_1', 'pca_dim_2')
        | plot_cluster_profiles('financial_kmeans', 'numerical', top_k_features=12)
        | plot_cluster_profiles('financial_kmeans', 'categorical')
        
        # Comprehensive reporting
        | print_cluster_summary('financial_kmeans')
        | save_kmeans_model('financial_kmeans', 'financial_customer_segments.joblib')
    )
    
    # Business interpretation
    print("\n=== Business Interpretation ===")
    profiles = financial_clusters.cluster_profiles['financial_kmeans']
    if 'numerical' in profiles:
        centroids = profiles['centroids']
        print("Cluster Characteristics:")
        for i, cluster in enumerate(centroids.index):
            income = centroids.loc[cluster, 'annual_income'] if 'annual_income' in centroids.columns else 0
            investment = centroids.loc[cluster, 'investment_portfolio_size'] if 'investment_portfolio_size' in centroids.columns else 0
            print(f"  {cluster}: Avg Income: ${income:,.0f}, Avg Investment: ${investment:,.0f}")
    
    return financial_clusters


if __name__ == "__main__":
    print("Running K-means Clustering Pipeline Examples...")
    
    print("\n" + "="*60)
    print("Example 1: E-commerce Customer Segmentation")
    print("="*60)
    customer_model = example_customer_segmentation()
    
    print("\n" + "="*60)
    print("Example 2: Market Research Consumer Clustering")
    print("="*60)
    market_model = example_market_research()
    
    print("\n" + "="*60)
    print("Example 3: Delivery Route Optimization")
    print("="*60)
    delivery_model = example_delivery_optimization()
    
    print("\n" + "="*60)
    print("Example 4: Large-Scale User Behavior Clustering")
    print("="*60)
    large_scale_model = example_large_scale_clustering()
    
    print("\n" + "="*60)
    print("Example 5: Advanced Financial Customer Clustering")
    print("="*60)
    financial_model = example_advanced_feature_engineering()
    
    print("\n" + "="*60)
    print("Example 6: Model Management - Save and Load")
    print("="*60)
    model_management_example = example_model_management()
    
    print("\n" + "="*60)
    print("Example 7: Feature Management and Addition")
    print("="*60)
    feature_management_example = example_feature_management()
    
    print("\n" + "="*60)
    print("Example 8: Model Retraining and Updates")
    print("="*60)
    retraining_example = example_model_retraining()
    
    print("\n" + "="*60)
    print("Example 9: Advanced Prediction on New Data")
    print("="*60)
    prediction_example = example_advanced_prediction()
    
    print("\n" + "="*60)
    print("Example 10: Complete Model Lifecycle")
    print("="*60)
    lifecycle_example = example_complete_lifecycle()
    
    print("\nAll K-means clustering examples completed successfully!")
    
    # Summary of all models
    print("\n" + "="*60)
    print("CLUSTERING SUMMARY")
    print("="*60)
    models = [
        ('Customer Segmentation', customer_model),
        ('Market Research', market_model),
        ('Delivery Optimization', delivery_model),
        ('Large Scale Behavior', large_scale_model),
        ('Financial Clustering', financial_model)
    ]
    
    for name, model in models:
        model_name = list(model.models.keys())[0]
        n_clusters = model.models[model_name]['config']['n_clusters']
        n_features = len(model.feature_columns)
        n_samples = len(model.data)
        
        print(f"{name}:")
        print(f"  Samples: {n_samples:,}, Features: {n_features}, Clusters: {n_clusters}")
        
        if model_name in model.evaluation_metrics:
            metrics = model.evaluation_metrics[model_name]
            if 'silhouette_score' in metrics:
                print(f"  Silhouette Score: {metrics['silhouette_score']:.3f}")
        print()


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
        'monthly_spend': np.random.gamma(2, 50, n_samples),
        'order_frequency': np.random.poisson(5, n_samples),
        'avg_order_value': np.random.gamma(2, 30, n_samples),
        'days_since_last_purchase': np.random.exponential(30, n_samples),
        'total_purchases': np.random.poisson(20, n_samples),
        'website_sessions': np.random.poisson(15, n_samples),
        'email_open_rate': np.random.beta(2, 3, n_samples),
        'preferred_category': np.random.choice(['Electronics', 'Fashion', 'Home', 'Sports', 'Books'], n_samples),
        'device_type': np.random.choice(['Mobile', 'Desktop', 'Tablet'], n_samples)
    })
    
    # Create and save model
    print("Creating and saving model...")
    saved_model = (
        KMeansPipe.from_dataframe(management_data)
        
        # Prepare clustering data
        | prepare_clustering_data(
            feature_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'days_since_last_purchase', 'total_purchases',
                'website_sessions', 'email_open_rate'
            ],
            scaling_method='standard',
            remove_outliers=True
        )
        
        # Engineer features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency'),
                ('website_sessions', 'total_purchases')
            ]
        )
        
        # Find optimal k
        | find_optimal_k(k_range=(2, 8), method='both', analysis_name='management_segments')
        
        # Configure and fit model
        | configure_kmeans(
            n_clusters=4,
            init='k-means++',
            n_init=20,
            model_name='management_model'
        )
        
        | fit_kmeans('management_model')
        
        # Evaluate and profile
        | evaluate_clustering('management_model')
        | profile_clusters('management_model')
        
        # Save model with preprocessing
        | save_kmeans_model(
            model_name='management_model',
            filepath='test_management_kmeans_model.joblib',
            include_preprocessing=True
        )
    )
    
    # Load model in new pipeline
    print("\nLoading model in new pipeline...")
    loaded_model = (
        KMeansPipe.from_dataframe(management_data)
        
        # Load saved model
        | load_kmeans_model(
            filepath='test_management_kmeans_model.joblib',
            model_name='loaded_management_model'
        )
        
        # Make predictions on new data
        | predict_clusters(
            model_name='loaded_management_model',
            new_data=management_data.head(200),  # Use first 200 samples as new data
            prediction_name='loaded_model_predictions'
        )
        
        # Get prediction results
        | get_prediction_results('loaded_model_predictions')
        
        # Print summary
        | print_cluster_summary('loaded_management_model')
    )
    
    # Compare original and loaded models
    print("\nComparing original and loaded models...")
    original_metrics = saved_model.evaluation_metrics.get('management_model', {})
    loaded_results = loaded_model.predictions.get('loaded_model_predictions', {})
    
    if original_metrics and loaded_results:
        print(f"Original model silhouette score: {original_metrics.get('silhouette_score', 'N/A')}")
        print(f"Loaded model predictions: {len(loaded_results.get('cluster_assignments', []))}")
    
    return loaded_model


# Example 7: Feature Management and Addition
def example_feature_management():
    """
    Demonstrate adding new features to K-means models
    """
    # Generate sample data with multiple features
    np.random.seed(123)
    n_samples = 1500
    
    feature_data = pd.DataFrame({
        'customer_id': range(n_samples),
        'age': np.random.randint(18, 75, n_samples),
        'income': np.random.lognormal(10, 0.6, n_samples),
        'monthly_spend': np.random.gamma(2, 60, n_samples),
        'order_frequency': np.random.poisson(6, n_samples),
        'avg_order_value': np.random.gamma(2, 35, n_samples),
        'days_since_last_purchase': np.random.exponential(25, n_samples),
        'total_purchases': np.random.poisson(25, n_samples),
        'website_sessions': np.random.poisson(18, n_samples),
        'email_open_rate': np.random.beta(2, 3, n_samples),
        'preferred_category': np.random.choice(['Electronics', 'Fashion', 'Home', 'Sports', 'Books'], n_samples),
        'device_type': np.random.choice(['Mobile', 'Desktop', 'Tablet'], n_samples),
        'loyalty_program': np.random.choice(['Bronze', 'Silver', 'Gold', 'Platinum'], n_samples),
        'customer_support_contacts': np.random.poisson(2, n_samples),
        'return_rate': np.random.beta(1, 10, n_samples)
    })
    
    # Feature management pipeline
    print("Creating model with initial features...")
    feature_model = (
        KMeansPipe.from_dataframe(feature_data)
        
        # Prepare initial features
        | prepare_clustering_data(
            feature_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'days_since_last_purchase'
            ],
            scaling_method='standard',
            remove_outliers=True
        )
        
        # Engineer initial features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency')
            ]
        )
        
        # Find optimal k
        | find_optimal_k(k_range=(2, 6), method='both', analysis_name='initial_features')
        
        # Configure and fit initial model
        | configure_kmeans(
            n_clusters=3,
            init='k-means++',
            n_init=15,
            model_name='initial_feature_model'
        )
        
        | fit_kmeans('initial_feature_model')
        | evaluate_clustering('initial_feature_model')
        | profile_clusters('initial_feature_model')
    )
    
    print("\nAdding new features...")
    # Add new features
    feature_model = (
        feature_model
        
        # Add new numerical features
        | add_features(
            feature_columns=['total_purchases', 'website_sessions', 'email_open_rate'],
            feature_type='clustering',
            feature_name='additional_numerical'
        )
        
        # Add categorical features
        | add_features(
            feature_columns=['preferred_category', 'device_type', 'loyalty_program'],
            feature_type='clustering',
            feature_name='additional_categorical'
        )
        
        # Add derived features (computed from existing features)
        | add_features(
            feature_columns=['customer_lifetime_value', 'engagement_score'],
            feature_type='derived',
            feature_name='derived_features'
        )
        
        # Add auxiliary features (for analysis but not clustering)
        | add_features(
            feature_columns=['customer_id'],
            feature_type='auxiliary',
            feature_name='auxiliary_data'
        )
    )
    
    # Create derived features
    feature_model.data['customer_lifetime_value'] = feature_model.data['total_purchases'] * feature_model.data['avg_order_value']
    feature_model.data['engagement_score'] = (feature_model.data['website_sessions'] * 0.3 + 
                                             feature_model.data['email_open_rate'] * 0.7)
    
    print("\nRetraining model with enhanced features...")
    # Retrain with enhanced features
    feature_model = (
        feature_model
        
        # Prepare enhanced data
        | prepare_clustering_data(
            feature_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'days_since_last_purchase', 'total_purchases',
                'website_sessions', 'email_open_rate', 'customer_lifetime_value',
                'engagement_score'
            ],
            scaling_method='standard',
            remove_outliers=True
        )
        
        # Engineer enhanced features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency'),
                ('customer_lifetime_value', 'age'),
                ('engagement_score', 'total_purchases')
            ],
            polynomial_features=['customer_lifetime_value', 'engagement_score']
        )
        
        # Find optimal k for enhanced model
        | find_optimal_k(k_range=(3, 8), method='both', analysis_name='enhanced_features')
        
        # Configure and fit enhanced model
        | configure_kmeans(
            n_clusters=4,
            init='k-means++',
            n_init=20,
            model_name='enhanced_feature_model'
        )
        
        | fit_kmeans('enhanced_feature_model')
        | evaluate_clustering('enhanced_feature_model')
        | profile_clusters('enhanced_feature_model')
        
        # Compare models
        | print_cluster_summary('initial_feature_model')
        | print_cluster_summary('enhanced_feature_model')
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
        'monthly_spend': np.random.gamma(2, 50, initial_samples),
        'order_frequency': np.random.poisson(5, initial_samples),
        'avg_order_value': np.random.gamma(2, 30, initial_samples),
        'days_since_last_purchase': np.random.exponential(30, initial_samples),
        'total_purchases': np.random.poisson(20, initial_samples),
        'website_sessions': np.random.poisson(15, initial_samples),
        'email_open_rate': np.random.beta(2, 3, initial_samples)
    })
    
    # Create initial model
    print("Creating initial model...")
    retrain_model = (
        KMeansPipe.from_dataframe(initial_data)
        
        # Prepare data
        | prepare_clustering_data(
            feature_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'days_since_last_purchase', 'total_purchases',
                'website_sessions', 'email_open_rate'
            ],
            scaling_method='standard',
            remove_outliers=True
        )
        
        # Engineer features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency')
            ]
        )
        
        # Find optimal k
        | find_optimal_k(k_range=(2, 6), method='both', analysis_name='initial_retrain')
        
        # Configure and fit initial model
        | configure_kmeans(
            n_clusters=3,
            init='k-means++',
            n_init=15,
            model_name='initial_model'
        )
        
        | fit_kmeans('initial_model')
        | evaluate_clustering('initial_model')
        | profile_clusters('initial_model')
    )
    
    # Generate new data with different patterns
    print("\nGenerating new data with updated patterns...")
    new_samples = 600
    
    new_data = pd.DataFrame({
        'customer_id': range(initial_samples, initial_samples + new_samples),
        'age': np.random.randint(20, 75, new_samples),  # Slightly different age distribution
        'income': np.random.lognormal(10.2, 0.6, new_samples),  # Higher income trend
        'monthly_spend': np.random.gamma(2.2, 55, new_samples),  # Higher spending
        'order_frequency': np.random.poisson(6, new_samples),  # Higher frequency
        'avg_order_value': np.random.gamma(2.1, 32, new_samples),  # Higher order values
        'days_since_last_purchase': np.random.exponential(25, new_samples),  # More recent purchases
        'total_purchases': np.random.poisson(22, new_samples),  # More purchases
        'website_sessions': np.random.poisson(17, new_samples),  # More sessions
        'email_open_rate': np.random.beta(2.2, 2.8, new_samples)  # Higher engagement
    })
    
    # Retrain with new data
    print("\nRetraining model with new data...")
    retrain_model = (
        retrain_model
        
        # Retrain with new data
        | retrain_kmeans_model(
            model_name='initial_model',
            new_data=new_data,
            retrain_name='retrained_model'
        )
        
        # Evaluate retrained model
        | evaluate_clustering('retrained_model')
        | profile_clusters('retrained_model')
    )
    
    # Retrain with updated configuration
    print("\nRetraining with updated configuration...")
    retrain_model = (
        retrain_model
        
        # Retrain with updated parameters
        | retrain_kmeans_model(
            model_name='retrained_model',
            update_config={
                'n_clusters': 4,  # More clusters
                'n_init': 25,     # More initializations
                'max_iter': 400,  # More iterations
                'tol': 1e-5       # Tighter tolerance
            },
            retrain_name='optimized_model'
        )
        
        # Evaluate optimized model
        | evaluate_clustering('optimized_model')
        | profile_clusters('optimized_model')
        
        # Compare all models
        | print_cluster_summary('initial_model')
        | print_cluster_summary('retrained_model')
        | print_cluster_summary('optimized_model')
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
        'monthly_spend': np.random.gamma(2.5, 70, n_samples),
        'order_frequency': np.random.poisson(7, n_samples),
        'avg_order_value': np.random.gamma(2.2, 40, n_samples),
        'days_since_last_purchase': np.random.exponential(20, n_samples),
        'total_purchases': np.random.poisson(30, n_samples),
        'website_sessions': np.random.poisson(20, n_samples),
        'email_open_rate': np.random.beta(2.5, 2.5, n_samples),
        'preferred_category': np.random.choice(['Electronics', 'Fashion', 'Home', 'Sports', 'Books'], n_samples),
        'device_type': np.random.choice(['Mobile', 'Desktop', 'Tablet'], n_samples),
        'loyalty_program': np.random.choice(['Bronze', 'Silver', 'Gold', 'Platinum'], n_samples),
        'customer_support_contacts': np.random.poisson(3, n_samples),
        'return_rate': np.random.beta(1, 10, n_samples)
    })
    
    # Create comprehensive model
    print("Creating comprehensive prediction model...")
    prediction_model = (
        KMeansPipe.from_dataframe(prediction_data)
        
        # Prepare comprehensive features
        | prepare_clustering_data(
            feature_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'days_since_last_purchase', 'total_purchases',
                'website_sessions', 'email_open_rate'
            ],
            scaling_method='standard',
            remove_outliers=True
        )
        
        # Engineer comprehensive features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency'),
                ('website_sessions', 'total_purchases'),
                ('email_open_rate', 'age')
            ],
            polynomial_features=['monthly_spend', 'income']
        )
        
        # Find optimal k
        | find_optimal_k(k_range=(3, 8), method='both', analysis_name='prediction_segments')
        
        # Configure and fit model
        | configure_kmeans(
            n_clusters=5,
            init='k-means++',
            n_init=25,
            model_name='prediction_model'
        )
        
        | fit_kmeans('prediction_model')
        | evaluate_clustering('prediction_model')
        | profile_clusters('prediction_model')
    )
    
    # Scenario 1: Basic prediction on new data
    print("\nScenario 1: Basic prediction on new data...")
    new_data_1 = prediction_data.sample(n=300, random_state=100)
    
    prediction_model = (
        prediction_model
        
        | predict_clusters(
            model_name='prediction_model',
            new_data=new_data_1,
            prediction_name='basic_new_predictions'
        )
    )
    
    # Scenario 2: Prediction with feature subset
    print("\nScenario 2: Prediction with feature subset...")
    new_data_2 = prediction_data.sample(n=250, random_state=200)
    feature_subset = ['age', 'income', 'monthly_spend', 'order_frequency', 'avg_order_value']
    
    prediction_model = (
        prediction_model
        
        | predict_clusters(
            model_name='prediction_model',
            new_data=new_data_2,
            feature_subset=feature_subset,
            prediction_name='subset_predictions'
        )
    )
    
    # Scenario 3: Prediction on high-value customers
    print("\nScenario 3: Prediction on high-value customers...")
    high_value_data = prediction_data[
        (prediction_data['income'] > prediction_data['income'].quantile(0.8)) |
        (prediction_data['monthly_spend'] > prediction_data['monthly_spend'].quantile(0.8)) |
        (prediction_data['loyalty_program'].isin(['Gold', 'Platinum']))
    ].sample(n=150, random_state=300)
    
    prediction_model = (
        prediction_model
        
        | predict_clusters(
            model_name='prediction_model',
            new_data=high_value_data,
            prediction_name='high_value_predictions'
        )
    )
    
    # Get and analyze prediction results
    print("\nAnalyzing prediction results...")
    basic_results = prediction_model | get_prediction_results('basic_new_predictions')
    subset_results = prediction_model | get_prediction_results('subset_predictions')
    high_value_results = prediction_model | get_prediction_results('high_value_predictions')
    
    # Print comprehensive summary
    prediction_model = prediction_model | print_cluster_summary('prediction_model')
    
    # Analyze prediction distributions
    print("\nPrediction Analysis:")
    for pred_name in ['basic_new_predictions', 'subset_predictions', 'high_value_predictions']:
        if pred_name in prediction_model.predictions:
            pred_data = prediction_model.predictions[pred_name]
            predictions = pred_data['cluster_assignments']
            print(f"\n{pred_name}:")
            print(f"  Total predictions: {len(predictions)}")
            print(f"  Cluster distribution: {dict(pd.Series(predictions).value_counts().sort_index())}")
            print(f"  Average confidence: {np.mean(pred_data['data'][f'{pred_name}_confidence']):.3f}")
    
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
        'monthly_spend': np.random.gamma(3, 80, n_samples),
        'order_frequency': np.random.poisson(8, n_samples),
        'avg_order_value': np.random.gamma(2.5, 50, n_samples),
        'days_since_last_purchase': np.random.exponential(15, n_samples),
        'total_purchases': np.random.poisson(35, n_samples),
        'website_sessions': np.random.poisson(25, n_samples),
        'email_open_rate': np.random.beta(3, 2, n_samples),
        'preferred_category': np.random.choice(['Electronics', 'Fashion', 'Home', 'Sports', 'Books'], n_samples),
        'device_type': np.random.choice(['Mobile', 'Desktop', 'Tablet'], n_samples),
        'loyalty_program': np.random.choice(['Bronze', 'Silver', 'Gold', 'Platinum'], n_samples),
        'customer_support_contacts': np.random.poisson(4, n_samples),
        'return_rate': np.random.beta(1, 10, n_samples)
    })
    
    print("=== Complete K-means Model Lifecycle Demo ===")
    
    # Step 1: Initial Model Development
    print("\nStep 1: Initial Model Development")
    lifecycle_model = (
        KMeansPipe.from_dataframe(lifecycle_data)
        
        # Basic data preparation
        | prepare_clustering_data(
            feature_columns=[
                'age', 'income', 'monthly_spend', 'order_frequency',
                'avg_order_value', 'days_since_last_purchase', 'total_purchases',
                'website_sessions', 'email_open_rate'
            ],
            scaling_method='standard',
            remove_outliers=True
        )
        
        # Basic feature engineering
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency')
            ]
        )
        
        # Find optimal k
        | find_optimal_k(k_range=(3, 8), method='both', analysis_name='lifecycle_segments')
        
        # Configure and fit initial model
        | configure_kmeans(
            n_clusters=4,
            init='k-means++',
            n_init=20,
            model_name='lifecycle_model'
        )
        
        | fit_kmeans('lifecycle_model')
        | evaluate_clustering('lifecycle_model')
        | profile_clusters('lifecycle_model')
    )
    
    # Step 2: Model Enhancement
    print("\nStep 2: Model Enhancement")
    lifecycle_model = (
        lifecycle_model
        
        # Add more features
        | add_features(
            feature_columns=['preferred_category', 'device_type', 'loyalty_program'],
            feature_type='clustering',
            feature_name='additional_features'
        )
        
        # Enhanced feature engineering
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('monthly_spend', 'income'),
                ('avg_order_value', 'order_frequency'),
                ('website_sessions', 'total_purchases'),
                ('email_open_rate', 'age')
            ],
            polynomial_features=['monthly_spend', 'income']
        )
        
        # Retrain with enhanced features
        | retrain_kmeans_model(
            model_name='lifecycle_model',
            update_config={
                'n_clusters': 5,
                'n_init': 25,
                'max_iter': 400
            },
            retrain_name='enhanced_lifecycle_model'
        )
        
        # Enhanced evaluation
        | evaluate_clustering('enhanced_lifecycle_model')
        | profile_clusters('enhanced_lifecycle_model')
    )
    
    # Step 3: Model Optimization
    print("\nStep 3: Model Optimization")
    
    # Test different configurations
    configs = [
        {'n_clusters': 4, 'n_init': 20, 'max_iter': 300},
        {'n_clusters': 6, 'n_init': 30, 'max_iter': 500},
        {'n_clusters': 5, 'n_init': 25, 'max_iter': 400}
    ]
    
    best_silhouette = -1
    best_config = None
    best_model_name = None
    
    for i, config in enumerate(configs):
        model_name = f'optimized_model_{i}'
        
        lifecycle_model = (
            lifecycle_model
            
            | retrain_kmeans_model(
                model_name='enhanced_lifecycle_model',
                update_config=config,
                retrain_name=model_name
            )
            
            | evaluate_clustering(model_name)
        )
        
        # Check if this is the best model
        metrics = lifecycle_model.evaluation_metrics.get(model_name, {})
        silhouette = metrics.get('silhouette_score', -1)
        
        if silhouette > best_silhouette:
            best_silhouette = silhouette
            best_config = config
            best_model_name = model_name
    
    print(f"Best model: {best_model_name} with silhouette score: {best_silhouette:.4f}")
    
    # Step 4: Model Deployment
    print("\nStep 4: Model Deployment")
    lifecycle_model = (
        lifecycle_model
        
        # Save optimized model
        | save_kmeans_model(
            model_name=best_model_name,
            filepath='deployed_lifecycle_kmeans_model.joblib',
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
        'monthly_spend': np.random.gamma(3.2, 85, new_samples),  # Higher spending
        'order_frequency': np.random.poisson(9, new_samples),  # Higher frequency
        'avg_order_value': np.random.gamma(2.7, 55, new_samples),  # Higher order values
        'days_since_last_purchase': np.random.exponential(12, new_samples),  # More recent purchases
        'total_purchases': np.random.poisson(38, new_samples),  # More purchases
        'website_sessions': np.random.poisson(28, new_samples),  # More sessions
        'email_open_rate': np.random.beta(3.2, 1.8, new_samples),  # Higher engagement
        'preferred_category': np.random.choice(['Electronics', 'Fashion', 'Home', 'Sports', 'Books'], new_samples),
        'device_type': np.random.choice(['Mobile', 'Desktop', 'Tablet'], new_samples),
        'loyalty_program': np.random.choice(['Bronze', 'Silver', 'Gold', 'Platinum'], new_samples),
        'customer_support_contacts': np.random.poisson(5, new_samples),
        'return_rate': np.random.beta(1, 10, new_samples)
    })
    
    # Update model with new data
    lifecycle_model = (
        lifecycle_model
        
        # Retrain with new data
        | retrain_kmeans_model(
            model_name=best_model_name,
            new_data=new_data,
            retrain_name='updated_lifecycle_model'
        )
        
        # Make predictions on new data
        | predict_clusters(
            model_name='updated_lifecycle_model',
            new_data=new_data.sample(n=100, random_state=400),
            prediction_name='monitoring_predictions'
        )
        
        # Final evaluation
        | evaluate_clustering('updated_lifecycle_model')
        | print_cluster_summary('updated_lifecycle_model')
    )
    
    print("\n=== Model Lifecycle Completed Successfully ===")
    
    return lifecycle_model