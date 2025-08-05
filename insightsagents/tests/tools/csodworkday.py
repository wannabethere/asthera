# HR Division & Employee Learning Analytics Examples
# K-means Clustering and Prophet Forecasting for Learning Data

from app.tools.mltools.models.kmeans_clustering import (
    KMeansPipe,
    prepare_clustering_data,
    engineer_clustering_features,
    reduce_dimensions,
    configure_kmeans,
    fit_kmeans,
    evaluate_clustering,
    profile_clusters,
    find_optimal_k,
    plot_clusters_2d,
    plot_cluster_profiles,
    plot_elbow_curve,
    save_kmeans_model,
    print_cluster_summary
)

from app.tools.mltools.models.prophet_forecast import (
    ProphetPipe,
    prepare_prophet_data,
    add_regressors,
    add_holidays,
    configure_prophet,
    add_custom_seasonality,
    fit_prophet,
    make_forecast,
    forecast_with_regressors,
    cross_validate_model,
    calculate_forecast_metrics,
    plot_forecast,
    save_prophet_model,
    print_prophet_summary
)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# =============================================================================
# K-MEANS CLUSTERING EXAMPLES
# =============================================================================

# Example 1: Division-Based Employee Performance Clustering
def example_division_employee_clustering():
    """
    Cluster employees by division based on training completion and performance patterns
    """
    # Generate CSOD-based training data by division
    np.random.seed(42)
    n_employees = 3000
    
    divisions = ['Administration', 'Acme Products', 'Private Operations']
    division_characteristics = {
        'Administration': {
            'completion_rate_mean': 0.85, 'completion_days_mean': 12, 'late_rate_mean': 0.15,
            'skill_focus': ['Compliance', 'Soft Skills'], 'training_volume': 'High'
        },
        'Acme Products': {
            'completion_rate_mean': 0.78, 'completion_days_mean': 18, 'late_rate_mean': 0.25,
            'skill_focus': ['Technical', 'Digital'], 'training_volume': 'Medium'
        },
        'Private Operations': {
            'completion_rate_mean': 0.72, 'completion_days_mean': 22, 'late_rate_mean': 0.30,
            'skill_focus': ['Leadership', 'Technical'], 'training_volume': 'Low'
        }
    }
    
    employee_data = []
    for i in range(n_employees):
        # Assign division
        division = np.random.choice(divisions)
        div_char = division_characteristics[division]
        
        # Employee demographics
        age = np.random.normal(38, 12)
        tenure_months = np.random.exponential(30)
        position = np.random.choice(['Individual Contributor', 'Senior', 'Lead', 'Manager'], 
                                  p=[0.5, 0.3, 0.15, 0.05])
        
        # Training metrics influenced by division
        base_completion_rate = np.random.normal(div_char['completion_rate_mean'], 0.15)
        completion_rate = np.clip(base_completion_rate, 0.3, 1.0)
        
        base_completion_days = np.random.normal(div_char['completion_days_mean'], 5)
        avg_completion_days = max(3, base_completion_days)
        
        base_late_rate = np.random.normal(div_char['late_rate_mean'], 0.08)
        late_completion_rate = np.clip(base_late_rate, 0.0, 0.6)
        
        # Training volume by division
        volume_multiplier = {'High': 1.5, 'Medium': 1.0, 'Low': 0.7}[div_char['training_volume']]
        total_assignments = max(5, int(np.random.poisson(20) * volume_multiplier))
        completed_assignments = int(total_assignments * completion_rate)
        
        # Skills development (Workday-based)
        skills_developed = np.random.poisson(8) if completion_rate > 0.8 else np.random.poisson(4)
        avg_proficiency_improvement = np.random.normal(1.8, 0.6) if completion_rate > 0.7 else np.random.normal(1.0, 0.4)
        
        # Performance indicators
        performance_rating = np.random.normal(3.5, 0.8)
        if completion_rate > 0.9:
            performance_rating += 0.5
        elif completion_rate < 0.6:
            performance_rating -= 0.3
            
        # Manager and engagement metrics
        manager_interactions = np.random.poisson(6)
        career_development_active = np.random.choice([0, 1], p=[0.4, 0.6])
        
        # Overdue training (current status)
        overdue_count = np.random.poisson(3) if late_completion_rate > 0.3 else np.random.poisson(1)
        
        employee_data.append({
            'employee_id': f'EMP_{i:04d}',
            'full_name': f'Employee_{i:04d}',
            'division': division,
            'position': position,
            'age': max(22, min(65, age)),
            'tenure_months': max(1, tenure_months),
            'training_completion_rate': completion_rate,
            'avg_completion_days': avg_completion_days,
            'late_completion_rate': late_completion_rate,
            'total_training_assignments': total_assignments,
            'completed_assignments': completed_assignments,
            'skills_developed': max(0, skills_developed),
            'avg_proficiency_improvement': max(0.1, avg_proficiency_improvement),
            'performance_rating': np.clip(performance_rating, 1.0, 5.0),
            'manager_interactions_per_month': max(0, manager_interactions),
            'career_development_active': career_development_active,
            'overdue_training_count': max(0, overdue_count),
            'certifications_earned': np.random.poisson(2),
            'training_hours_completed': completed_assignments * np.random.uniform(2, 8),
            'manager_support_score': np.random.uniform(2.5, 5.0),
            'succession_planning_participant': np.random.choice([0, 1], p=[0.8, 0.2])
        })
    
    employee_df = pd.DataFrame(employee_data)
    
    # Division-based employee clustering pipeline
    division_clustering = (
        KMeansPipe.from_dataframe(employee_df)
        
        # Prepare clustering features
        | prepare_clustering_data(
            feature_columns=[
                'age', 'tenure_months', 'training_completion_rate', 'avg_completion_days',
                'late_completion_rate', 'total_training_assignments', 'completed_assignments',
                'skills_developed', 'avg_proficiency_improvement', 'performance_rating',
                'manager_interactions_per_month', 'career_development_active',
                'overdue_training_count', 'certifications_earned', 'training_hours_completed',
                'manager_support_score', 'succession_planning_participant'
            ],
            scaling_method='standard',
            remove_outliers=True,
            outlier_method='iqr'
        )
        
        # Engineer division-specific features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('completed_assignments', 'total_training_assignments'),
                ('skills_developed', 'training_hours_completed'),
                ('performance_rating', 'manager_support_score'),
                ('certifications_earned', 'tenure_months')
            ],
            polynomial_features=['training_completion_rate', 'performance_rating']
        )
        
        # Dimensionality reduction for visualization
        | reduce_dimensions(method='pca', n_components=2, reducer_name='division_pca')
        
        # Find optimal clusters
        | find_optimal_k(k_range=(3, 8), method='both', analysis_name='division_segments')
        | plot_elbow_curve('division_segments')
        
        # Configure clustering model
        | configure_kmeans(
            n_clusters=5,  # Based on business intuition: High/Medium/Low performers + Specialists
            init='k-means++',
            n_init=25,
            model_name='division_employee_clusters'
        )
        
        # Fit and evaluate
        | fit_kmeans('division_employee_clusters')
        | evaluate_clustering('division_employee_clusters')
        
        # Create detailed profiles
        | profile_clusters(
            'division_employee_clusters',
            profile_columns=[
                'division', 'position', 'age', 'tenure_months', 'training_completion_rate',
                'avg_completion_days', 'performance_rating', 'skills_developed',
                'manager_support_score', 'succession_planning_participant'
            ],
            include_categorical=True
        )
        
        # Visualize clusters
        | plot_clusters_2d('division_employee_clusters', 'training_completion_rate', 'performance_rating')
        | plot_clusters_2d('division_employee_clusters', 'division_pca_dim_1', 'division_pca_dim_2')
        | plot_cluster_profiles('division_employee_clusters', 'numerical', top_k_features=10)
        | plot_cluster_profiles('division_employee_clusters', 'categorical')
        
        # Print summary
        | print_cluster_summary('division_employee_clusters')
        
        # Save model
        | save_kmeans_model('division_employee_clusters', 'division_employee_clustering_model.joblib')
    )
    
    # Business Analysis
    print("\n=== Division-Based Employee Clustering Analysis ===")
    
    # Analyze cluster distribution by division
    cluster_col = division_clustering.cluster_assignments['division_employee_clusters']['cluster_column']
    division_cluster_analysis = pd.crosstab(
        employee_df['division'], 
        division_clustering.data[cluster_col], 
        normalize='index'
    ) * 100
    
    print("\nCluster Distribution by Division (%):")
    print(division_cluster_analysis.round(1))
    
    # Performance analysis by cluster
    cluster_performance = division_clustering.data.groupby(cluster_col).agg({
        'training_completion_rate': 'mean',
        'performance_rating': 'mean',
        'skills_developed': 'mean',
        'avg_completion_days': 'mean',
        'overdue_training_count': 'mean'
    }).round(3)
    
    print("\nCluster Performance Summary:")
    print(cluster_performance)
    
    # Division-specific insights
    for division in divisions:
        div_data = employee_df[employee_df['division'] == division]
        print(f"\n{division} Division Summary:")
        print(f"  Employees: {len(div_data)}")
        print(f"  Avg Completion Rate: {div_data['training_completion_rate'].mean():.3f}")
        print(f"  Avg Performance Rating: {div_data['performance_rating'].mean():.3f}")
        print(f"  High Performers (>4.0 rating): {(div_data['performance_rating'] > 4.0).sum()}")
    
    return division_clustering


