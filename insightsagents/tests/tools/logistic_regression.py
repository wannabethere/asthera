# HR Employee Learning Churn Prediction Pipeline Examples

from app.tools.mltools.models.logistic_regression import (
    LogisticRegressionPipe,
    prepare_classification_data,
    engineer_features,
    select_features,
    configure_logistic_regression,
    configure_ridge_classifier,
    split_train_test,
    fit_model,
    predict,
    evaluate_model,
    calculate_feature_importance,
    cross_validate_model,
    tune_hyperparameters,
    plot_confusion_matrix,
    plot_feature_importance,
    plot_roc_curve,
    save_model,
    load_model,
    print_model_summary
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# Example 1: Employee Churn Prediction
def example_employee_churn_prediction():
    """
    Predict employee churn based on training completion, skills development, and engagement metrics
    """
    # Generate realistic employee data based on CSOD and Workday schemas
    np.random.seed(42)
    n_employees = 5000
    
    # Create different employee archetypes
    employee_segments = ['High Performer', 'Steady Contributor', 'At Risk', 'New Hire', 'Struggling']
    true_segments = np.random.choice(employee_segments, n_employees, p=[0.15, 0.35, 0.20, 0.20, 0.10])
    
    employee_data = []
    for i, segment in enumerate(true_segments):
        # Base demographics
        tenure_months = np.random.exponential(24) if segment != 'New Hire' else np.random.uniform(1, 12)
        age = np.random.normal(35, 8) if segment != 'New Hire' else np.random.normal(28, 5)
        
        # Division and role
        division = np.random.choice(['Administration', 'Acme Products', 'Private Operations'])
        job_level = np.random.choice(['Individual Contributor', 'Senior', 'Lead', 'Manager'], 
                                   p=[0.4, 0.3, 0.2, 0.1])
        
        # Training metrics (based on segment)
        if segment == 'High Performer':
            training_completion_rate = np.random.normal(0.95, 0.05)
            avg_completion_days = np.random.normal(8, 2)
            late_completion_rate = np.random.normal(0.05, 0.02)
            skills_developed = np.random.poisson(12)
            avg_proficiency_improvement = np.random.normal(2.5, 0.5)
            certifications_earned = np.random.poisson(3)
            churn_probability = 0.05
        elif segment == 'Steady Contributor':
            training_completion_rate = np.random.normal(0.85, 0.10)
            avg_completion_days = np.random.normal(15, 4)
            late_completion_rate = np.random.normal(0.15, 0.05)
            skills_developed = np.random.poisson(8)
            avg_proficiency_improvement = np.random.normal(1.8, 0.4)
            certifications_earned = np.random.poisson(2)
            churn_probability = 0.10
        elif segment == 'At Risk':
            training_completion_rate = np.random.normal(0.60, 0.15)
            avg_completion_days = np.random.normal(25, 8)
            late_completion_rate = np.random.normal(0.35, 0.10)
            skills_developed = np.random.poisson(4)
            avg_proficiency_improvement = np.random.normal(1.0, 0.3)
            certifications_earned = np.random.poisson(1)
            churn_probability = 0.45
        elif segment == 'New Hire':
            training_completion_rate = np.random.normal(0.75, 0.20)
            avg_completion_days = np.random.normal(12, 5)
            late_completion_rate = np.random.normal(0.20, 0.08)
            skills_developed = np.random.poisson(6)
            avg_proficiency_improvement = np.random.normal(2.0, 0.6)
            certifications_earned = np.random.poisson(1)
            churn_probability = 0.25
        else:  # Struggling
            training_completion_rate = np.random.normal(0.40, 0.20)
            avg_completion_days = np.random.normal(35, 10)
            late_completion_rate = np.random.normal(0.50, 0.15)
            skills_developed = np.random.poisson(2)
            avg_proficiency_improvement = np.random.normal(0.5, 0.2)
            certifications_earned = np.random.poisson(0.5)
            churn_probability = 0.65
        
        # Engagement and performance metrics
        manager_interactions = np.random.poisson(8) if segment == 'High Performer' else np.random.poisson(3)
        performance_rating = np.random.normal(4.2, 0.3) if segment == 'High Performer' else np.random.normal(3.0, 0.5)
        career_development_participation = np.random.choice([0, 1], p=[0.2, 0.8] if segment == 'High Performer' else [0.7, 0.3])
        
        # Additional factors
        salary_percentile = np.random.uniform(0.7, 0.95) if segment == 'High Performer' else np.random.uniform(0.3, 0.7)
        remote_work_eligible = np.random.choice([0, 1], p=[0.3, 0.7])
        promotion_in_last_year = np.random.choice([0, 1], p=[0.8, 0.2] if segment == 'High Performer' else [0.95, 0.05])
        
        # Generate actual churn based on probability
        churned = np.random.binomial(1, churn_probability)
        
        employee_data.append({
            'employee_id': f'EMP_{i:04d}',
            'age': max(22, min(65, age)),
            'tenure_months': max(1, tenure_months),
            'division': division,
            'job_level': job_level,
            'training_completion_rate': np.clip(training_completion_rate, 0, 1),
            'avg_completion_days': max(1, avg_completion_days),
            'late_completion_rate': np.clip(late_completion_rate, 0, 1),
            'total_training_assignments': np.random.poisson(20),
            'skills_developed': max(0, skills_developed),
            'avg_proficiency_improvement': max(0, avg_proficiency_improvement),
            'certifications_earned': max(0, int(certifications_earned)),
            'manager_interactions_per_month': max(0, manager_interactions),
            'performance_rating': np.clip(performance_rating, 1, 5),
            'career_development_participation': career_development_participation,
            'salary_percentile': np.clip(salary_percentile, 0.1, 0.99),
            'remote_work_eligible': remote_work_eligible,
            'promotion_in_last_year': promotion_in_last_year,
            'overdue_training_count': np.random.poisson(2) if segment in ['At Risk', 'Struggling'] else np.random.poisson(0.5),
            'succession_plan_participant': np.random.choice([0, 1], p=[0.3, 0.7] if segment == 'High Performer' else [0.9, 0.1]),
            'true_segment': segment,
            'churned': churned
        })
    
    employee_df = pd.DataFrame(employee_data)
    
    # Employee churn prediction pipeline
    churn_model = (
        LogisticRegressionPipe.from_dataframe(employee_df)
        
        # Prepare data for classification
        | prepare_classification_data(
            feature_columns=[
                'age', 'tenure_months', 'training_completion_rate', 'avg_completion_days',
                'late_completion_rate', 'total_training_assignments', 'skills_developed',
                'avg_proficiency_improvement', 'certifications_earned', 'manager_interactions_per_month',
                'performance_rating', 'career_development_participation', 'salary_percentile',
                'remote_work_eligible', 'promotion_in_last_year', 'overdue_training_count',
                'succession_plan_participant'
            ],
            target_column='churned',
            scaling_method='standard',
            handle_missing='mean',
            remove_outliers=True,
            encode_target=False  # Already binary
        )
        
        # Engineer features for churn prediction
        | engineer_features(
            interaction_features=True,
            ratio_features=[
                ('skills_developed', 'tenure_months'),
                ('certifications_earned', 'total_training_assignments'),
                ('avg_proficiency_improvement', 'training_completion_rate'),
                ('manager_interactions_per_month', 'tenure_months')
            ],
            polynomial_features=['performance_rating', 'salary_percentile', 'training_completion_rate']
        )
        
        # Select most important features
        | select_features(
            method='k_best',
            k=15,
            score_func='f_classif',
            selector_name='churn_features'
        )
        
        # Split data for training and testing
        | split_train_test(
            test_size=0.2,
            stratify=True,
            split_name='churn_split'
        )
        
        # Configure logistic regression for churn prediction
        | configure_logistic_regression(
            penalty='l2',
            C=1.0,
            solver='lbfgs',
            class_weight='balanced',  # Handle class imbalance
            model_name='churn_model'
        )
        
        # Fit the model
        | fit_model('churn_model', 'churn_split')
        
        # Make predictions
        | predict('churn_model', 'churn_split', include_probabilities=True)
        
        # Evaluate model performance
        | evaluate_model(
            'churn_model',
            metrics=['accuracy', 'precision', 'recall', 'f1', 'auc', 'confusion_matrix']
        )
        
        # Calculate feature importance
        | calculate_feature_importance('churn_model', method='coefficients')
        
        # Cross-validation
        | cross_validate_model('churn_model', cv_folds=5, scoring='roc_auc')
        
        # Visualizations
        | plot_confusion_matrix('churn_model')
        | plot_feature_importance('churn_model', top_k=15)
        | plot_roc_curve('churn_model')
        
        # Print comprehensive summary
        | print_model_summary('churn_model')
        
        # Save model
        | save_model('churn_model', 'employee_churn_model.joblib')
    )
    
    # Business insights
    print("\n=== Employee Churn Prediction Results ===")
    metrics = churn_model.evaluation_metrics.get('churn_model', {})
    if metrics:
        print(f"Model Accuracy: {metrics.get('accuracy', 0):.3f}")
        print(f"Precision: {metrics.get('precision', 0):.3f}")
        print(f"Recall: {metrics.get('recall', 0):.3f}")
        print(f"AUC Score: {metrics.get('auc_score', 0):.3f}")
    
    # Validate against true segments
    if hasattr(churn_model, 'data') and 'churn_model_prediction' in churn_model.data.columns:
        validation_df = churn_model.data[['true_segment', 'churned', 'churn_model_prediction']].copy()
        print("\nChurn Rate by True Employee Segment:")
        segment_churn = validation_df.groupby('true_segment')['churned'].agg(['count', 'sum', 'mean'])
        segment_churn.columns = ['Total', 'Churned', 'Churn_Rate']
        print(segment_churn)
    
    return churn_model


# Example 2: Training Program Dropout Prediction
def example_training_dropout_prediction():
    """
    Predict which employees are likely to drop out of training programs
    """
    # Generate training enrollment data
    np.random.seed(123)
    n_enrollments = 8000
    
    # Training program types
    program_types = ['Technical Skills', 'Leadership Development', 'Compliance', 'Soft Skills', 'Digital Transformation']
    program_durations = {'Technical Skills': 40, 'Leadership Development': 60, 'Compliance': 20, 
                        'Soft Skills': 30, 'Digital Transformation': 50}
    
    enrollment_data = []
    for i in range(n_enrollments):
        # Program characteristics
        program_type = np.random.choice(program_types)
        program_duration = program_durations[program_type] + np.random.normal(0, 5)
        program_difficulty = np.random.uniform(1, 5)
        
        # Employee characteristics
        age = np.random.normal(35, 10)
        tenure = np.random.exponential(30)
        prior_completions = np.random.poisson(5)
        job_level = np.random.choice(['Individual Contributor', 'Senior', 'Lead', 'Manager'], 
                                   p=[0.5, 0.3, 0.15, 0.05])
        
        # Engagement factors
        voluntary_enrollment = np.random.choice([0, 1], p=[0.3, 0.7])
        manager_support_score = np.random.normal(4, 1)
        workload_hours_per_week = np.random.normal(45, 8)
        
        # Learning preferences and history
        preferred_learning_style = np.random.choice(['Visual', 'Auditory', 'Kinesthetic', 'Reading'])
        previous_dropout_count = np.random.poisson(1)
        avg_time_to_complete = np.random.gamma(2, 10)
        
        # Schedule and logistics
        training_format = np.random.choice(['Online', 'In-Person', 'Blended'], p=[0.6, 0.2, 0.2])
        time_of_day = np.random.choice(['Morning', 'Afternoon', 'Evening'], p=[0.4, 0.5, 0.1])
        conflicts_with_work = np.random.choice([0, 1], p=[0.7, 0.3])
        
        # Calculate dropout probability based on factors
        dropout_prob = 0.1  # Base probability
        
        # Adjust based on engagement
        if not voluntary_enrollment:
            dropout_prob += 0.2
        if manager_support_score < 3:
            dropout_prob += 0.15
        if workload_hours_per_week > 50:
            dropout_prob += 0.1
        
        # Adjust based on history
        dropout_prob += previous_dropout_count * 0.1
        if prior_completions > 8:
            dropout_prob -= 0.1
            
        # Adjust based on program characteristics
        if program_difficulty > 4:
            dropout_prob += 0.15
        if program_duration > 45:
            dropout_prob += 0.1
            
        # Adjust based on logistics
        if conflicts_with_work:
            dropout_prob += 0.2
        if training_format == 'Online' and preferred_learning_style in ['Kinesthetic']:
            dropout_prob += 0.1
            
        # Cap probability
        dropout_prob = min(0.8, max(0.02, dropout_prob))
        
        # Generate actual dropout
        dropped_out = np.random.binomial(1, dropout_prob)
        
        enrollment_data.append({
            'enrollment_id': f'ENROLL_{i:04d}',
            'program_type': program_type,
            'program_duration_hours': max(10, program_duration),
            'program_difficulty_score': program_difficulty,
            'employee_age': max(22, min(65, age)),
            'tenure_months': max(1, tenure),
            'prior_training_completions': max(0, prior_completions),
            'job_level': job_level,
            'voluntary_enrollment': voluntary_enrollment,
            'manager_support_score': np.clip(manager_support_score, 1, 5),
            'workload_hours_per_week': max(20, min(70, workload_hours_per_week)),
            'preferred_learning_style': preferred_learning_style,
            'previous_dropout_count': max(0, previous_dropout_count),
            'avg_completion_time_days': max(1, avg_time_to_complete),
            'training_format': training_format,
            'time_of_day': time_of_day,
            'conflicts_with_work_schedule': conflicts_with_work,
            'division': np.random.choice(['Administration', 'Acme Products', 'Private Operations']),
            'training_budget_allocated': np.random.gamma(2, 500),
            'peer_completion_rate': np.random.uniform(0.4, 0.9),
            'training_relevance_score': np.random.uniform(2, 5),
            'dropped_out': dropped_out
        })
    
    enrollment_df = pd.DataFrame(enrollment_data)
    
    # Training dropout prediction pipeline
    dropout_model = (
        LogisticRegressionPipe.from_dataframe(enrollment_df)
        
        # Prepare data
        | prepare_classification_data(
            feature_columns=[
                'program_duration_hours', 'program_difficulty_score', 'employee_age',
                'tenure_months', 'prior_training_completions', 'voluntary_enrollment',
                'manager_support_score', 'workload_hours_per_week', 'previous_dropout_count',
                'avg_completion_time_days', 'conflicts_with_work_schedule', 'training_budget_allocated',
                'peer_completion_rate', 'training_relevance_score'
            ],
            target_column='dropped_out',
            scaling_method='robust',
            handle_categorical='encode',
            remove_outliers=True
        )
        
        # Add categorical features
        | prepare_classification_data(
            feature_columns=[
                'program_type', 'job_level', 'preferred_learning_style', 
                'training_format', 'time_of_day', 'division'
            ],
            target_column='dropped_out',
            handle_categorical='dummy'
        )
        
        # Engineer features
        | engineer_features(
            interaction_features=True,
            ratio_features=[
                ('program_duration_hours', 'workload_hours_per_week'),
                ('prior_training_completions', 'tenure_months'),
                ('manager_support_score', 'training_relevance_score'),
                ('training_budget_allocated', 'program_duration_hours')
            ],
            polynomial_features=['manager_support_score', 'training_relevance_score'],
            statistical_features=True
        )
        
        # Feature selection
        | select_features(
            method='rfe',
            k=20,
            selector_name='dropout_features'
        )
        
        # Split data
        | split_train_test(
            test_size=0.25,
            stratify=True,
            split_name='dropout_split'
        )
        
        # Configure model with regularization
        | configure_logistic_regression(
            penalty='l1',
            C=0.5,
            solver='liblinear',
            class_weight='balanced',
            model_name='dropout_model'
        )
        
        # Fit and evaluate
        | fit_model('dropout_model', 'dropout_split')
        | predict('dropout_model', 'dropout_split', include_probabilities=True)
        | evaluate_model('dropout_model')
        | calculate_feature_importance('dropout_model', method='coefficients')
        
        # Cross-validation with different metrics
        | cross_validate_model('dropout_model', cv_folds=5, scoring='precision')
        
        # Hyperparameter tuning
        | tune_hyperparameters(
            'dropout_model',
            param_grid={
                'C': [0.1, 0.5, 1.0, 2.0],
                'penalty': ['l1', 'l2'],
                'solver': ['liblinear', 'saga']
            },
            search_method='grid',
            cv_folds=3,
            scoring='f1',
            tuning_name='dropout_tuning'
        )
        
        # Evaluate tuned model
        | predict('dropout_model_tuned', 'dropout_split', prediction_name='tuned_predictions', include_probabilities=True)
        | evaluate_model('tuned_predictions')
        
        # Visualizations
        | plot_confusion_matrix('tuned_predictions')
        | plot_feature_importance('dropout_model', top_k=20)
        | plot_roc_curve('tuned_predictions')
        
        # Print summary
        | print_model_summary('dropout_model_tuned')
    )
    
    # Business insights
    print("\n=== Training Dropout Prediction Results ===")
    
    # Compare original and tuned models
    original_metrics = dropout_model.evaluation_metrics.get('dropout_model', {})
    tuned_metrics = dropout_model.evaluation_metrics.get('tuned_predictions', {})
    
    print("Model Comparison:")
    print(f"Original Model - AUC: {original_metrics.get('auc_score', 0):.3f}, F1: {original_metrics.get('f1_score', 0):.3f}")
    print(f"Tuned Model - AUC: {tuned_metrics.get('auc_score', 0):.3f}, F1: {tuned_metrics.get('f1_score', 0):.3f}")
    
    # Program type analysis
    program_dropout_rates = enrollment_df.groupby('program_type')['dropped_out'].agg(['count', 'sum', 'mean'])
    program_dropout_rates.columns = ['Enrollments', 'Dropouts', 'Dropout_Rate']
    print(f"\nDropout Rates by Program Type:")
    print(program_dropout_rates.sort_values('Dropout_Rate', ascending=False))
    
    return dropout_model


# Example 3: Skills Gap Risk Assessment
def example_skills_gap_risk_prediction():
    """
    Predict employees at risk of having critical skills gaps
    """
    # Generate skills assessment data based on Workday schema
    np.random.seed(456)
    n_assessments = 6000
    
    # Skill categories and criticalities
    skill_categories = ['Technical', 'Leadership', 'Compliance', 'Soft Skills', 'Digital']
    skill_criticalities = ['Critical', 'Important', 'Beneficial']
    competency_frameworks = ['Engineering', 'Management', 'Sales', 'Operations', 'Support']
    
    skills_data = []
    for i in range(n_assessments):
        # Employee characteristics
        employee_id = f'EMP_{np.random.randint(1000, 5000):04d}'
        division = np.random.choice(['Administration', 'Acme Products', 'Private Operations'])
        job_level = np.random.choice(['Individual Contributor', 'Senior', 'Lead', 'Manager'], 
                                   p=[0.4, 0.3, 0.2, 0.1])
        tenure_months = np.random.exponential(36)
        
        # Skill characteristics
        skill_category = np.random.choice(skill_categories)
        skill_criticality = np.random.choice(skill_criticalities, p=[0.3, 0.5, 0.2])
        competency_framework = np.random.choice(competency_frameworks)
        
        # Proficiency levels (1-5 scale)
        target_proficiency = np.random.choice([3, 4, 5], p=[0.5, 0.3, 0.2])
        
        # Factors affecting current proficiency
        training_completed = np.random.choice([0, 1], p=[0.3, 0.7])
        training_recency_months = np.random.exponential(12) if training_completed else 999
        
        # Calculate current proficiency based on factors
        base_proficiency = np.random.uniform(1, 3)
        
        if training_completed:
            base_proficiency += 1.5
        if training_recency_months < 6:
            base_proficiency += 0.5
        elif training_recency_months > 24:
            base_proficiency -= 0.3
            
        if job_level in ['Lead', 'Manager'] and skill_category == 'Leadership':
            base_proficiency += 0.8
        if tenure_months > 60:
            base_proficiency += 0.5
            
        current_proficiency = min(5, max(1, base_proficiency + np.random.normal(0, 0.5)))
        
        # Calculate risk factors
        proficiency_gap = max(0, target_proficiency - current_proficiency)
        training_investment = np.random.gamma(2, 300) if training_completed else 0
        
        # Performance and engagement metrics
        performance_rating = np.random.normal(3.5, 0.8)
        career_development_active = np.random.choice([0, 1], p=[0.4, 0.6])
        manager_support_score = np.random.uniform(2, 5)
        
        # Learning factors
        learning_agility_score = np.random.uniform(2, 5)
        time_since_last_assessment = np.random.exponential(18)
        
        # Generate skills gap risk
        # High risk if gap exists and other negative factors
        risk_probability = 0.1  # Base risk
        
        if proficiency_gap >= 2:
            risk_probability += 0.4
        elif proficiency_gap >= 1:
            risk_probability += 0.2
            
        if skill_criticality == 'Critical':
            risk_probability += 0.2
        elif skill_criticality == 'Important':
            risk_probability += 0.1
            
        if not training_completed:
            risk_probability += 0.3
        if training_recency_months > 24:
            risk_probability += 0.2
            
        if performance_rating < 3:
            risk_probability += 0.2
        if not career_development_active:
            risk_probability += 0.1
        if manager_support_score < 3:
            risk_probability += 0.15
        if learning_agility_score < 3:
            risk_probability += 0.15
            
        # Cap probability
        risk_probability = min(0.9, max(0.05, risk_probability))
        
        skills_gap_risk = np.random.binomial(1, risk_probability)
        
        skills_data.append({
            'assessment_id': f'ASSESS_{i:04d}',
            'employee_id': employee_id,
            'division': division,
            'job_level': job_level,
            'tenure_months': max(1, tenure_months),
            'skill_category': skill_category,
            'skill_criticality': skill_criticality,
            'competency_framework': competency_framework,
            'current_proficiency': round(current_proficiency, 1),
            'target_proficiency': target_proficiency,
            'proficiency_gap': max(0, round(proficiency_gap, 1)),
            'training_completed': training_completed,
            'training_recency_months': min(999, training_recency_months),
            'training_investment': training_investment,
            'performance_rating': np.clip(performance_rating, 1, 5),
            'career_development_active': career_development_active,
            'manager_support_score': manager_support_score,
            'learning_agility_score': learning_agility_score,
            'time_since_last_assessment_months': time_since_last_assessment,
            'certification_earned': np.random.choice([0, 1], p=[0.7, 0.3]),
            'peer_group_avg_proficiency': np.random.uniform(2, 4),
            'skills_gap_risk': skills_gap_risk
        })
    
    skills_df = pd.DataFrame(skills_data)
    
    # Skills gap risk prediction pipeline
    skills_risk_model = (
        LogisticRegressionPipe.from_dataframe(skills_df)
        
        # Prepare data
        | prepare_classification_data(
            feature_columns=[
                'tenure_months', 'current_proficiency', 'target_proficiency', 'proficiency_gap',
                'training_completed', 'training_recency_months', 'training_investment',
                'performance_rating', 'career_development_active', 'manager_support_score',
                'learning_agility_score', 'time_since_last_assessment_months', 'certification_earned',
                'peer_group_avg_proficiency'
            ],
            target_column='skills_gap_risk',
            scaling_method='standard',
            remove_outliers=True
        )
        
        # Handle categorical features
        | prepare_classification_data(
            feature_columns=['division', 'job_level', 'skill_category', 'skill_criticality', 'competency_framework'],
            target_column='skills_gap_risk',
            handle_categorical='dummy'
        )
        
        # Advanced feature engineering
        | engineer_features(
            interaction_features=True,
            ratio_features=[
                ('current_proficiency', 'target_proficiency'),
                ('training_investment', 'proficiency_gap'),
                ('performance_rating', 'manager_support_score'),
                ('learning_agility_score', 'time_since_last_assessment_months')
            ],
            polynomial_features=['current_proficiency', 'manager_support_score', 'learning_agility_score'],
            binning_features={
                'tenure_months': 5,
                'training_recency_months': 4,
                'time_since_last_assessment_months': 4
            }
        )
        
        # Feature selection with multiple methods
        | select_features(
            method='from_model',
            k=25,
            selector_name='skills_risk_features'
        )
        
        # Split data
        | split_train_test(
            test_size=0.2,
            stratify=True,
            split_name='skills_risk_split'
        )
        
        # Configure multiple models for comparison
        | configure_logistic_regression(
            penalty='l2',
            C=1.0,
            solver='lbfgs',
            class_weight='balanced',
            model_name='logistic_model'
        )
        
        | configure_ridge_classifier(
            alpha=1.0,
            class_weight='balanced',
            model_name='ridge_model'
        )
        
        # Fit both models
        | fit_model('logistic_model', 'skills_risk_split')
        | fit_model('ridge_model', 'skills_risk_split')
        
        # Make predictions
        | predict('logistic_model', 'skills_risk_split', prediction_name='logistic_predictions', include_probabilities=True)
        | predict('ridge_model', 'skills_risk_split', prediction_name='ridge_predictions', include_probabilities=False)
        
        # Evaluate both models
        | evaluate_model('logistic_predictions')
        | evaluate_model('ridge_predictions')
        
        # Feature importance
        | calculate_feature_importance('logistic_model', method='coefficients', importance_name='logistic_importance')
        | calculate_feature_importance('logistic_model', method='permutation', importance_name='permutation_importance')
        
        # Cross-validation for both models
        | cross_validate_model('logistic_model', cv_folds=5, scoring='roc_auc', cv_name='logistic_cv')
        | cross_validate_model('ridge_model', cv_folds=5, scoring='roc_auc', cv_name='ridge_cv')
        
        # Hyperparameter tuning for the better performing model
        | tune_hyperparameters(
            'logistic_model',
            param_grid={
                'C': [0.1, 0.5, 1.0, 2.0, 5.0],
                'penalty': ['l1', 'l2'],
                'solver': ['liblinear', 'saga']
            },
            search_method='random',
            n_iter=20,
            cv_folds=3,
            scoring='roc_auc',
            tuning_name='skills_risk_tuning'
        )
        
        # Final predictions with best model
        | predict('logistic_model_tuned', 'skills_risk_split', prediction_name='final_predictions', include_probabilities=True)
        | evaluate_model('final_predictions')
        
        # Visualizations
        | plot_confusion_matrix('final_predictions')
        | plot_feature_importance('logistic_importance', top_k=20)
        | plot_roc_curve('final_predictions')
        
        # Print comprehensive summary
        | print_model_summary('logistic_model_tuned')
    )
    
    # Business insights
    print("\n=== Skills Gap Risk Prediction Results ===")
    
    # Model comparison
    logistic_metrics = skills_risk_model.evaluation_metrics.get('logistic_predictions', {})
    ridge_metrics = skills_risk_model.evaluation_metrics.get('ridge_predictions', {})
    final_metrics = skills_risk_model.evaluation_metrics.get('final_predictions', {})
    
    print("Model Performance Comparison:")
    print(f"Logistic Regression - AUC: {logistic_metrics.get('auc_score', 0):.3f}")
    print(f"Ridge Classifier - Accuracy: {ridge_metrics.get('accuracy', 0):.3f}")
    print(f"Tuned Model - AUC: {final_metrics.get('auc_score', 0):.3f}, F1: {final_metrics.get('f1_score', 0):.3f}")
    
    # Skills category risk analysis
    category_risk = skills_df.groupby('skill_category')['skills_gap_risk'].agg(['count', 'sum', 'mean'])
    category_risk.columns = ['Total_Assessments', 'At_Risk', 'Risk_Rate']
    print(f"\nSkills Gap Risk by Category:")
    print(category_risk.sort_values('Risk_Rate', ascending=False))
    
    # Criticality analysis
    criticality_risk = skills_df.groupby('skill_criticality')['skills_gap_risk'].agg(['count', 'sum', 'mean'])
    criticality_risk.columns = ['Total_Assessments', 'At_Risk', 'Risk_Rate']
    print(f"\nSkills Gap Risk by Criticality:")
    print(criticality_risk.sort_values('Risk_Rate', ascending=False))
    
    return skills_risk_model


# Example 4: Learning Engagement Prediction
def example_learning_engagement_prediction():
    """
    Predict employee learning engagement levels for personalized recommendations
    """
    # Generate learning engagement data
    np.random.seed(789)
    n_employees = 4500
    
    engagement_data = []
    for i in range(n_employees):
        # Employee demographics
        age = np.random.normal(35, 12)
        tenure = np.random.exponential(30)
        job_level = np.random.choice(['Individual Contributor', 'Senior', 'Lead', 'Manager'], 
                                   p=[0.45, 0.30, 0.15, 0.10])
        division = np.random.choice(['Administration', 'Acme Products', 'Private Operations'])
        
        # Learning history
        courses_completed_last_year = np.random.poisson(8)
        avg_course_rating = np.random.uniform(2, 5)
        learning_hours_last_quarter = np.random.gamma(2, 15)
        
        # Engagement indicators
        voluntary_learning_participation = np.random.choice([0, 1], p=[0.4, 0.6])
        peer_learning_collaboration = np.random.poisson(3)
        knowledge_sharing_activities = np.random.poisson(2)
        
        # Performance and career factors
        performance_rating = np.random.normal(3.5, 0.7)
        career_growth_aspirations = np.random.uniform(1, 5)
        promotion_in_last_2_years = np.random.choice([0, 1], p=[0.8, 0.2])
        
        # Work environment factors
        manager_learning_support = np.random.uniform(2, 5)
        team_learning_culture = np.random.uniform(2, 5)
        workload_stress_level = np.random.uniform(1, 5)
        
        # Technology and accessibility
        digital_literacy_score = np.random.uniform(2, 5)
        learning_platform_usage_hours = np.random.gamma(2, 10)
        mobile_learning_preference = np.random.choice([0, 1], p=[0.3, 0.7])
        
        # Personal factors
        work_life_balance_score = np.random.uniform(2, 5)
        intrinsic_motivation_score = np.random.uniform(2, 5)
        
        # Calculate engagement score (continuous target for classification)
        engagement_score = 2.0  # Base score
        
        # Add factors
        engagement_score += courses_completed_last_year * 0.1
        engagement_score += avg_course_rating * 0.3
        engagement_score += learning_hours_last_quarter * 0.02
        engagement_score += voluntary_learning_participation * 0.5
        engagement_score += peer_learning_collaboration * 0.1
        engagement_score += knowledge_sharing_activities * 0.15
        engagement_score += (performance_rating - 2.5) * 0.3
        engagement_score += career_growth_aspirations * 0.2
        engagement_score += promotion_in_last_2_years * 0.3
        engagement_score += (manager_learning_support - 2.5) * 0.2
        engagement_score += (team_learning_culture - 2.5) * 0.2
        engagement_score -= (workload_stress_level - 2.5) * 0.15
        engagement_score += (digital_literacy_score - 2.5) * 0.1
        engagement_score += learning_platform_usage_hours * 0.01
        engagement_score += mobile_learning_preference * 0.2
        engagement_score += (work_life_balance_score - 2.5) * 0.15
        engagement_score += (intrinsic_motivation_score - 2.5) * 0.25
        
        # Add noise and clip
        engagement_score += np.random.normal(0, 0.3)
        engagement_score = np.clip(engagement_score, 1, 5)
        
        # Convert to categorical for classification (Low, Medium, High)
        if engagement_score < 2.5:
            engagement_level = 0  # Low
        elif engagement_score < 3.5:
            engagement_level = 1  # Medium
        else:
            engagement_level = 2  # High
            
        engagement_data.append({
            'employee_id': f'EMP_{i:04d}',
            'age': max(22, min(65, age)),
            'tenure_months': max(1, tenure),
            'job_level': job_level,
            'division': division,
            'courses_completed_last_year': max(0, courses_completed_last_year),
            'avg_course_rating': avg_course_rating,
            'learning_hours_last_quarter': max(0, learning_hours_last_quarter),
            'voluntary_learning_participation': voluntary_learning_participation,
            'peer_learning_collaboration': max(0, peer_learning_collaboration),
            'knowledge_sharing_activities': max(0, knowledge_sharing_activities),
            'performance_rating': np.clip(performance_rating, 1, 5),
            'career_growth_aspirations': career_growth_aspirations,
            'promotion_in_last_2_years': promotion_in_last_2_years,
            'manager_learning_support': manager_learning_support,
            'team_learning_culture': team_learning_culture,
            'workload_stress_level': workload_stress_level,
            'digital_literacy_score': digital_literacy_score,
            'learning_platform_usage_hours': max(0, learning_platform_usage_hours),
            'mobile_learning_preference': mobile_learning_preference,
            'work_life_balance_score': work_life_balance_score,
            'intrinsic_motivation_score': intrinsic_motivation_score,
            'engagement_score': engagement_score,
            'engagement_level': engagement_level
        })
    
    engagement_df = pd.DataFrame(engagement_data)
    
    # Learning engagement prediction pipeline
    engagement_model = (
        LogisticRegressionPipe.from_dataframe(engagement_df)
        
        # Prepare data for multi-class classification
        | prepare_classification_data(
            feature_columns=[
                'age', 'tenure_months', 'courses_completed_last_year', 'avg_course_rating',
                'learning_hours_last_quarter', 'voluntary_learning_participation',
                'peer_learning_collaboration', 'knowledge_sharing_activities', 'performance_rating',
                'career_growth_aspirations', 'promotion_in_last_2_years', 'manager_learning_support',
                'team_learning_culture', 'workload_stress_level', 'digital_literacy_score',
                'learning_platform_usage_hours', 'mobile_learning_preference',
                'work_life_balance_score', 'intrinsic_motivation_score'
            ],
            target_column='engagement_level',
            scaling_method='standard',
            handle_categorical='encode',
            remove_outliers=True,
            encode_target=False  # Keep original encoding
        )
        
        # Feature engineering for engagement prediction
        | engineer_features(
            interaction_features=True,
            ratio_features=[
                ('learning_hours_last_quarter', 'courses_completed_last_year'),
                ('career_growth_aspirations', 'performance_rating'),
                ('manager_learning_support', 'team_learning_culture'),
                ('digital_literacy_score', 'learning_platform_usage_hours')
            ],
            polynomial_features=['intrinsic_motivation_score', 'manager_learning_support'],
            statistical_features=True
        )
        
        # Feature selection
        | select_features(
            method='k_best',
            k=20,
            score_func='f_classif',
            selector_name='engagement_features'
        )
        
        # Split data
        | split_train_test(
            test_size=0.25,
            stratify=True,
            split_name='engagement_split'
        )
        
        # Configure multi-class logistic regression
        | configure_logistic_regression(
            penalty='l2',
            C=1.0,
            solver='lbfgs',
            multi_class='multinomial',  # For multi-class
            class_weight='balanced',
            model_name='engagement_model'
        )
        
        # Fit and predict
        | fit_model('engagement_model', 'engagement_split')
        | predict('engagement_model', 'engagement_split', include_probabilities=True)
        
        # Evaluate model
        | evaluate_model('engagement_model')
        
        # Feature importance
        | calculate_feature_importance('engagement_model', method='coefficients')
        
        # Cross-validation
        | cross_validate_model('engagement_model', cv_folds=5, scoring='accuracy')
        
        # Hyperparameter tuning for multi-class
        | tune_hyperparameters(
            'engagement_model',
            param_grid={
                'C': [0.1, 0.5, 1.0, 2.0, 5.0],
                'penalty': ['l2', 'none'],
                'solver': ['lbfgs', 'newton-cg']
            },
            search_method='grid',
            cv_folds=3,
            scoring='f1_weighted',
            tuning_name='engagement_tuning'
        )
        
        # Final predictions
        | predict('engagement_model_tuned', 'engagement_split', prediction_name='final_engagement_predictions', include_probabilities=True)
        | evaluate_model('final_engagement_predictions')
        
        # Visualizations
        | plot_confusion_matrix('final_engagement_predictions')
        | plot_feature_importance('engagement_model', top_k=15)
        
        # Print summary
        | print_model_summary('engagement_model_tuned')
    )
    
    # Business insights
    print("\n=== Learning Engagement Prediction Results ===")
    
    final_metrics = engagement_model.evaluation_metrics.get('final_engagement_predictions', {})
    print(f"Model Accuracy: {final_metrics.get('accuracy', 0):.3f}")
    print(f"Weighted F1 Score: {final_metrics.get('f1_score', 0):.3f}")
    
    # Engagement distribution
    engagement_dist = engagement_df['engagement_level'].value_counts().sort_index()
    engagement_labels = ['Low', 'Medium', 'High']
    print(f"\nEngagement Level Distribution:")
    for level, count in engagement_dist.items():
        print(f"  {engagement_labels[level]}: {count} ({count/len(engagement_df)*100:.1f}%)")
    
    # Top factors for high engagement
    if 'engagement_model' in engagement_model.feature_importance:
        importance_data = engagement_model.feature_importance['engagement_model']['importance_data']
        print(f"\nTop Factors for Learning Engagement:")
        print(importance_data.head(10)[['feature', 'importance']])
    
    return engagement_model


# Example 5: Certification Renewal Risk Prediction
def example_certification_renewal_risk():
    """
    Predict risk of employees not renewing critical certifications
    """
    # Generate certification data
    np.random.seed(999)
    n_certifications = 3500
    
    cert_types = ['Technical Certification', 'Safety Certification', 'Professional License', 
                  'Industry Standard', 'Compliance Certification']
    cert_importance = {'Technical Certification': 'High', 'Safety Certification': 'Critical', 
                      'Professional License': 'Critical', 'Industry Standard': 'Medium', 
                      'Compliance Certification': 'High'}
    
    certification_data = []
    for i in range(n_certifications):
        # Certification details
        cert_type = np.random.choice(cert_types)
        importance = cert_importance[cert_type]
        
        # Employee characteristics
        employee_age = np.random.normal(40, 10)
        tenure = np.random.exponential(48)  # Longer tenure for certified employees
        job_level = np.random.choice(['Senior', 'Lead', 'Manager', 'Director'], p=[0.4, 0.3, 0.2, 0.1])
        
        # Certification history
        original_cert_date = datetime.now() - timedelta(days=np.random.randint(365, 2190))  # 1-6 years ago
        renewal_period_months = np.random.choice([12, 24, 36], p=[0.3, 0.5, 0.2])
        
        # Calculate time to renewal
        days_to_renewal = renewal_period_months * 30 - (datetime.now() - original_cert_date).days % (renewal_period_months * 30)
        
        # Performance and engagement
        performance_rating = np.random.normal(4.0, 0.6)  # Higher for certified employees
        career_advancement_rate = np.random.uniform(0, 3)  # Promotions/job changes per year
        
        # Learning and development
        training_hours_last_year = np.random.gamma(3, 10)
        continuing_education_participation = np.random.choice([0, 1], p=[0.3, 0.7])
        
        # Work factors
        role_requires_certification = np.random.choice([0, 1], p=[0.2, 0.8])
        certification_cost = np.random.gamma(2, 500)
        employer_pays_renewal = np.random.choice([0, 1], p=[0.3, 0.7])
        
        # External factors
        industry_demand_for_cert = np.random.uniform(2, 5)
        certification_difficulty = np.random.uniform(2, 5)
        study_time_required_hours = np.random.gamma(2, 20)
        
        # Personal factors
        work_life_balance = np.random.uniform(2, 5)
        intrinsic_motivation = np.random.uniform(2, 5)
        
        # Calculate renewal risk
        renewal_risk_prob = 0.1  # Base probability
        
        # Age and tenure effects
        if employee_age > 55:
            renewal_risk_prob += 0.15  # Near retirement
        if tenure > 120:  # 10+ years
            renewal_risk_prob += 0.1
            
        # Performance effects
        if performance_rating < 3:
            renewal_risk_prob += 0.2
        if career_advancement_rate > 2:
            renewal_risk_prob += 0.1  # Job hopping
            
        # Learning engagement effects
        if training_hours_last_year < 20:
            renewal_risk_prob += 0.15
        if not continuing_education_participation:
            renewal_risk_prob += 0.2
            
        # Work requirement effects
        if not role_requires_certification:
            renewal_risk_prob += 0.25
        if not employer_pays_renewal:
            renewal_risk_prob += 0.15
            
        # Certification characteristics
        if importance == 'Critical':
            renewal_risk_prob -= 0.1
        elif importance == 'Medium':
            renewal_risk_prob += 0.1
            
        if certification_difficulty > 4:
            renewal_risk_prob += 0.1
        if study_time_required_hours > 60:
            renewal_risk_prob += 0.15
            
        # External factors
        if industry_demand_for_cert < 3:
            renewal_risk_prob += 0.2
            
        # Personal factors
        if work_life_balance < 3:
            renewal_risk_prob += 0.1
        if intrinsic_motivation < 3:
            renewal_risk_prob += 0.15
            
        # Time pressure effect
        if days_to_renewal < 90:
            renewal_risk_prob += 0.05  # Last minute awareness
        elif days_to_renewal < 30:
            renewal_risk_prob += 0.2  # Very late
            
        # Cap probability
        renewal_risk_prob = min(0.8, max(0.02, renewal_risk_prob))
        
        # Generate outcome
        renewal_risk = np.random.binomial(1, renewal_risk_prob)
        
        certification_data.append({
            'cert_id': f'CERT_{i:04d}',
            'employee_age': max(25, min(70, employee_age)),
            'tenure_months': max(6, tenure),
            'job_level': job_level,
            'certification_type': cert_type,
            'certification_importance': importance,
            'days_to_renewal': max(1, days_to_renewal),
            'renewal_period_months': renewal_period_months,
            'performance_rating': np.clip(performance_rating, 1, 5),
            'career_advancement_rate': career_advancement_rate,
            'training_hours_last_year': max(0, training_hours_last_year),
            'continuing_education_participation': continuing_education_participation,
            'role_requires_certification': role_requires_certification,
            'certification_cost': certification_cost,
            'employer_pays_renewal': employer_pays_renewal,
            'industry_demand_for_cert': industry_demand_for_cert,
            'certification_difficulty': certification_difficulty,
            'study_time_required_hours': max(5, study_time_required_hours),
            'work_life_balance_score': work_life_balance,
            'intrinsic_motivation_score': intrinsic_motivation,
            'division': np.random.choice(['Administration', 'Acme Products', 'Private Operations']),
            'previous_renewals_count': np.random.poisson(2),
            'peer_renewal_rate': np.random.uniform(0.6, 0.95),
            'renewal_risk': renewal_risk
        })
    
    cert_df = pd.DataFrame(certification_data)
    
    # Certification renewal risk prediction pipeline
    cert_risk_model = (
        LogisticRegressionPipe.from_dataframe(cert_df)
        
        # Prepare data
        | prepare_classification_data(
            feature_columns=[
                'employee_age', 'tenure_months', 'days_to_renewal', 'renewal_period_months',
                'performance_rating', 'career_advancement_rate', 'training_hours_last_year',
                'continuing_education_participation', 'role_requires_certification',
                'certification_cost', 'employer_pays_renewal', 'industry_demand_for_cert',
                'certification_difficulty', 'study_time_required_hours', 'work_life_balance_score',
                'intrinsic_motivation_score', 'previous_renewals_count', 'peer_renewal_rate'
            ],
            target_column='renewal_risk',
            scaling_method='robust',
            remove_outliers=True
        )
        
        # Handle categorical features
        | prepare_classification_data(
            feature_columns=['job_level', 'certification_type', 'certification_importance', 'division'],
            target_column='renewal_risk',
            handle_categorical='dummy'
        )
        
        # Feature engineering
        | engineer_features(
            interaction_features=True,
            ratio_features=[
                ('certification_cost', 'employer_pays_renewal'),
                ('study_time_required_hours', 'work_life_balance_score'),
                ('training_hours_last_year', 'tenure_months'),
                ('performance_rating', 'intrinsic_motivation_score')
            ],
            polynomial_features=['performance_rating', 'industry_demand_for_cert'],
            binning_features={
                'days_to_renewal': 5,
                'employee_age': 4,
                'tenure_months': 5
            }
        )
        
        # Feature selection
        | select_features(
            method='rfe',
            k=25,
            selector_name='cert_risk_features'
        )
        
        # Split data
        | split_train_test(
            test_size=0.2,
            stratify=True,
            split_name='cert_risk_split'
        )
        
        # Configure model
        | configure_logistic_regression(
            penalty='elasticnet',
            C=1.0,
            solver='saga',
            l1_ratio=0.5,  # Mix of L1 and L2
            class_weight='balanced',
            model_name='cert_risk_model'
        )
        
        # Fit and evaluate
        | fit_model('cert_risk_model', 'cert_risk_split')
        | predict('cert_risk_model', 'cert_risk_split', include_probabilities=True)
        | evaluate_model('cert_risk_model')
        
        # Feature importance
        | calculate_feature_importance('cert_risk_model', method='coefficients')
        | calculate_feature_importance('cert_risk_model', method='permutation', importance_name='perm_importance')
        
        # Cross-validation
        | cross_validate_model('cert_risk_model', cv_folds=5, scoring='roc_auc')
        
        # Hyperparameter tuning
        | tune_hyperparameters(
            'cert_risk_model',
            param_grid={
                'C': [0.1, 0.5, 1.0, 2.0],
                'l1_ratio': [0.1, 0.3, 0.5, 0.7, 0.9],
                'penalty': ['elasticnet']
            },
            search_method='random',
            n_iter=15,
            cv_folds=3,
            scoring='f1',
            tuning_name='cert_risk_tuning'
        )
        
        # Final model evaluation
        | predict('cert_risk_model_tuned', 'cert_risk_split', prediction_name='final_cert_predictions', include_probabilities=True)
        | evaluate_model('final_cert_predictions')
        
        # Visualizations
        | plot_confusion_matrix('final_cert_predictions')
        | plot_feature_importance('cert_risk_model', top_k=20)
        | plot_roc_curve('final_cert_predictions')
        
        # Summary
        | print_model_summary('cert_risk_model_tuned')
        
        # Save model
        | save_model('cert_risk_model_tuned', 'certification_renewal_risk_model.joblib')
    )
    
    # Business insights
    print("\n=== Certification Renewal Risk Prediction Results ===")
    
    final_metrics = cert_risk_model.evaluation_metrics.get('final_cert_predictions', {})
    print(f"Final Model Performance:")
    print(f"  AUC Score: {final_metrics.get('auc_score', 0):.3f}")
    print(f"  Precision: {final_metrics.get('precision', 0):.3f}")
    print(f"  Recall: {final_metrics.get('recall', 0):.3f}")
    print(f"  F1 Score: {final_metrics.get('f1_score', 0):.3f}")
    
    # Risk analysis by certification type
    cert_type_risk = cert_df.groupby('certification_type')['renewal_risk'].agg(['count', 'sum', 'mean'])
    cert_type_risk.columns = ['Total_Certs', 'At_Risk', 'Risk_Rate']
    print(f"\nRenewal Risk by Certification Type:")
    print(cert_type_risk.sort_values('Risk_Rate', ascending=False))
    
    # Importance level analysis
    importance_risk = cert_df.groupby('certification_importance')['renewal_risk'].agg(['count', 'sum', 'mean'])
    importance_risk.columns = ['Total_Certs', 'At_Risk', 'Risk_Rate']
    print(f"\nRenewal Risk by Certification Importance:")
    print(importance_risk.sort_values('Risk_Rate', ascending=False))
    
    # Urgent renewals (next 90 days)
    urgent_renewals = cert_df[cert_df['days_to_renewal'] <= 90]
    print(f"\nUrgent Renewals (Next 90 Days): {len(urgent_renewals)}")
    print(f"High Risk Urgent Renewals: {urgent_renewals['renewal_risk'].sum()}")
    
    return cert_risk_model


# Example 6: Model Management and Lifecycle
def example_model_management():
    """
    Demonstrate comprehensive model management for HR churn prediction
    """
    # Generate sample HR data
    np.random.seed(111)
    n_employees = 2000
    
    # Simple employee dataset for model management demo
    management_data = []
    for i in range(n_employees):
        age = np.random.normal(35, 10)
        tenure = np.random.exponential(30)
        performance = np.random.normal(3.5, 0.8)
        training_completion = np.random.uniform(0.4, 1.0)
        satisfaction = np.random.uniform(2, 5)
        salary_percentile = np.random.uniform(0.2, 0.9)
        
        # Simple churn calculation
        churn_prob = 0.3 - (performance - 3) * 0.1 - (satisfaction - 3.5) * 0.1 - training_completion * 0.2
        churn_prob = np.clip(churn_prob, 0.05, 0.7)
        churned = np.random.binomial(1, churn_prob)
        
        management_data.append({
            'employee_id': f'EMP_{i:04d}',
            'age': max(22, min(65, age)),
            'tenure_months': max(1, tenure),
            'performance_rating': np.clip(performance, 1, 5),
            'training_completion_rate': training_completion,
            'satisfaction_score': satisfaction,
            'salary_percentile': salary_percentile,
            'division': np.random.choice(['Administration', 'Acme Products', 'Private Operations']),
            'churned': churned
        })
    
    management_df = pd.DataFrame(management_data)
    
    print("=== HR Churn Prediction Model Management Demo ===")
    
    # Step 1: Create and save initial model
    print("\nStep 1: Creating and saving initial model...")
    initial_model = (
        LogisticRegressionPipe.from_dataframe(management_df)
        
        | prepare_classification_data(
            feature_columns=['age', 'tenure_months', 'performance_rating', 
                           'training_completion_rate', 'satisfaction_score', 'salary_percentile'],
            target_column='churned',
            scaling_method='standard'
        )
        
        | split_train_test(test_size=0.2, stratify=True)
        
        | configure_logistic_regression(
            penalty='l2',
            C=1.0,
            class_weight='balanced',
            model_name='initial_churn_model'
        )
        
        | fit_model('initial_churn_model')
        | predict('initial_churn_model', include_probabilities=True)
        | evaluate_model('initial_churn_model')
        
        | save_model('initial_churn_model', 'hr_churn_model_v1.joblib')
    )
    
    # Step 2: Load model and make predictions on new data
    print("\nStep 2: Loading model and making predictions...")
    
    # Generate new employee data
    new_employees = []
    for i in range(500):
        new_employees.append({
            'employee_id': f'NEW_{i:04d}',
            'age': np.random.normal(33, 8),
            'tenure_months': np.random.exponential(20),
            'performance_rating': np.random.normal(3.8, 0.6),
            'training_completion_rate': np.random.uniform(0.5, 1.0),
            'satisfaction_score': np.random.uniform(2.5, 5),
            'salary_percentile': np.random.uniform(0.3, 0.8),
            'division': np.random.choice(['Administration', 'Acme Products', 'Private Operations'])
        })
    
    new_employees_df = pd.DataFrame(new_employees)
    
    loaded_model = (
        LogisticRegressionPipe.from_dataframe(new_employees_df)
        
        | load_model('hr_churn_model_v1.joblib', 'loaded_churn_model')
        
        # Note: In practice, you'd need to implement a predict_new_data method
        # For demo purposes, we'll show the model was loaded successfully
        | print_model_summary('loaded_churn_model')
    )
    
    # Step 3: Model comparison and selection
    print("\nStep 3: Model comparison and hyperparameter tuning...")
    comparison_model = (
        LogisticRegressionPipe.from_dataframe(management_df)
        
        | prepare_classification_data(
            feature_columns=['age', 'tenure_months', 'performance_rating', 
                           'training_completion_rate', 'satisfaction_score', 'salary_percentile'],
            target_column='churned',
            scaling_method='standard'
        )
        
        | engineer_features(
            interaction_features=True,
            ratio_features=[('performance_rating', 'satisfaction_score')]
        )
        
        | split_train_test(test_size=0.2, stratify=True)
        
        # Multiple models for comparison
        | configure_logistic_regression(
            penalty='l1', C=0.5, solver='liblinear', class_weight='balanced',
            model_name='l1_model'
        )
        
        | configure_logistic_regression(
            penalty='l2', C=1.0, class_weight='balanced',
            model_name='l2_model'
        )
        
        | configure_ridge_classifier(
            alpha=1.0, class_weight='balanced',
            model_name='ridge_model'
        )
        
        # Fit all models
        | fit_model('l1_model')
        | fit_model('l2_model')
        | fit_model('ridge_model')
        
        # Evaluate all models
        | predict('l1_model', prediction_name='l1_predictions', include_probabilities=True)
        | predict('l2_model', prediction_name='l2_predictions', include_probabilities=True)
        | predict('ridge_model', prediction_name='ridge_predictions')
        
        | evaluate_model('l1_predictions')
        | evaluate_model('l2_predictions')
        | evaluate_model('ridge_predictions')
        
        # Hyperparameter tuning for best model
        | tune_hyperparameters(
            'l2_model',
            param_grid={'C': [0.1, 0.5, 1.0, 2.0, 5.0]},
            search_method='grid',
            scoring='roc_auc'
        )
        
        | predict('l2_model_tuned', prediction_name='tuned_predictions', include_probabilities=True)
        | evaluate_model('tuned_predictions')
        
        | save_model('l2_model_tuned', 'hr_churn_model_v2.joblib')
    )
    
    # Model comparison results
    print("\nModel Performance Comparison:")
    models_to_compare = ['l1_predictions', 'l2_predictions', 'ridge_predictions', 'tuned_predictions']
    
    for model_name in models_to_compare:
        if model_name in comparison_model.evaluation_metrics:
            metrics = comparison_model.evaluation_metrics[model_name]
            auc = metrics.get('auc_score', 0)
            f1 = metrics.get('f1_score', 0)
            print(f"  {model_name}: AUC={auc:.3f}, F1={f1:.3f}")
    
    print("\n=== Model Management Demo Completed ===")
    
    return comparison_model


if __name__ == "__main__":
    print("Running HR Employee Learning Churn Prediction Pipeline Examples...")
    
    print("\n" + "="*70)
    print("Example 1: Employee Churn Prediction")
    print("="*70)
    employee_churn_model = example_employee_churn_prediction()
    
    print("\n" + "="*70)
    print("Example 2: Training Program Dropout Prediction")
    print("="*70)
    dropout_model = example_training_dropout_prediction()
    
    print("\n" + "="*70)
    print("Example 3: Skills Gap Risk Assessment")
    print("="*70)
    skills_risk_model = example_skills_gap_risk_prediction()
    
    print("\n" + "="*70)
    print("Example 4: Learning Engagement Prediction")
    print("="*70)
    engagement_model = example_learning_engagement_prediction()
    
    print("\n" + "="*70)
    print("Example 5: Certification Renewal Risk Prediction")
    print("="*70)
    cert_risk_model = example_certification_renewal_risk()
    
    print("\n" + "="*70)
    print("Example 6: Model Management and Lifecycle")
    print("="*70)
    management_example = example_model_management()
    
    print("\nAll HR Employee Learning Churn Prediction examples completed successfully!")
    
    # Summary of all models
    print("\n" + "="*70)
    print("HR CHURN PREDICTION MODELS SUMMARY")
    print("="*70)
    
    models = [
        ('Employee Churn', employee_churn_model, 'churn_model'),
        ('Training Dropout', dropout_model, 'tuned_predictions'),
        ('Skills Gap Risk', skills_risk_model, 'final_predictions'),
        ('Learning Engagement', engagement_model, 'final_engagement_predictions'),
        ('Certification Renewal Risk', cert_risk_model, 'final_cert_predictions')
    ]
    
    for name, model, prediction_key in models:
        print(f"\n{name}:")
        if hasattr(model, 'evaluation_metrics') and prediction_key in model.evaluation_metrics:
            metrics = model.evaluation_metrics[prediction_key]
            print(f"  Accuracy: {metrics.get('accuracy', 0):.3f}")
            print(f"  Precision: {metrics.get('precision', 0):.3f}")
            print(f"  Recall: {metrics.get('recall', 0):.3f}")
            print(f"  F1 Score: {metrics.get('f1_score', 0):.3f}")
            if 'auc_score' in metrics:
                print(f"  AUC Score: {metrics.get('auc_score', 0):.3f}")
        
        # Dataset info
        if hasattr(model, 'data'):
            n_samples = len(model.data)
            n_features = len(model.feature_columns) if hasattr(model, 'feature_columns') else 0
            print(f"  Dataset: {n_samples:,} samples, {n_features} features")
    
    print("\n" + "="*70)
    print("Key Insights and Business Applications:")
    print("="*70)
    print("1. Employee Churn: Identify at-risk employees for retention programs")
    print("2. Training Dropout: Optimize training design and support systems")
    print("3. Skills Gap Risk: Proactive skills development planning")
    print("4. Learning Engagement: Personalized learning recommendations")
    print("5. Certification Renewal: Ensure compliance and professional development")
    print("\nAll models demonstrate the power of logistic regression for HR analytics!")