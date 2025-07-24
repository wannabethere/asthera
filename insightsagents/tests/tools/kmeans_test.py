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
    print_cluster_summary
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