# Example 2: Learning Behavior Clustering
def example_learning_behavior_clustering():
    """
    Cluster employees based on learning behaviors and preferences
    """
    # Generate learning behavior data
    np.random.seed(123)
    n_employees = 2500
    
    # Learning behavior archetypes
    behavior_types = ['Self-Directed Learner', 'Structured Learner', 'Social Learner', 
                     'Reluctant Learner', 'Just-in-Time Learner']
    
    learning_data = []
    for i in range(n_employees):
        # Assign behavior type for validation
        behavior_type = np.random.choice(behavior_types)
        
        # Demographics
        division = np.random.choice(['Administration', 'Acme Products', 'Private Operations'])
        job_level = np.random.choice(['Individual Contributor', 'Senior', 'Lead', 'Manager'], 
                                   p=[0.4, 0.3, 0.2, 0.1])
        age = np.random.normal(36, 10)
        tenure = np.random.exponential(36)
        
        # Generate behavior patterns based on archetype
        if behavior_type == 'Self-Directed Learner':
            voluntary_learning_hours = np.random.gamma(3, 15)
            formal_training_preference = np.random.uniform(0.3, 0.7)
            online_learning_preference = np.random.uniform(0.7, 1.0)
            learning_frequency_days = np.random.uniform(2, 7)
            collaboration_score = np.random.uniform(0.4, 0.8)
            completion_speed = np.random.uniform(0.8, 1.2)  # Faster than average
            
        elif behavior_type == 'Structured Learner':
            voluntary_learning_hours = np.random.gamma(2, 10)
            formal_training_preference = np.random.uniform(0.8, 1.0)
            online_learning_preference = np.random.uniform(0.4, 0.8)
            learning_frequency_days = np.random.uniform(7, 14)
            collaboration_score = np.random.uniform(0.2, 0.6)
            completion_speed = np.random.uniform(0.9, 1.1)  # Average speed
            
        elif behavior_type == 'Social Learner':
            voluntary_learning_hours = np.random.gamma(2.5, 12)
            formal_training_preference = np.random.uniform(0.6, 0.9)
            online_learning_preference = np.random.uniform(0.3, 0.7)
            learning_frequency_days = np.random.uniform(3, 10)
            collaboration_score = np.random.uniform(0.8, 1.0)
            completion_speed = np.random.uniform(0.7, 1.0)  # Slower due to discussion
            
        elif behavior_type == 'Reluctant Learner':
            voluntary_learning_hours = np.random.gamma(1, 5)
            formal_training_preference = np.random.uniform(0.2, 0.6)
            online_learning_preference = np.random.uniform(0.2, 0.6)
            learning_frequency_days = np.random.uniform(21, 60)
            collaboration_score = np.random.uniform(0.1, 0.4)
            completion_speed = np.random.uniform(0.5, 0.8)  # Slower completion
            
        else:  # Just-in-Time Learner
            voluntary_learning_hours = np.random.gamma(1.5, 8)
            formal_training_preference = np.random.uniform(0.3, 0.7)
            online_learning_preference = np.random.uniform(0.8, 1.0)
            learning_frequency_days = np.random.uniform(1, 30)  # Irregular
            collaboration_score = np.random.uniform(0.3, 0.7)
            completion_speed = np.random.uniform(1.1, 1.5)  # Very fast when needed
        
        # Additional learning metrics
        courses_started = np.random.poisson(12)
        courses_completed = int(courses_started * np.random.uniform(0.4, 1.0))
        avg_course_rating = np.random.uniform(2.5, 5.0)
        
        # Engagement metrics
        forum_participation = np.random.poisson(collaboration_score * 10)
        knowledge_sharing_contributions = np.random.poisson(collaboration_score * 5)
        mentoring_activities = np.random.choice([0, 1], p=[0.7, 0.3])
        
        # Performance outcomes
        skill_assessments_passed = np.random.poisson(4)
        certification_attempts = np.random.poisson(2)
        certifications_earned = min(certification_attempts, np.random.poisson(1.5))
        
        # Time and resource usage
        mobile_learning_usage_pct = np.random.uniform(0.2, 0.8)
        peak_learning_time = np.random.choice(['Morning', 'Afternoon', 'Evening'], p=[0.4, 0.4, 0.2])
        learning_interruption_frequency = np.random.uniform(0.1, 0.8)
        
        learning_data.append({
            'employee_id': f'LEARNER_{i:04d}',
            'division': division,
            'job_level': job_level,
            'age': max(22, min(65, age)),
            'tenure_months': max(1, tenure),
            'voluntary_learning_hours_per_month': max(0, voluntary_learning_hours),
            'formal_training_preference_score': formal_training_preference,
            'online_learning_preference_score': online_learning_preference,
            'learning_frequency_days': learning_frequency_days,
            'collaboration_score': collaboration_score,
            'completion_speed_factor': completion_speed,
            'courses_started': max(0, courses_started),
            'courses_completed': max(0, courses_completed),
            'completion_rate': courses_completed / max(1, courses_started),
            'avg_course_rating': avg_course_rating,
            'forum_participation_count': max(0, forum_participation),
            'knowledge_sharing_contributions': max(0, knowledge_sharing_contributions),
            'mentoring_activities': mentoring_activities,
            'skill_assessments_passed': max(0, skill_assessments_passed),
            'certification_attempts': max(0, certification_attempts),
            'certifications_earned': max(0, certifications_earned),
            'mobile_learning_usage_pct': mobile_learning_usage_pct,
            'peak_learning_time': peak_learning_time,
            'learning_interruption_frequency': learning_interruption_frequency,
            'true_behavior_type': behavior_type
        })
    
    learning_df = pd.DataFrame(learning_data)
    
    # Learning behavior clustering pipeline
    behavior_clustering = (
        KMeansPipe.from_dataframe(learning_df)
        
        # Prepare learning behavior features
        | prepare_clustering_data(
            feature_columns=[
                'age', 'tenure_months', 'voluntary_learning_hours_per_month',
                'formal_training_preference_score', 'online_learning_preference_score',
                'learning_frequency_days', 'collaboration_score', 'completion_speed_factor',
                'courses_started', 'courses_completed', 'completion_rate',
                'avg_course_rating', 'forum_participation_count', 'knowledge_sharing_contributions',
                'mentoring_activities', 'skill_assessments_passed', 'certification_attempts',
                'certifications_earned', 'mobile_learning_usage_pct', 'learning_interruption_frequency'
            ],
            scaling_method='robust',
            remove_outliers=True,
            outlier_method='zscore',
            outlier_threshold=2.5
        )
        
        # Engineer learning-specific features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('courses_completed', 'voluntary_learning_hours_per_month'),
                ('certifications_earned', 'certification_attempts'),
                ('knowledge_sharing_contributions', 'collaboration_score'),
                ('skill_assessments_passed', 'courses_completed')
            ],
            polynomial_features=['collaboration_score', 'completion_rate'],
            binning_features={
                'learning_frequency_days': 4,
                'voluntary_learning_hours_per_month': 5
            }
        )
        
        # Dimensionality reduction
        | reduce_dimensions(method='pca', n_components=2, reducer_name='behavior_pca')
        | reduce_dimensions(method='tsne', n_components=2, reducer_name='behavior_tsne')
        
        # Find optimal number of behavior clusters
        | find_optimal_k(k_range=(3, 8), method='both', analysis_name='behavior_segments')
        | plot_elbow_curve('behavior_segments')
        
        # Configure clustering
        | configure_kmeans(
            n_clusters=5,  # Matching our behavior archetypes
            init='k-means++',
            n_init=30,
            max_iter=500,
            model_name='learning_behavior_clusters'
        )
        
        # Fit and evaluate
        | fit_kmeans('learning_behavior_clusters')
        | evaluate_clustering('learning_behavior_clusters')
        
        # Create comprehensive profiles
        | profile_clusters(
            'learning_behavior_clusters',
            profile_columns=[
                'division', 'job_level', 'age', 'tenure_months', 'voluntary_learning_hours_per_month',
                'formal_training_preference_score', 'online_learning_preference_score',
                'collaboration_score', 'completion_rate', 'peak_learning_time'
            ],
            include_categorical=True
        )
        
        # Visualizations
        | plot_clusters_2d('learning_behavior_clusters', 'collaboration_score', 'completion_rate')
        | plot_clusters_2d('learning_behavior_clusters', 'behavior_pca_dim_1', 'behavior_pca_dim_2')
        | plot_clusters_2d('learning_behavior_clusters', 'behavior_tsne_dim_1', 'behavior_tsne_dim_2')
        | plot_cluster_profiles('learning_behavior_clusters', 'numerical', top_k_features=12)
        | plot_cluster_profiles('learning_behavior_clusters', 'categorical')
        
        # Summary
        | print_cluster_summary('learning_behavior_clusters')
        | save_kmeans_model('learning_behavior_clusters', 'learning_behavior_clustering_model.joblib')
    )
    
    # Validation against true behavior types
    print("\n=== Learning Behavior Clustering Analysis ===")
    
    cluster_col = behavior_clustering.cluster_assignments['learning_behavior_clusters']['cluster_column']
    behavior_validation = pd.crosstab(
        learning_df['true_behavior_type'],
        behavior_clustering.data[cluster_col],
        normalize='index'
    ) * 100
    
    print("\nBehavior Type vs Cluster Distribution (%):")
    print(behavior_validation.round(1))
    
    # Cluster characteristics
    cluster_summary = behavior_clustering.data.groupby(cluster_col).agg({
        'voluntary_learning_hours_per_month': 'mean',
        'collaboration_score': 'mean',
        'completion_rate': 'mean',
        'online_learning_preference_score': 'mean',
        'certifications_earned': 'mean'
    }).round(3)
    
    print("\nCluster Learning Characteristics:")
    print(cluster_summary)
    
    return behavior_clustering


# Example 3: Skills Development Clustering by Division
def example_skills_development_clustering():
    """
    Cluster employees based on skills development patterns within divisions
    """
    # Generate Workday-style skills development data
    np.random.seed(456)
    n_assessments = 4000
    
    divisions = ['Administration', 'Acme Products', 'Private Operations']
    skill_categories = ['Technical', 'Leadership', 'Compliance', 'Soft Skills', 'Digital']
    competency_frameworks = ['Engineering', 'Management', 'Sales', 'Operations', 'Support']
    
    # Division-specific skill priorities
    division_skill_focus = {
        'Administration': ['Compliance', 'Soft Skills', 'Leadership'],
        'Acme Products': ['Technical', 'Digital', 'Leadership'],
        'Private Operations': ['Leadership', 'Technical', 'Compliance']
    }
    
    skills_data = []
    for i in range(n_assessments):
        # Employee assignment
        division = np.random.choice(divisions)
        employee_id = f'SKL_EMP_{np.random.randint(1000, 3000):04d}'
        
        # Demographics
        job_level = np.random.choice(['Individual Contributor', 'Senior', 'Lead', 'Manager'], 
                                   p=[0.4, 0.3, 0.2, 0.1])
        tenure_months = np.random.exponential(42)
        
        # Skill characteristics
        skill_category = np.random.choice(division_skill_focus[division])
        competency_framework = np.random.choice(competency_frameworks)
        skill_criticality = np.random.choice(['Critical', 'Important', 'Beneficial'], p=[0.3, 0.5, 0.2])
        
        # Proficiency levels (influenced by division and role)
        target_proficiency = np.random.choice([3, 4, 5], p=[0.5, 0.3, 0.2])
        
        # Division-specific performance patterns
        if division == 'Administration':
            pre_training_proficiency = np.random.uniform(2.0, 3.5)
            training_effectiveness = 1.2  # Good training programs
        elif division == 'Acme Products':
            pre_training_proficiency = np.random.uniform(1.5, 3.0)
            training_effectiveness = 1.0  # Average training programs
        else:  # Private Operations
            pre_training_proficiency = np.random.uniform(1.0, 2.8)
            training_effectiveness = 0.8  # Needs improvement
        
        # Post-training proficiency
        training_impact = np.random.normal(1.5 * training_effectiveness, 0.5)
        post_training_proficiency = min(5.0, pre_training_proficiency + max(0, training_impact))
        
        # Training investment and outcomes
        training_cost = np.random.gamma(2, 400)
        training_hours = np.random.gamma(2, 15)
        
        # Assessment details
        assessment_method = np.random.choice(['Self-Assessment', 'Manager Review', 'Certification', 'Practical Test'])
        certification_earned = np.random.choice(['', 'Basic Cert', 'Advanced Cert', 'Professional License'], 
                                              p=[0.6, 0.2, 0.15, 0.05])
        
        # Performance correlation
        performance_rating = np.random.normal(3.5, 0.7)
        if post_training_proficiency >= target_proficiency:
            performance_rating += 0.3
        
        # Career development indicators
        career_development_plan = np.random.choice(['', 'Leadership Track', 'Technical Track', 'Cross-functional'], 
                                                 p=[0.4, 0.2, 0.25, 0.15])
        succession_plan_role = np.random.choice(['', 'Team Lead', 'Manager', 'Senior Manager'], 
                                              p=[0.7, 0.15, 0.1, 0.05])
        
        skills_data.append({
            'assessment_id': f'ASSESS_{i:04d}',
            'employee_id': employee_id,
            'division': division,
            'job_level': job_level,
            'tenure_months': max(1, tenure_months),
            'skill_category': skill_category,
            'competency_framework': competency_framework,
            'skill_criticality': skill_criticality,
            'pre_training_proficiency': round(pre_training_proficiency, 1),
            'post_training_proficiency': round(post_training_proficiency, 1),
            'target_proficiency': target_proficiency,
            'proficiency_improvement': round(post_training_proficiency - pre_training_proficiency, 1),
            'target_gap': max(0, round(target_proficiency - post_training_proficiency, 1)),
            'training_cost': training_cost,
            'training_hours': max(1, training_hours),
            'assessment_method': assessment_method,
            'certification_earned': certification_earned,
            'performance_rating': np.clip(performance_rating, 1.0, 5.0),
            'career_development_plan': career_development_plan,
            'succession_plan_role': succession_plan_role,
            'is_skill_proficient': post_training_proficiency >= target_proficiency,
            'roi_indicator': (post_training_proficiency - pre_training_proficiency) / training_cost * 1000 if training_cost > 0 else 0
        })
    
    skills_df = pd.DataFrame(skills_data)
    
    # Skills development clustering pipeline
    skills_clustering = (
        KMeansPipe.from_dataframe(skills_df)
        
        # Prepare skills development features
        | prepare_clustering_data(
            feature_columns=[
                'tenure_months', 'pre_training_proficiency', 'post_training_proficiency',
                'target_proficiency', 'proficiency_improvement', 'target_gap',
                'training_cost', 'training_hours', 'performance_rating',
                'is_skill_proficient', 'roi_indicator'
            ],
            scaling_method='standard',
            remove_outliers=True,
            outlier_method='iqr'
        )
        
        # Engineer skills-specific features
        | engineer_clustering_features(
            interaction_features=True,
            ratio_features=[
                ('proficiency_improvement', 'training_cost'),
                ('post_training_proficiency', 'target_proficiency'),
                ('training_hours', 'proficiency_improvement'),
                ('performance_rating', 'post_training_proficiency')
            ],
            polynomial_features=['post_training_proficiency', 'roi_indicator'],
            binning_features={
                'training_cost': 5,
                'training_hours': 4
            }
        )
        
        # Dimensionality reduction
        | reduce_dimensions(method='pca', n_components=3, reducer_name='skills_pca')
        
        # Find optimal clusters
        | find_optimal_k(k_range=(4, 10), method='both', analysis_name='skills_segments')
        | plot_elbow_curve('skills_segments')
        
        # Configure clustering
        | configure_kmeans(
            n_clusters=6,  # Different skill development patterns
            init='k-means++',
            n_init=25,
            max_iter=400,
            model_name='skills_development_clusters'
        )
        
        # Fit and evaluate
        | fit_kmeans('skills_development_clusters')
        | evaluate_clustering('skills_development_clusters')
        
        # Create profiles
        | profile_clusters(
            'skills_development_clusters',
            profile_columns=[
                'division', 'job_level', 'skill_category', 'competency_framework',
                'skill_criticality', 'pre_training_proficiency', 'post_training_proficiency',
                'proficiency_improvement', 'training_cost', 'performance_rating',
                'certification_earned', 'career_development_plan'
            ],
            include_categorical=True
        )
        
        # Visualizations
        | plot_clusters_2d('skills_development_clusters', 'proficiency_improvement', 'roi_indicator')
        | plot_clusters_2d('skills_development_clusters', 'pre_training_proficiency', 'post_training_proficiency')
        | plot_cluster_profiles('skills_development_clusters', 'numerical', top_k_features=10)
        | plot_cluster_profiles('skills_development_clusters', 'categorical')
        
        # Summary
        | print_cluster_summary('skills_development_clusters')
        | save_kmeans_model('skills_development_clusters', 'skills_development_clustering_model.joblib')
    )
    
    # Business Analysis
    print("\n=== Skills Development Clustering Analysis ===")
    
    cluster_col = skills_clustering.cluster_assignments['skills_development_clusters']['cluster_column']
    
    # Division analysis
    division_cluster_analysis = pd.crosstab(
        skills_df['division'],
        skills_clustering.data[cluster_col],
        normalize='index'
    ) * 100
    
    print("\nSkills Cluster Distribution by Division (%):")
    print(division_cluster_analysis.round(1))
    
    # Skill category analysis
    category_cluster_analysis = pd.crosstab(
        skills_df['skill_category'],
        skills_clustering.data[cluster_col],
        normalize='index'
    ) * 100
    
    print("\nSkills Cluster Distribution by Skill Category (%):")
    print(category_cluster_analysis.round(1))
    
    # Performance summary by cluster
    cluster_performance = skills_clustering.data.groupby(cluster_col).agg({
        'proficiency_improvement': 'mean',
        'roi_indicator': 'mean',
        'training_cost': 'mean',
        'performance_rating': 'mean',
        'is_skill_proficient': 'mean'
    }).round(3)
    
    print("\nCluster Performance Summary:")
    print(cluster_performance)
    
    # Division-specific ROI analysis
    print("\nROI Analysis by Division:")
    for division in divisions:
        div_data = skills_df[skills_df['division'] == division]
        print(f"\n{division}:")
        print(f"  Avg Proficiency Improvement: {div_data['proficiency_improvement'].mean():.2f}")
        print(f"  Avg ROI Indicator: {div_data['roi_indicator'].mean():.2f}")
        print(f"  Skills Proficiency Rate: {div_data['is_skill_proficient'].mean():.3f}")
        print(f"  Total Training Investment: ${div_data['training_cost'].sum():.0f}")
    
    return skills_clustering


# =============================================================================
# PROPHET FORECASTING EXAMPLES
# =============================================================================

# Example 4: Training Completion Forecasting by Division
def example_training_completion_forecasting():
    """
    Forecast training completion trends by division using Prophet
    """
    # Generate historical training completion data
    np.random.seed(789)
    
    # Create 3 years of daily training completion data
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2023, 12, 31)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    divisions = ['Administration', 'Acme Products', 'Private Operations']
    
    all_training_data = []
    
    for division in divisions:
        # Division-specific patterns
        if division == 'Administration':
            base_completions = 25
            growth_rate = 0.0003  # Steady growth
            seasonality_strength = 0.3
            weekend_effect = -0.6  # Lower weekend activity
        elif division == 'Acme Products':
            base_completions = 35
            growth_rate = 0.0005  # Higher growth
            seasonality_strength = 0.4
            weekend_effect = -0.4
        else:  # Private Operations
            base_completions = 20
            growth_rate = 0.0001  # Slower growth
            seasonality_strength = 0.2
            weekend_effect = -0.3
        
        for i, date in enumerate(date_range):
            # Base trend
            trend = base_completions + (i * growth_rate)
            
            # Seasonal patterns
            yearly_season = seasonality_strength * 10 * np.sin(2 * np.pi * i / 365.25)
            monthly_season = seasonality_strength * 5 * np.sin(2 * np.pi * i / 30)
            
            # Weekly pattern (lower on weekends)
            day_of_week = date.weekday()
            weekly_effect = weekend_effect * base_completions if day_of_week >= 5 else 0
            
            # Holiday effects
            holiday_effect = 0
            if date.month == 12 and date.day >= 20:  # Holiday season
                holiday_effect = -0.4 * base_completions
            elif date.month == 1 and date.day <= 7:  # New Year
                holiday_effect = -0.3 * base_completions
            elif date.month == 7:  # Summer vacation
                holiday_effect = -0.2 * base_completions
            
            # Training campaign effects (quarterly pushes)
            campaign_effect = 0
            if date.month in [3, 6, 9, 12] and date.day <= 15:  # Quarter-end pushes
                campaign_effect = 0.3 * base_completions
            
            # External factors (simulated)
            manager_push_effect = np.random.choice([0, 0.2 * base_completions], p=[0.9, 0.1])
            system_downtime_effect = np.random.choice([0, -0.5 * base_completions], p=[0.98, 0.02])
            
            # Combine all effects
            daily_completions = (trend + yearly_season + monthly_season + weekly_effect + 
                               holiday_effect + campaign_effect + manager_push_effect + 
                               system_downtime_effect + np.random.normal(0, 3))
            
            daily_completions = max(0, daily_completions)
            
            all_training_data.append({
                'date': date,
                'division': division,
                'daily_completions': daily_completions,
                'manager_push': 1 if manager_push_effect > 0 else 0,
                'system_downtime': 1 if system_downtime_effect < 0 else 0,
                'campaign_active': 1 if campaign_effect > 0 else 0,
                'is_weekend': 1 if day_of_week >= 5 else 0,
                'month': date.month,
                'quarter': (date.month - 1) // 3 + 1
            })
    
    training_forecast_df = pd.DataFrame(all_training_data)
    
    # Create separate forecasting models for each division
    forecast_results = {}
    
    for division in divisions:
        print(f"\n=== Forecasting Training Completions for {division} ===")
        
        # Filter data for specific division
        division_data = training_forecast_df[training_forecast_df['division'] == division].copy()
        
        # Training completion forecasting pipeline
        division_forecast = (
            ProphetPipe.from_dataframe(division_data)
            
            # Prepare Prophet data
            | prepare_prophet_data(
                date_column='date',
                value_column='daily_completions'
            )
            
            # Add external regressors (need to merge with original data)
            | add_regressors(
                regressor_columns=['manager_push', 'system_downtime', 'campaign_active', 'is_weekend'],
                regressor_data=division_data[['date', 'manager_push', 'system_downtime', 'campaign_active', 'is_weekend']].rename(columns={'date': 'ds'}),
                prior_scale=0.1
            )
            
            # Create holiday dataframe for training-specific events
            # (In practice, this would include company holidays, training deadlines, etc.)
            
            # Configure Prophet
            | configure_prophet(
                growth='linear',
                seasonality_mode='additive',
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10.0,
                model_name=f'{division.lower()}_training_model'
            )
            
            # Add custom seasonalities
            | add_custom_seasonality(
                name='monthly',
                period=30.5,
                fourier_order=3,
                model_name=f'{division.lower()}_training_model'
            )
            
            | add_custom_seasonality(
                name='quarterly',
                period=91.25,
                fourier_order=2,
                model_name=f'{division.lower()}_training_model'
            )
            
            # Fit model
            | fit_prophet(model_name=f'{division.lower()}_training_model')
            
            # Make 90-day forecast
            | forecast_with_regressors(
                periods=90,
                regressor_future_values={
                    'manager_push': np.random.choice([0, 1], 90, p=[0.9, 0.1]),
                    'system_downtime': np.random.choice([0, 1], 90, p=[0.98, 0.02]),
                    'campaign_active': [1 if (i % 91) < 15 else 0 for i in range(90)],  # Quarterly campaigns
                    'is_weekend': [1 if (i % 7) >= 5 else 0 for i in range(90)]
                },
                model_name=f'{division.lower()}_training_model'
            )
            
            # Cross-validate
            | cross_validate_model(
                initial='365 days',
                period='90 days',
                horizon='30 days',
                model_name=f'{division.lower()}_training_model'
            )
            
            # Calculate metrics
            | calculate_forecast_metrics(f'{division.lower()}_training_model_forecast_with_regressors')
            
            # Plot results
            | plot_forecast(f'{division.lower()}_training_model_forecast_with_regressors', show_components=True)
            
            # Save model
            | save_prophet_model(f'{division.lower()}_training_model', f'{division.lower()}_training_forecast_model.joblib')
            
            # Print summary
            | print_prophet_summary()
        )
        
        forecast_results[division] = division_forecast
    
    # Comparative analysis
    print("\n=== Training Completion Forecasting Analysis ===")
    
    # Current completion rates by division
    current_rates = training_forecast_df.groupby('division')['daily_completions'].agg(['mean', 'std', 'sum'])
    print("\nCurrent Training Completion Statistics:")
    print(current_rates.round(2))
    
    # Seasonal patterns
    seasonal_analysis = training_forecast_df.groupby(['division', 'month'])['daily_completions'].mean().unstack('division')
    print(f"\nMonthly Seasonal Patterns:")
    print(seasonal_analysis.round(1))
    
    # Weekend vs weekday analysis
    weekend_analysis = training_forecast_df.groupby(['division', 'is_weekend'])['daily_completions'].mean().unstack('division')
    print(f"\nWeekend vs Weekday Completion Rates:")
    print(weekend_analysis.round(1))
    
    return forecast_results


# Example 5: Skills Development Progression Forecasting
def example_skills_progression_forecasting():
    """
    Forecast skills development progression trends using Prophet
    """
    # Generate historical skills assessment data
    np.random.seed(999)
    
    # Create 2.5 years of weekly skills assessment data
    start_date = datetime(2021, 6, 1)
    end_date = datetime(2023, 12, 31)
    date_range = pd.date_range(start=start_date, end=end_date, freq='W')
    
    skill_categories = ['Technical', 'Leadership', 'Compliance', 'Soft Skills', 'Digital']
    
    all_skills_data = []
    
    for skill_category in skill_categories:
        # Category-specific progression patterns
        if skill_category == 'Technical':
            base_proficiency = 2.8
            growth_rate = 0.005  # Steady technical skill growth
            volatility = 0.1
        elif skill_category == 'Leadership':
            base_proficiency = 2.5
            growth_rate = 0.003  # Slower leadership development
            volatility = 0.15
        elif skill_category == 'Compliance':
            base_proficiency = 3.2
            growth_rate = 0.001  # Minimal growth (maintenance)
            volatility = 0.05
        elif skill_category == 'Soft Skills':
            base_proficiency = 3.0
            growth_rate = 0.004  # Moderate growth
            volatility = 0.12
        else:  # Digital
            base_proficiency = 2.6
            growth_rate = 0.008  # Rapid digital skill growth
            volatility = 0.2
        
        for i, date in enumerate(date_range):
            # Base trend
            trend = base_proficiency + (i * growth_rate)
            
            # Seasonal effects (training cycles)
            quarterly_season = 0.1 * np.sin(2 * np.pi * i / 13)  # 13 weeks per quarter
            
            # Training program effects
            training_boost = 0
            if i % 26 < 4:  # Intensive training periods twice a year
                training_boost = 0.2
            
            # End-of-year assessment effects
            if date.month == 12:
                training_boost += 0.15  # Year-end skill development push
            
            # Economic/industry factors
            industry_factor = 0.05 * np.sin(2 * np.pi * i / 52)  # Annual industry cycles
            
            # Random events (new tools, methodologies, etc.)
            random_boost = np.random.choice([0, 0.1, -0.05], p=[0.8, 0.15, 0.05])
            
            # Calculate average proficiency
            avg_proficiency = (trend + quarterly_season + training_boost + 
                             industry_factor + random_boost + 
                             np.random.normal(0, volatility))
            
            avg_proficiency = np.clip(avg_proficiency, 1.0, 5.0)
            
            # Generate related metrics
            assessments_completed = max(10, int(np.random.poisson(50)))
            proficiency_improvement = max(0, np.random.normal(0.1, 0.05))
            training_investment = np.random.gamma(2, 5000)
            
            all_skills_data.append({
                'date': date,
                'skill_category': skill_category,
                'avg_proficiency_score': avg_proficiency,
                'assessments_completed': assessments_completed,
                'proficiency_improvement': proficiency_improvement,
                'training_investment': training_investment,
                'training_program_active': 1 if training_boost > 0.1 else 0,
                'quarter': (date.month - 1) // 3 + 1,
                'year': date.year
            })
    
    skills_progression_df = pd.DataFrame(all_skills_data)
    
    # Create forecasting models for each skill category
    skills_forecast_results = {}
    
    for skill_category in skill_categories:
        print(f"\n=== Forecasting Skills Progression for {skill_category} ===")
        
        # Filter data for specific skill category
        category_data = skills_progression_df[skills_progression_df['skill_category'] == skill_category].copy()
        
        # Skills progression forecasting pipeline
        skills_forecast = (
            ProphetPipe.from_dataframe(category_data)
            
            # Prepare Prophet data
            | prepare_prophet_data(
                date_column='date',
                value_column='avg_proficiency_score'
            )
            
            # Add external regressors (need to merge with original data)
            | add_regressors(
                regressor_columns=['training_investment', 'training_program_active'],
                regressor_data=category_data[['date', 'training_investment', 'training_program_active']].rename(columns={'date': 'ds'}),
                prior_scale=0.05
            )
            
            # Configure Prophet with capacity (proficiency is capped at 5.0)
            | configure_prophet(
                growth='linear',
                seasonality_mode='additive',
                yearly_seasonality=True,
                weekly_seasonality=False,  # Weekly data doesn't need weekly seasonality
                changepoint_prior_scale=0.1,
                seasonality_prior_scale=15.0,
                model_name=f'{skill_category.lower()}_skills_model'
            )
            
            # Add custom quarterly seasonality
            | add_custom_seasonality(
                name='quarterly',
                period=13,  # 13 weeks per quarter
                fourier_order=2,
                model_name=f'{skill_category.lower()}_skills_model'
            )
            
            # Fit model
            | fit_prophet(model_name=f'{skill_category.lower()}_skills_model')
            
            # Make 52-week (1 year) forecast
            | forecast_with_regressors(
                periods=52,
                regressor_future_values={
                    'training_investment': np.random.gamma(2, 5000, 52),  # Projected training investment
                    'training_program_active': [1 if (i % 26) < 4 else 0 for i in range(52)]  # Planned training programs
                },
                freq='W',
                model_name=f'{skill_category.lower()}_skills_model'
            )
            
            # Cross-validate
            | cross_validate_model(
                initial='364 days',  # 52 weeks
                period='91 days',    # 13 weeks
                horizon='56 days',   # 8 weeks
                model_name=f'{skill_category.lower()}_skills_model'
            )
            
            # Calculate metrics
            | calculate_forecast_metrics(f'{skill_category.lower()}_skills_model_forecast_with_regressors')
            
            # Plot results
            | plot_forecast(f'{skill_category.lower()}_skills_model_forecast_with_regressors', show_components=True)
            
            # Save model
            | save_prophet_model(f'{skill_category.lower()}_skills_model', f'{skill_category.lower()}_skills_forecast_model.joblib')
        )
        
        skills_forecast_results[skill_category] = skills_forecast
    
    # Comparative analysis
    print("\n=== Skills Progression Forecasting Analysis ===")
    
    # Current proficiency levels by skill category
    current_proficiency = skills_progression_df.groupby('skill_category')['avg_proficiency_score'].agg(['mean', 'std', 'min', 'max'])
    print("\nCurrent Skills Proficiency Statistics:")
    print(current_proficiency.round(3))
    
    # Growth trends
    growth_analysis = skills_progression_df.groupby(['skill_category', 'year'])['avg_proficiency_score'].mean().unstack('skill_category')
    print(f"\nYearly Proficiency Trends:")
    print(growth_analysis.round(3))
    
    # Training investment effectiveness
    investment_effectiveness = skills_progression_df.groupby('skill_category').agg({
        'training_investment': 'sum',
        'proficiency_improvement': 'sum'
    })
    investment_effectiveness['roi_ratio'] = investment_effectiveness['proficiency_improvement'] / (investment_effectiveness['training_investment'] / 1000)
    print(f"\nTraining Investment Effectiveness:")
    print(investment_effectiveness.round(3))
    
    return skills_forecast_results


# Example 6: Learning Engagement Trend Forecasting
def example_learning_engagement_forecasting():
    """
    Forecast learning engagement trends using Prophet
    """
    # Generate historical learning engagement data
    np.random.seed(111)
    
    # Create 3 years of daily engagement data
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2023, 12, 31)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    engagement_data = []
    
    for i, date in enumerate(date_range):
        # Base engagement level
        base_engagement = 3.2  # Out of 5
        
        # Long-term trend (slight improvement over time)
        trend = 0.0002 * i
        
        # Seasonal patterns
        yearly_season = 0.3 * np.sin(2 * np.pi * i / 365.25 + np.pi/4)  # Peak in fall
        monthly_season = 0.1 * np.sin(2 * np.pi * i / 30)
        
        # Weekly patterns (lower on weekends)
        day_of_week = date.weekday()
        weekly_effect = -0.4 if day_of_week >= 5 else 0.1
        
        # Holiday and vacation effects
        holiday_effect = 0
        if date.month == 12 and date.day >= 15:  # Holiday season
            holiday_effect = -0.6
        elif date.month == 1 and date.day <= 10:  # Post-holiday return
            holiday_effect = -0.3
        elif date.month in [7, 8]:  # Summer vacation periods
            holiday_effect = -0.2
        
        # Learning campaign effects
        campaign_effect = 0
        learning_campaigns = [
            (datetime(2021, 9, 1), datetime(2021, 9, 30)),  # Back-to-school campaign
            (datetime(2022, 1, 15), datetime(2022, 2, 15)),  # New Year learning goals
            (datetime(2022, 9, 1), datetime(2022, 9, 30)),  # Annual learning campaign
            (datetime(2023, 1, 15), datetime(2023, 2, 15)),  # New Year learning goals
            (datetime(2023, 9, 1), datetime(2023, 9, 30)),  # Annual learning campaign
        ]
        
        for start, end in learning_campaigns:
            if start <= date <= end:
                campaign_effect = 0.5
                break
        
        # External factors
        new_platform_launch = 0
        if datetime(2022, 3, 1) <= date <= datetime(2022, 5, 1):  # New learning platform
            new_platform_launch = 0.3
        elif datetime(2023, 6, 1) <= date <= datetime(2023, 8, 1):  # Platform upgrade
            new_platform_launch = 0.2
        
        # Remote work effects (higher engagement due to more online learning)
        remote_work_boost = 0.4 if date >= datetime(2021, 3, 1) else 0
        
        # Manager engagement initiatives
        manager_initiative = np.random.choice([0, 0.2], p=[0.95, 0.05])
        
        # System issues (occasional negative spikes)
        system_issues = np.random.choice([0, -0.8], p=[0.99, 0.01])
        
        # Calculate daily engagement
        daily_engagement = (base_engagement + trend + yearly_season + monthly_season + 
                          weekly_effect + holiday_effect + campaign_effect + 
                          new_platform_launch + remote_work_boost + manager_initiative + 
                          system_issues + np.random.normal(0, 0.15))
        
        daily_engagement = np.clip(daily_engagement, 1.0, 5.0)
        
        # Generate related metrics
        active_learners = max(50, int(np.random.poisson(200 + daily_engagement * 30)))
        course_enrollments = max(10, int(np.random.poisson(50 + daily_engagement * 15)))
        avg_session_duration = max(5, np.random.normal(20 + daily_engagement * 3, 5))
        
        engagement_data.append({
            'date': date,
            'avg_engagement_score': daily_engagement,
            'active_learners': active_learners,
            'course_enrollments': course_enrollments,
            'avg_session_duration_minutes': avg_session_duration,
            'learning_campaign_active': 1 if campaign_effect > 0 else 0,
            'platform_enhancement': 1 if new_platform_launch > 0 else 0,
            'manager_initiative': 1 if manager_initiative > 0 else 0,
            'system_issues': 1 if system_issues < 0 else 0,
            'is_weekend': 1 if day_of_week >= 5 else 0,
            'is_holiday_period': 1 if holiday_effect < -0.3 else 0,
            'month': date.month,
            'quarter': (date.month - 1) // 3 + 1
        })
    
    engagement_forecast_df = pd.DataFrame(engagement_data)
    
    # Create holidays dataframe for learning-specific events
    holidays_df = pd.DataFrame({
        'ds': pd.to_datetime([
            '2021-09-15', '2022-01-30', '2022-09-15', '2023-01-30', '2023-09-15',  # Learning campaigns
            '2021-12-25', '2022-12-25', '2023-12-25',  # Christmas
            '2021-07-04', '2022-07-04', '2023-07-04',  # July 4th
        ]),
        'holiday': [
            'learning_campaign', 'learning_campaign', 'learning_campaign', 'learning_campaign', 'learning_campaign',
            'christmas', 'christmas', 'christmas',
            'independence_day', 'independence_day', 'independence_day'
        ]
    })
    
    # Learning engagement forecasting pipeline
    engagement_forecast = (ProphetPipe.from_dataframe(engagement_forecast_df)
        # Prepare Prophet data
        | prepare_prophet_data(
            date_column='date',
            value_column='avg_engagement_score'
        )
        
        # Add external regressors (need to merge with original data)
        | add_regressors(
            regressor_columns=[
                'learning_campaign_active', 'platform_enhancement', 'manager_initiative',
                'system_issues', 'is_weekend', 'is_holiday_period'
            ],
            regressor_data=engagement_forecast_df[['date', 'learning_campaign_active', 'platform_enhancement', 'manager_initiative', 'system_issues', 'is_weekend', 'is_holiday_period']].rename(columns={'date': 'ds'}),
            prior_scale=0.1
        )
        
        # Add holidays
        | add_holidays(
            holiday_data=holidays_df,
            holiday_name='learning_holidays',
            prior_scale=5.0,
            lower_window=-2,
            upper_window=2
        )
        
        # Configure Prophet
        | configure_prophet(
            growth='linear',
            seasonality_mode='additive',
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.08,
            seasonality_prior_scale=12.0,
            model_name='engagement_forecast_model'
        )
        
        # Add custom seasonalities
        | add_custom_seasonality(
            name='monthly',
            period=30.5,
            fourier_order=4,
            model_name='engagement_forecast_model'
        )
        
        | add_custom_seasonality(
            name='quarterly',
            period=91.25,
            fourier_order=3,
            model_name='engagement_forecast_model'
        )
        
        # Fit model
        | fit_prophet(model_name='engagement_forecast_model')
        
        # Make 180-day forecast (6 months)
        | forecast_with_regressors(
            periods=180,
            regressor_future_values={
                'learning_campaign_active': [1 if (60 <= i <= 90) or (150 <= i <= 180) else 0 for i in range(180)],  # Future campaigns
                'platform_enhancement': [1 if 30 <= i <= 60 else 0 for i in range(180)],  # Planned upgrade
                'manager_initiative': np.random.choice([0, 1], 180, p=[0.95, 0.05]),  # Random initiatives
                'system_issues': np.random.choice([0, 1], 180, p=[0.99, 0.01]),  # Occasional issues
                'is_weekend': [1 if (i % 7) >= 5 else 0 for i in range(180)],  # Weekend pattern
                'is_holiday_period': [1 if (i % 365) in [355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9] else 0 for i in range(180)]  # Holiday periods
            },
            model_name='engagement_forecast_model'
        )
        
        # Cross-validate
        | cross_validate_model(
            initial='365 days',
            period='90 days',
            horizon='30 days',
            model_name='engagement_forecast_model'
        )
        
        # Calculate metrics
        | calculate_forecast_metrics('engagement_forecast_model_forecast_with_regressors')
        
        # Plot results
        | plot_forecast('engagement_forecast_model_forecast_with_regressors', show_components=True)
        
        # Save model
        | save_prophet_model('engagement_forecast_model', 'learning_engagement_forecast_model.joblib')
        
        # Print summary
        | print_prophet_summary()
    )
    
    # Business Analysis
    print("\n=== Learning Engagement Forecasting Analysis ===")
    
    # Current engagement statistics
    current_stats = {
        'avg_engagement': engagement_forecast_df['avg_engagement_score'].mean(),
        'std_engagement': engagement_forecast_df['avg_engagement_score'].std(),
        'min_engagement': engagement_forecast_df['avg_engagement_score'].min(),
        'max_engagement': engagement_forecast_df['avg_engagement_score'].max()
    }
    
    print(f"\nCurrent Engagement Statistics:")
    for key, value in current_stats.items():
        print(f"  {key}: {value:.3f}")
    
    # Seasonal analysis
    monthly_engagement = engagement_forecast_df.groupby('month')['avg_engagement_score'].mean()
    print(f"\nMonthly Engagement Patterns:")
    for month, avg_engagement in monthly_engagement.items():
        print(f"  Month {month}: {avg_engagement:.3f}")
    
    # Campaign effectiveness
    campaign_effectiveness = engagement_forecast_df.groupby('learning_campaign_active')['avg_engagement_score'].mean()
    print(f"\nLearning Campaign Effectiveness:")
    print(f"  Without Campaign: {campaign_effectiveness[0]:.3f}")
    print(f"  With Campaign: {campaign_effectiveness[1]:.3f}")
    print(f"  Campaign Lift: {((campaign_effectiveness[1] / campaign_effectiveness[0]) - 1) * 100:.1f}%")
    
    # Weekend vs weekday engagement
    weekend_analysis = engagement_forecast_df.groupby('is_weekend')['avg_engagement_score'].mean()
    print(f"\nWeekend vs Weekday Engagement:")
    print(f"  Weekdays: {weekend_analysis[0]:.3f}")
    print(f"  Weekends: {weekend_analysis[1]:.3f}")
    print(f"  Weekend Drop: {((weekend_analysis[1] / weekend_analysis[0]) - 1) * 100:.1f}%")
    
    return engagement_forecast


if __name__ == "__main__":
    print("Running HR Division & Employee Learning Analytics Examples...")
    
    print("\n" + "="*80)
    print("K-MEANS CLUSTERING EXAMPLES")
    print("="*80)
    
    print("\n" + "="*60)
    print("Example 1: Division-Based Employee Performance Clustering")
    print("="*60)
    division_employee_model = example_division_employee_clustering()
    
    print("\n" + "="*60)
    print("Example 2: Learning Behavior Clustering")
    print("="*60)
    learning_behavior_model = example_learning_behavior_clustering()
    
    print("\n" + "="*60)
    print("Example 3: Skills Development Clustering by Division")
    print("="*60)
    skills_development_model = example_skills_development_clustering()
    
    print("\n" + "="*80)
    print("PROPHET FORECASTING EXAMPLES")
    print("="*80)
    
    print("\n" + "="*60)
    print("Example 4: Training Completion Forecasting by Division")
    print("="*60)
    training_forecast_models = example_training_completion_forecasting()
    
    print("\n" + "="*60)
    print("Example 5: Skills Development Progression Forecasting")
    print("="*60)
    skills_forecast_models = example_skills_progression_forecasting()
    
    print("\n" + "="*60)
    print("Example 6: Learning Engagement Trend Forecasting")
    print("="*60)
    engagement_forecast_model = example_learning_engagement_forecasting()
    
    print("\n" + "="*80)
    print("HR LEARNING ANALYTICS SUMMARY")
    print("="*80)
    
    print("\nK-means Clustering Models:")
    clustering_models = [
        ('Division Employee Performance', division_employee_model),
        ('Learning Behavior Patterns', learning_behavior_model),
        ('Skills Development by Division', skills_development_model)
    ]
    
    for name, model in clustering_models:
        if hasattr(model, 'models') and model.models:
            model_name = list(model.models.keys())[0]
            n_clusters = model.models[model_name]['config']['n_clusters']
            n_samples = len(model.data) if hasattr(model, 'data') else 0
            print(f"  {name}: {n_clusters} clusters, {n_samples:,} samples")
            
            if model_name in model.evaluation_metrics:
                metrics = model.evaluation_metrics[model_name]
                if 'silhouette_score' in metrics:
                    print(f"    Silhouette Score: {metrics['silhouette_score']:.3f}")
    
    print(f"\nProphet Forecasting Models:")
    print(f"  Training Completion: {len(training_forecast_models)} division models")
    print(f"  Skills Progression: {len(skills_forecast_models)} skill category models")
    print(f"  Learning Engagement: 1 organization-wide model")
    
    print(f"\nBusiness Applications:")
    print(f"  • Identify high-performing vs at-risk employee segments")
    print(f"  • Optimize training programs by division and learning style")
    print(f"  • Forecast training completion rates for resource planning")
    print(f"  • Predict skills development trends for workforce planning")
    print(f"  • Anticipate learning engagement patterns for campaign timing")
    print(f"  • Enable data-driven L&D strategy and budget allocation")
    
    print(f"\nAll HR Division & Employee Learning Analytics examples completed successfully!")