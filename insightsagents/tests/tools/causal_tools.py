# Causal Inference Pipeline Examples

from app.tools.mltools.models.causal_inference import (
    CausalPipe,
    prepare_causal_data,
    estimate_propensity_scores,
    apply_matching,
    estimate_treatment_effects,
    design_ab_test,
    analyze_ab_test,
    check_covariate_balance,
    sensitivity_analysis,
    plot_propensity_distribution,
    plot_treatment_effects,
    plot_covariate_balance,
    save_causal_model,
    load_causal_model,
    add_features,
    inference,
    get_inference_results,
    print_causal_summary
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import tempfile


# Example 1: A/B Testing for E-commerce Website Feature
def example_ab_test_website_feature():
    """
    A/B test to measure the causal effect of a new checkout flow on conversion rates
    """
    # Generate realistic A/B test data
    np.random.seed(42)
    n_users = 5000
    
    # User characteristics that might affect conversion
    user_age = np.random.normal(35, 12, n_users)
    user_income = np.random.lognormal(10, 0.5, n_users)
    previous_purchases = np.random.poisson(2, n_users)
    session_duration = np.random.gamma(2, 10, n_users)  # minutes
    device_type = np.random.choice(['mobile', 'desktop', 'tablet'], n_users, p=[0.6, 0.35, 0.05])
    traffic_source = np.random.choice(['organic', 'paid', 'direct', 'social'], n_users, p=[0.4, 0.3, 0.2, 0.1])
    
    # Random assignment to treatment (new checkout flow = 1, old = 0)
    treatment_assignment = np.random.binomial(1, 0.5, n_users)
    
    # Conversion probability depends on treatment and user characteristics
    base_conversion_prob = (
        0.03 +  # Base conversion rate
        0.001 * (user_age - 30) +  # Age effect
        0.00001 * (user_income - 50000) +  # Income effect
        0.01 * previous_purchases +  # Loyalty effect
        0.002 * session_duration +  # Engagement effect
        (device_type == 'desktop').astype(int) * 0.01 +  # Device effect
        (traffic_source == 'paid').astype(int) * 0.015  # Traffic source effect
    )
    
    # Treatment effect: new checkout flow increases conversion by 25%
    treatment_effect = 0.01  # 1 percentage point increase
    conversion_prob = base_conversion_prob + treatment_assignment * treatment_effect
    
    # Generate conversion outcomes
    conversions = np.random.binomial(1, np.clip(conversion_prob, 0, 1), n_users)
    
    ab_test_data = pd.DataFrame({
        'user_id': [f'USER_{i:05d}' for i in range(n_users)],
        'age': np.clip(user_age, 18, 80),
        'estimated_income': np.clip(user_income, 20000, 500000),
        'previous_purchases': previous_purchases,
        'session_duration_minutes': session_duration,
        'device_type': device_type,
        'traffic_source': traffic_source,
        'new_checkout_flow': treatment_assignment,
        'converted': conversions,
        'true_effect': treatment_effect  # For validation
    })
    
    # A/B Test Analysis Pipeline
    ab_test_analysis = (
        CausalPipe.from_dataframe(ab_test_data)
        
        # Prepare data for causal analysis
        | prepare_causal_data(
            treatment_column='new_checkout_flow',
            outcome_column='converted',
            covariate_columns=[
                'age', 'estimated_income', 'previous_purchases', 
                'session_duration_minutes'
            ]
        )
        
        # Design A/B test (power analysis)
        | design_ab_test(
            effect_size=0.01,  # Expected 1 percentage point increase
            baseline_rate=0.05,  # Expected baseline conversion rate
            power=0.8,
            alpha=0.05,
            test_name='checkout_flow_test'
        )
        
        # Analyze A/B test results
        | analyze_ab_test(
            confidence_level=0.95,
            test_name='checkout_flow_results'
        )
        
        # Estimate treatment effects using multiple methods
        | estimate_treatment_effects(
            methods=['ate', 'doubly_robust'],
            analysis_name='checkout_effects'
        )
        
        # Check randomization balance (should be good in A/B test)
        | check_covariate_balance(balance_threshold=0.1, test_name='randomization_check')
        
        # Plot results
        | plot_treatment_effects('checkout_effects')
        | plot_covariate_balance('randomization_check')
        
        # Sensitivity analysis
        | sensitivity_analysis(
            hidden_confounder_strength=[0.05, 0.1, 0.15, 0.2],
            analysis_name='checkout_sensitivity'
        )
        
        # Summary and save
        | print_causal_summary()
        | save_causal_model(['effects'], 'checkout_ab_test_model.joblib')
    )
    
    # Validate against true effect
    estimated_ate = ab_test_analysis.treatment_effects['checkout_effects']['ate']['estimate']
    true_effect = ab_test_data['true_effect'].iloc[0]
    
    print(f"\n=== Validation ===")
    print(f"True ATE: {true_effect:.4f}")
    print(f"Estimated ATE: {estimated_ate:.4f}")
    print(f"Estimation Error: {abs(estimated_ate - true_effect):.4f}")
    
    return ab_test_analysis


# Example 2: Observational Study with Propensity Score Matching
def example_observational_study_education():
    """
    Estimate the causal effect of college education on income using observational data
    """
    # Generate observational data with confounding
    np.random.seed(123)
    n_individuals = 3000
    
    # Background characteristics that affect both education and income
    family_income = np.random.lognormal(10, 0.6, n_individuals)
    parent_education = np.random.normal(12, 3, n_individuals)  # Years of education
    cognitive_ability = np.random.normal(100, 15, n_individuals)  # IQ-like measure
    motivation = np.random.beta(3, 2, n_individuals) * 10  # 0-10 scale
    age = np.random.normal(30, 8, n_individuals)
    
    # Geographic and demographic factors
    urban_area = np.random.binomial(1, 0.6, n_individuals)
    gender = np.random.binomial(1, 0.5, n_individuals)  # 1 = male, 0 = female
    
    # Probability of college education (confounded by family background)
    college_prob = (
        -3.0 +
        0.00002 * family_income +  # Higher family income → more likely to attend college
        0.1 * parent_education +    # More educated parents → more likely
        0.02 * cognitive_ability +  # Higher ability → more likely
        0.1 * motivation +          # Higher motivation → more likely
        0.3 * urban_area +          # Urban → more access to colleges
        np.random.normal(0, 0.5, n_individuals)  # Random variation
    )
    
    college_education = (1 / (1 + np.exp(-college_prob)) > 0.5).astype(int)
    
    # Income is affected by education AND the same confounders
    log_income = (
        9.5 +  # Base log income
        0.3 * college_education +     # TRUE CAUSAL EFFECT of college
        0.00001 * family_income +     # Family background effect
        0.02 * parent_education +     # Parent education effect
        0.01 * cognitive_ability +    # Ability effect
        0.05 * motivation +           # Motivation effect
        0.02 * age +                  # Experience effect
        0.1 * urban_area +            # Urban wage premium
        0.05 * gender +               # Gender wage gap
        np.random.normal(0, 0.3, n_individuals)  # Random variation
    )
    
    income = np.exp(log_income)
    
    education_data = pd.DataFrame({
        'individual_id': [f'IND_{i:04d}' for i in range(n_individuals)],
        'family_income': family_income,
        'parent_education_years': np.clip(parent_education, 6, 20),
        'cognitive_ability_score': np.clip(cognitive_ability, 70, 140),
        'motivation_score': motivation,
        'age': np.clip(age, 22, 65),
        'urban_area': urban_area,
        'gender_male': gender,
        'college_education': college_education,
        'annual_income': income,
        'true_college_effect': 0.3  # True log income effect
    })
    
    # Observational Study Analysis Pipeline
    education_analysis = (
        CausalPipe.from_dataframe(education_data)
        
        # Prepare data for causal analysis
        | prepare_causal_data(
            treatment_column='college_education',
            outcome_column='annual_income',
            covariate_columns=[
                'family_income', 'parent_education_years', 'cognitive_ability_score',
                'motivation_score', 'age', 'urban_area', 'gender_male'
            ],
            standardize_covariates=True
        )
        
        # Estimate propensity scores (probability of college attendance)
        | estimate_propensity_scores(
            method='logistic',
            model_name='education_propensity'
        )
        
        # Check propensity score quality
        | plot_propensity_distribution('education_propensity')
        
        # Apply propensity score matching
        | apply_matching(
            method='nearest_neighbor',
            n_neighbors=1,
            caliper=0.1,  # Maximum propensity score difference
            matching_name='education_matched'
        )
        
        # Check covariate balance before matching
        | check_covariate_balance(
            matching_name=None,  # Original data
            test_name='balance_before'
        )
        
        # Check covariate balance after matching
        | check_covariate_balance(
            matching_name='education_matched',
            test_name='balance_after'
        )
        
        # Estimate treatment effects on matched sample
        | estimate_treatment_effects(
            methods=['ate', 'att', 'ipw', 'doubly_robust'],
            outcome_model='linear',
            analysis_name='education_effects'
        )
        
        # Visualize results
        | plot_treatment_effects('education_effects')
        | plot_covariate_balance('balance_before')
        | plot_covariate_balance('balance_after')
        
        # Sensitivity analysis for unmeasured confounding
        | sensitivity_analysis(
            hidden_confounder_strength=[0.1, 0.2, 0.3, 0.4, 0.5],
            analysis_name='education_sensitivity'
        )
        
        # Summary
        | print_causal_summary()
        | save_causal_model(['propensity', 'effects'], 'education_causal_model.joblib')
    )
    
    # Compare with naive estimate (ignoring confounding)
    college_group = education_data[education_data['college_education'] == 1]['annual_income']
    no_college_group = education_data[education_data['college_education'] == 0]['annual_income']
    naive_effect = college_group.mean() - no_college_group.mean()
    
    # Get causal estimate
    causal_ate = education_analysis.treatment_effects['education_effects']['ate']['estimate']
    
    print(f"\n=== Comparison of Estimates ===")
    print(f"Naive Difference: ${naive_effect:,.0f}")
    print(f"Causal ATE (Matched): ${causal_ate:,.0f}")
    print(f"True Effect (on log scale): {education_data['true_college_effect'].iloc[0]:.2f}")
    print(f"Bias Reduction: {abs(naive_effect - causal_ate):,.0f}")
    
    return education_analysis


# Example 3: Marketing Campaign Effectiveness Analysis
def example_marketing_campaign_analysis():
    """
    Evaluate the causal impact of a targeted marketing campaign on customer purchases
    """
    # Generate customer data with campaign targeting
    np.random.seed(456)
    n_customers = 4000
    
    # Customer characteristics
    customer_age = np.random.normal(40, 15, n_customers)
    customer_income = np.random.lognormal(10.5, 0.7, n_customers)
    previous_purchases = np.random.poisson(5, n_customers)
    engagement_score = np.random.beta(2, 3, n_customers) * 100  # 0-100
    loyalty_years = np.random.exponential(2, n_customers)
    
    # Geographic and channel factors
    premium_location = np.random.binomial(1, 0.3, n_customers)
    email_subscriber = np.random.binomial(1, 0.7, n_customers)
    mobile_app_user = np.random.binomial(1, 0.4, n_customers)
    
    # Campaign targeting (NOT random - this is the key!)
    # Marketing team targets high-value, engaged customers
    campaign_target_score = (
        0.00001 * customer_income +
        0.1 * previous_purchases +
        0.01 * engagement_score +
        0.2 * loyalty_years +
        0.5 * premium_location +
        0.3 * email_subscriber +
        0.4 * mobile_app_user +
        np.random.normal(0, 0.5, n_customers)
    )
    
    # Campaign targeting decision (top 40% get campaign)
    campaign_threshold = np.percentile(campaign_target_score, 60)
    received_campaign = (campaign_target_score > campaign_threshold).astype(int)
    
    # Purchase behavior (outcome)
    # Both campaign AND customer characteristics affect purchases
    purchase_propensity = (
        0.1 +  # Base purchase rate
        0.05 * received_campaign +      # TRUE CAMPAIGN EFFECT
        0.000005 * customer_income +    # Income effect
        0.01 * previous_purchases +     # Loyalty effect
        0.002 * engagement_score +      # Engagement effect
        0.02 * loyalty_years +          # Tenure effect
        0.03 * premium_location +       # Location effect
        0.02 * email_subscriber +       # Email effect
        np.random.normal(0, 0.05, n_customers)
    )
    
    made_purchase = np.random.binomial(1, np.clip(purchase_propensity, 0, 1), n_customers)
    
    # Purchase amount for those who purchased
    purchase_amounts = np.where(
        made_purchase == 1,
        np.random.gamma(2, 100) + received_campaign * 20,  # Campaign increases amount too
        0
    )
    
    campaign_data = pd.DataFrame({
        'customer_id': [f'CUST_{i:04d}' for i in range(n_customers)],
        'age': np.clip(customer_age, 18, 80),
        'annual_income': customer_income,
        'previous_purchases_12m': previous_purchases,
        'engagement_score': engagement_score,
        'loyalty_years': loyalty_years,
        'premium_location': premium_location,
        'email_subscriber': email_subscriber,
        'mobile_app_user': mobile_app_user,
        'received_campaign': received_campaign,
        'made_purchase': made_purchase,
        'purchase_amount': purchase_amounts,
        'target_score': campaign_target_score,
        'true_campaign_effect_rate': 0.05,
        'true_campaign_effect_amount': 20
    })
    
    # Marketing Campaign Analysis Pipeline
    campaign_analysis = (
        CausalPipe.from_dataframe(campaign_data)
        
        # Analyze purchase probability first
        | prepare_causal_data(
            treatment_column='received_campaign',
            outcome_column='made_purchase',
            covariate_columns=[
                'age', 'annual_income', 'previous_purchases_12m', 'engagement_score',
                'loyalty_years', 'premium_location', 'email_subscriber', 'mobile_app_user'
            ]
        )
        
        # Estimate propensity scores (campaign targeting model)
        | estimate_propensity_scores(
            method='random_forest',
            model_params={'n_estimators': 100, 'random_state': 42},
            model_name='campaign_propensity'
        )
        
        # Visualize targeting bias
        | plot_propensity_distribution('campaign_propensity')
        
        # Apply inverse probability weighting
        | estimate_treatment_effects(
            methods=['ate', 'att', 'ipw', 'doubly_robust'],
            outcome_model='random_forest',
            analysis_name='campaign_purchase_effects'
        )
        
        # Also apply matching for comparison
        | apply_matching(
            method='nearest_neighbor',
            n_neighbors=2,
            caliper=0.2,
            matching_name='campaign_matched'
        )
        
        # Check balance
        | check_covariate_balance(test_name='targeting_bias_check')
        | check_covariate_balance(
            matching_name='campaign_matched',
            test_name='matched_balance_check'
        )
        
        # Visualize results
        | plot_treatment_effects('campaign_purchase_effects')
        | plot_covariate_balance('targeting_bias_check')
        | plot_covariate_balance('matched_balance_check')
        
        # Sensitivity analysis
        | sensitivity_analysis(analysis_name='campaign_sensitivity')
        
        # Save the trained model
        | save_causal_model(['all'], 'marketing_campaign_model.joblib')
        
        # Summary
        | print_causal_summary()
    )
    
    print("\n=== Loading Saved Model for Additional Analysis ===")
    
    # Load the saved model for additional analysis
    loaded_campaign_model = (
        CausalPipe.from_dataframe(campaign_data)
        | load_causal_model('marketing_campaign_model.joblib', 'loaded_campaign_model')
    )
    
    print("Model loaded successfully. Available components:")
    print(f"- Propensity models: {list(loaded_campaign_model.propensity_models.keys())}")
    print(f"- Treatment effects: {list(loaded_campaign_model.treatment_effects.keys())}")
    print(f"- Balance tests: {list(loaded_campaign_model.balance_tests.keys())}")
    
    # Add new features to the loaded model
    campaign_data['high_value_customer'] = (campaign_data['annual_income'] > 100000).astype(int)
    campaign_data['engagement_income_interaction'] = campaign_data['engagement_score'] * campaign_data['annual_income'] / 1000000
    
    # Create new pipeline with additional features
    enhanced_campaign_analysis = (
        CausalPipe.from_dataframe(campaign_data)
        | load_causal_model('marketing_campaign_model.joblib', 'enhanced_model')
        
        # Add new features
        | add_features(
            feature_columns=['high_value_customer', 'engagement_income_interaction'],
            feature_type='covariate',
            feature_name='enhanced_features'
        )
        
        # Re-prepare data with new features
        | prepare_causal_data(
            treatment_column='received_campaign',
            outcome_column='made_purchase',
            covariate_columns=[
                'age', 'annual_income', 'previous_purchases_12m', 'engagement_score',
                'loyalty_years', 'premium_location', 'email_subscriber', 'mobile_app_user',
                'high_value_customer', 'engagement_income_interaction'
            ]
        )
        
        # Re-estimate with enhanced features
        | estimate_propensity_scores(
            method='random_forest',
            model_params={'n_estimators': 150, 'random_state': 42},
            model_name='enhanced_campaign_propensity'
        )
        
        | estimate_treatment_effects(
            methods=['ate', 'doubly_robust'],
            outcome_model='random_forest',
            analysis_name='enhanced_campaign_effects'
        )
        
        # Save enhanced model
        | save_causal_model(['all'], 'enhanced_marketing_campaign_model.joblib')
        
        | print_causal_summary()
    )
    
    # Clean up saved files
    import os
    if os.path.exists('marketing_campaign_model.joblib'):
        os.remove('marketing_campaign_model.joblib')
    if os.path.exists('enhanced_marketing_campaign_model.joblib'):
        os.remove('enhanced_marketing_campaign_model.joblib')
    
    print("\n=== Model Comparison ===")
    original_ate = campaign_analysis.treatment_effects['campaign_purchase_effects']['ate']['estimate']
    enhanced_ate = enhanced_campaign_analysis.treatment_effects['enhanced_campaign_effects']['ate']['estimate']
    
    print(f"Original Model ATE: {original_ate:.4f}")
    print(f"Enhanced Model ATE: {enhanced_ate:.4f}")
    print(f"Difference: {abs(enhanced_ate - original_ate):.4f}")
    
    return {
        'original_analysis': campaign_analysis,
        'enhanced_analysis': enhanced_campaign_analysis,
        'loaded_model': loaded_campaign_model
    }
    
    """
    # Analyze purchase amounts separately (for those who purchased)
    purchased_data = campaign_data[campaign_data['made_purchase'] == 1].copy()
    
    if len(purchased_data) > 100:  # Ensure sufficient data
        amount_analysis = (
            CausalPipe.from_dataframe(purchased_data)
            
            | prepare_causal_data(
                treatment_column='received_campaign',
                outcome_column='purchase_amount',
                covariate_columns=[
                    'age', 'annual_income', 'previous_purchases_12m', 'engagement_score',
                    'loyalty_years', 'premium_location'
                ]
            )
            
            | estimate_propensity_scores(method='logistic', model_name='amount_propensity')
            
            | estimate_treatment_effects(
                methods=['ate', 'doubly_robust'],
                analysis_name='campaign_amount_effects'
            )
            
            | print_causal_summary()
        )
    
    # Compare with naive analysis
    campaign_customers = campaign_data[campaign_data['received_campaign'] == 1]
    no_campaign_customers = campaign_data[campaign_data['received_campaign'] == 0]
    
    naive_purchase_effect = (
        campaign_customers['made_purchase'].mean() - 
        no_campaign_customers['made_purchase'].mean()
    )
    
    causal_purchase_effect = campaign_analysis.treatment_effects['campaign_purchase_effects']['ate']['estimate']
    
    print(f"\n=== Campaign Effectiveness Analysis ===")
    print(f"Naive Purchase Rate Difference: {naive_purchase_effect:.4f} ({naive_purchase_effect*100:.2f}%)")
    print(f"Causal Purchase Rate Effect: {causal_purchase_effect:.4f} ({causal_purchase_effect*100:.2f}%)")
    print(f"True Campaign Effect: {campaign_data['true_campaign_effect_rate'].iloc[0]:.4f} ({campaign_data['true_campaign_effect_rate'].iloc[0]*100:.2f}%)")
    print(f"Selection Bias: {naive_purchase_effect - causal_purchase_effect:.4f} ({(naive_purchase_effect - causal_purchase_effect)*100:.2f}%)")
    
    return campaign_analysis
    """

# Example 4: Policy Intervention Evaluation
def example_policy_intervention_evaluation():
    """
    Evaluate the causal effect of a job training program on employment outcomes
    """
    # Generate data for a job training program evaluation
    np.random.seed(789)
    n_participants = 2500
    
    # Pre-intervention characteristics
    age = np.random.normal(35, 12, n_participants)
    education_years = np.random.normal(11, 3, n_participants)
    previous_work_experience = np.random.exponential(8, n_participants)
    unemployment_duration = np.random.exponential(6, n_participants)  # months
    
    # Demographics and location
    gender_male = np.random.binomial(1, 0.6, n_participants)
    minority_status = np.random.binomial(1, 0.4, n_participants)
    urban_location = np.random.binomial(1, 0.7, n_participants)
    
    # Skills and barriers
    baseline_skills_score = np.random.normal(50, 15, n_participants)
    transportation_access = np.random.binomial(1, 0.8, n_participants)
    childcare_constraints = np.random.binomial(1, 0.3, n_participants)
    
    # Program eligibility and participation (quasi-experimental design)
    # Participants self-select based on motivation and circumstances
    participation_propensity = (
        -2.0 +
        0.02 * (age - 35) +
        0.1 * education_years +
        -0.1 * previous_work_experience +  # Desperate people more likely to join
        0.05 * unemployment_duration +
        0.3 * minority_status +  # Targeted outreach
        0.4 * urban_location +   # Program availability
        -0.3 * childcare_constraints +  # Barrier to participation
        0.3 * transportation_access +
        np.random.normal(0, 1, n_participants)
    )
    
    program_participation = (1 / (1 + np.exp(-participation_propensity)) > 0.4).astype(int)
    
    # Employment outcomes (6 months post-program)
    # Both program participation AND individual characteristics matter
    employment_propensity = (
        -1.0 +
        0.2 * program_participation +      # TRUE PROGRAM EFFECT
        0.01 * age +
        0.1 * education_years +
        0.05 * previous_work_experience +
        -0.02 * unemployment_duration +
        0.3 * gender_male +               # Gender employment gap
        -0.2 * minority_status +          # Discrimination effect
        0.01 * baseline_skills_score +
        0.3 * transportation_access +
        -0.4 * childcare_constraints +
        np.random.normal(0, 0.8, n_participants)
    )
    
    employed_6m_post = (1 / (1 + np.exp(-employment_propensity)) > 0.5).astype(int)
    
    # Monthly earnings for employed individuals
    log_earnings = np.where(
        employed_6m_post == 1,
        7.5 +  # Base log earnings
        0.1 * program_participation +      # Program earnings premium
        0.01 * age +
        0.05 * education_years +
        0.02 * previous_work_experience +
        0.005 * baseline_skills_score +
        0.1 * gender_male +
        -0.1 * minority_status +
        np.random.normal(0, 0.3, n_participants),
        0  # No earnings if unemployed
    )
    
    monthly_earnings = np.where(employed_6m_post == 1, np.exp(log_earnings), 0)
    
    policy_data = pd.DataFrame({
        'participant_id': [f'P_{i:04d}' for i in range(n_participants)],
        'age': np.clip(age, 18, 65),
        'education_years': np.clip(education_years, 6, 18),
        'work_experience_years': previous_work_experience,
        'unemployment_months': unemployment_duration,
        'gender_male': gender_male,
        'minority_status': minority_status,
        'urban_location': urban_location,
        'baseline_skills_score': np.clip(baseline_skills_score, 20, 80),
        'transportation_access': transportation_access,
        'childcare_constraints': childcare_constraints,
        'training_program_participation': program_participation,
        'employed_6m_post': employed_6m_post,
        'monthly_earnings_6m_post': monthly_earnings,
        'true_employment_effect': 0.2,
        'true_earnings_effect': 0.1
    })
    
    # Policy Evaluation Analysis Pipeline
    policy_analysis = (
        CausalPipe.from_dataframe(policy_data)
        
        # Analyze employment effect
        | prepare_causal_data(
            treatment_column='training_program_participation',
            outcome_column='employed_6m_post',
            covariate_columns=[
                'age', 'education_years', 'work_experience_years', 'unemployment_months',
                'gender_male', 'minority_status', 'urban_location', 'baseline_skills_score',
                'transportation_access', 'childcare_constraints'
            ]
        )
        
        # Estimate participation propensity
        | estimate_propensity_scores(
            method='random_forest',
            model_params={'n_estimators': 200, 'max_depth': 10, 'random_state': 42},
            model_name='program_propensity'
        )
        
        # Check propensity scores
        | plot_propensity_distribution('program_propensity')
        
        # Multiple matching approaches
        | apply_matching(
            method='nearest_neighbor',
            n_neighbors=1,
            caliper=0.15,
            matching_name='nn_matched'
        )
        
        | apply_matching(
            method='stratified',
            matching_name='stratified_matched'
        )
        
        # Estimate treatment effects using all methods
        | estimate_treatment_effects(
            methods=['ate', 'att', 'ipw', 'doubly_robust'],
            outcome_model='random_forest',
            analysis_name='employment_effects'
        )
        
        # Comprehensive balance checking
        | check_covariate_balance(
            matching_name=None,
            test_name='selection_bias_check'
        )
        
        | check_covariate_balance(
            matching_name='nn_matched',
            test_name='nn_balance_check'
        )
        
        | check_covariate_balance(
            matching_name='stratified_matched',
            test_name='stratified_balance_check'
        )
        
        # Visualizations
        | plot_treatment_effects('employment_effects')
        | plot_covariate_balance('selection_bias_check')
        | plot_covariate_balance('nn_balance_check')
        
        # Robustness checks
        | sensitivity_analysis(
            hidden_confounder_strength=[0.05, 0.1, 0.15, 0.2, 0.25, 0.3],
            analysis_name='policy_sensitivity'
        )
        
        # Summary
        | print_causal_summary()
        | save_causal_model(['all'], 'job_training_policy_model.joblib')
    )
    
    # Analyze earnings effect for employed individuals
    employed_data = policy_data[policy_data['employed_6m_post'] == 1].copy()
    
    if len(employed_data) > 200:
        earnings_analysis = (
            CausalPipe.from_dataframe(employed_data)
            
            | prepare_causal_data(
                treatment_column='training_program_participation',
                outcome_column='monthly_earnings_6m_post',
                covariate_columns=[
                    'age', 'education_years', 'work_experience_years',
                    'baseline_skills_score', 'gender_male', 'minority_status'
                ]
            )
            
            | estimate_propensity_scores(method='logistic', model_name='earnings_propensity')
            
            | estimate_treatment_effects(
                methods=['ate', 'doubly_robust'],
                analysis_name='earnings_effects'
            )
        )
        
        print(f"\n=== Earnings Analysis (Employed Only) ===")
        earnings_ate = earnings_analysis.treatment_effects['earnings_effects']['ate']['estimate']
        print(f"Program Effect on Monthly Earnings: ${earnings_ate:.0f}")
        print(f"True Earnings Effect: ${policy_data['true_earnings_effect'].iloc[0] * 1800:.0f}")  # Rough estimate
    
    # Policy Impact Summary
    naive_employment_effect = (
        policy_data[policy_data['training_program_participation'] == 1]['employed_6m_post'].mean() -
        policy_data[policy_data['training_program_participation'] == 0]['employed_6m_post'].mean()
    )
    
    causal_employment_effect = policy_analysis.treatment_effects['employment_effects']['ate']['estimate']
    true_effect = policy_data['true_employment_effect'].iloc[0]
    
    print(f"\n=== Policy Impact Assessment ===")
    print(f"Naive Employment Effect: {naive_employment_effect:.4f} ({naive_employment_effect*100:.2f}%)")
    print(f"Causal Employment Effect: {causal_employment_effect:.4f} ({causal_employment_effect*100:.2f}%)")
    print(f"True Program Effect: {true_effect:.4f} ({true_effect*100:.2f}%)")
    print(f"Selection Bias Magnitude: {abs(naive_employment_effect - causal_employment_effect):.4f}")
    
    # Cost-benefit analysis (simplified)
    program_cost_per_participant = 5000  # Hypothetical cost
    participants_treated = policy_data['training_program_participation'].sum()
    
    # Benefits: increased employment * average earnings gain * 12 months
    if len(employed_data) > 200:
        avg_earnings_gain = earnings_analysis.treatment_effects['earnings_effects']['ate']['estimate']
        annual_benefit_per_participant = causal_employment_effect * avg_earnings_gain * 12
    else:
        annual_benefit_per_participant = causal_employment_effect * 2000 * 12  # Rough estimate
    
    total_annual_benefits = annual_benefit_per_participant * participants_treated
    total_program_costs = program_cost_per_participant * participants_treated
    
    print(f"\n=== Cost-Benefit Analysis ===")
    print(f"Program Participants: {participants_treated}")
    print(f"Total Program Cost: ${total_program_costs:,.0f}")
    print(f"Annual Benefit per Participant: ${annual_benefit_per_participant:,.0f}")
    print(f"Total Annual Benefits: ${total_annual_benefits:,.0f}")
    print(f"Benefit-Cost Ratio: {total_annual_benefits / total_program_costs:.2f}")
    
    return policy_analysis


# Example 5: Advanced Causal Analysis with Multiple Treatment Effects
def example_advanced_causal_analysis():
    """
    Advanced causal analysis with heterogeneous treatment effects and multiple outcomes
    """
    # Generate complex dataset with heterogeneous effects
    np.random.seed(999)
    n_observations = 3500
    
    # Individual characteristics
    age = np.random.normal(45, 15, n_observations)
    income = np.random.lognormal(10.8, 0.8, n_observations)
    education = np.random.normal(14, 4, n_observations)
    health_status = np.random.normal(7, 2, n_observations)  # 1-10 scale
    
    # Geographic and social factors
    rural_location = np.random.binomial(1, 0.3, n_observations)
    social_support = np.random.beta(3, 2, n_observations) * 10
    
    # Treatment assignment (wellness program)
    # Complex selection process with multiple factors
    treatment_propensity = (
        -1.5 +
        0.01 * (age - 45) +
        0.00001 * (income - 60000) +
        0.05 * education +
        -0.1 * health_status +  # Sicker people more likely to join
        -0.3 * rural_location +  # Less access in rural areas
        0.1 * social_support +
        np.random.normal(0, 1, n_observations)
    )
    
    treatment_assignment = (1 / (1 + np.exp(-treatment_propensity)) > 0.4).astype(int)
    
    # Heterogeneous treatment effects
    # Effect varies by age and baseline health
    treatment_effect_health = (
        0.5 +  # Base effect
        0.01 * (age - 45) +  # Older people benefit more
        -0.1 * health_status  # Sicker people benefit more
    )
    
    treatment_effect_satisfaction = (
        1.0 +
        0.02 * education +  # Educated people more satisfied
        0.05 * social_support
    )
    
    # Outcomes
    # Health improvement (continuous)
    health_improvement = (
        1.0 +  # Base improvement
        treatment_assignment * treatment_effect_health +
        0.01 * age +
        0.00001 * income +
        0.05 * education +
        0.1 * social_support +
        -0.2 * rural_location +
        np.random.normal(0, 1, n_observations)
    )
    
    # Life satisfaction (continuous, 1-10)
    life_satisfaction = np.clip(
        5.0 +
        treatment_assignment * treatment_effect_satisfaction +
        0.00002 * income +
        0.1 * health_status +
        0.1 * social_support +
        np.random.normal(0, 1, n_observations),
        1, 10
    )
    
    # Healthcare utilization (count outcome)
    healthcare_visits = np.random.poisson(
        np.exp(
            1.5 +
            -0.3 * treatment_assignment +  # Treatment reduces healthcare usage
            0.01 * age +
            -0.05 * health_status +
            0.1 * rural_location
        )
    )
    
    advanced_causal_data = pd.DataFrame({
        'individual_id': [f'ADV_{i:04d}' for i in range(n_observations)],
        'age': np.clip(age, 18, 85),
        'annual_income': income,
        'education_years': np.clip(education, 8, 20),
        'baseline_health_status': np.clip(health_status, 1, 10),
        'rural_location': rural_location,
        'social_support_score': social_support,
        'wellness_program': treatment_assignment,
        'health_improvement_score': health_improvement,
        'life_satisfaction_score': life_satisfaction,
        'healthcare_visits_12m': healthcare_visits,
        'true_health_effect': treatment_effect_health,
        'true_satisfaction_effect': treatment_effect_satisfaction
    })
    
    # Advanced Causal Analysis Pipeline
    advanced_analysis = (
        CausalPipe.from_dataframe(advanced_causal_data)
        
        # Primary analysis: Health improvement
        | prepare_causal_data(
            treatment_column='wellness_program',
            outcome_column='health_improvement_score',
            covariate_columns=[
                'age', 'annual_income', 'education_years', 'baseline_health_status',
                'rural_location', 'social_support_score'
            ]
        )
        
        # High-quality propensity score estimation
        | estimate_propensity_scores(
            method='random_forest',
            model_params={
                'n_estimators': 200,
                'max_depth': 8,
                'min_samples_split': 10,
                'random_state': 42
            },
            model_name='wellness_propensity'
        )
        
        # Comprehensive treatment effect estimation
        | estimate_treatment_effects(
            methods=['ate', 'att', 'ipw', 'doubly_robust'],
            outcome_model='random_forest',
            confidence_level=0.95,
            analysis_name='health_effects'
        )
        
        # Multiple matching strategies
        | apply_matching(
            method='nearest_neighbor',
            n_neighbors=2,
            caliper=0.1,
            matching_name='health_nn_matched'
        )
        
        | apply_matching(
            method='stratified',
            matching_name='health_stratified'
        )
        
        # Balance assessment
        | check_covariate_balance(test_name='health_original_balance')
        | check_covariate_balance(
            matching_name='health_nn_matched',
            test_name='health_nn_balance'
        )
        
        # Visualizations
        | plot_propensity_distribution('wellness_propensity')
        | plot_treatment_effects('health_effects')
        | plot_covariate_balance('health_original_balance')
        | plot_covariate_balance('health_nn_balance')
        
        # Comprehensive sensitivity analysis
        | sensitivity_analysis(
            hidden_confounder_strength=np.arange(0.05, 0.51, 0.05).tolist(),
            analysis_name='health_sensitivity'
        )
        
        | print_causal_summary()
    )
    
    # Secondary analysis: Life satisfaction
    satisfaction_analysis = (
        CausalPipe.from_dataframe(advanced_causal_data)
        
        | prepare_causal_data(
            treatment_column='wellness_program',
            outcome_column='life_satisfaction_score',
            covariate_columns=[
                'age', 'annual_income', 'education_years', 'baseline_health_status',
                'social_support_score'
            ]
        )
        
        | estimate_propensity_scores(method='logistic', model_name='satisfaction_propensity')
        | estimate_treatment_effects(methods=['ate', 'doubly_robust'], analysis_name='satisfaction_effects')
        | print_causal_summary()
    )
    
    # Heterogeneity analysis (simplified)
    print(f"\n=== Treatment Effect Heterogeneity Analysis ===")
    
    # Split by age groups
    young_group = advanced_causal_data[advanced_causal_data['age'] <= 40]
    old_group = advanced_causal_data[advanced_causal_data['age'] > 60]
    
    for group_name, group_data in [('Young (≤40)', young_group), ('Old (>60)', old_group)]:
        if len(group_data) > 200:
            treated = group_data[group_data['wellness_program'] == 1]['health_improvement_score'].mean()
            control = group_data[group_data['wellness_program'] == 0]['health_improvement_score'].mean()
            naive_effect = treated - control
            
            print(f"{group_name} - Naive Health Effect: {naive_effect:.3f}")
    
    # Overall results comparison
    main_health_ate = advanced_analysis.treatment_effects['health_effects']['ate']['estimate']
    main_satisfaction_ate = satisfaction_analysis.treatment_effects['satisfaction_effects']['ate']['estimate']
    
    print(f"\n=== Multi-Outcome Causal Effects ===")
    print(f"Health Improvement ATE: {main_health_ate:.3f}")
    print(f"Life Satisfaction ATE: {main_satisfaction_ate:.3f}")
    
    # Save comprehensive analysis
    advanced_analysis = (
        advanced_analysis
        | save_causal_model(['all'], 'advanced_wellness_causal_model.joblib')
    )
    
    return {
        'health_analysis': advanced_analysis,
        'satisfaction_analysis': satisfaction_analysis
    }


# Example 6: Complete Pipeline with Save, Load, Add Features, and Inference
def example_complete_pipeline():
    """
    Demonstrates the complete causal inference pipeline including saving, loading,
    adding features, and performing inference.
    """
    print("=== Complete Pipeline Example ===")
    
    # Generate synthetic data for demonstration
    np.random.seed(42)
    n_samples = 1000
    
    # Generate features
    age = np.random.normal(35, 10, n_samples)
    income = np.random.lognormal(10, 0.5, n_samples)
    education = np.random.normal(14, 3, n_samples)
    health_score = np.random.normal(7, 2, n_samples)
    
    # Treatment assignment (confounded)
    treatment_prob = 1 / (1 + np.exp(-(-2 + 0.01*age + 0.00001*income + 0.1*education)))
    treatment = np.random.binomial(1, treatment_prob, n_samples)
    
    # Outcome (affected by treatment and confounders)
    outcome = (
        50 +  # Base outcome
        5 * treatment +  # True treatment effect
        0.1 * age +
        0.00001 * income +
        0.5 * education +
        0.3 * health_score +
        np.random.normal(0, 5, n_samples)
    )
    
    # Create DataFrame
    data = pd.DataFrame({
        'age': age,
        'income': income,
        'education': education,
        'health_score': health_score,
        'treatment': treatment,
        'outcome': outcome
    })
    
    print("1. Initial Data Preparation and Model Training")
    print("-" * 50)
    
    # Step 1: Initial pipeline with training
    initial_pipeline = (
        CausalPipe.from_dataframe(data)
        | prepare_causal_data(
            treatment_column='treatment',
            outcome_column='outcome',
            covariate_columns=['age', 'income', 'education', 'health_score']
        )
        | estimate_propensity_scores(
            method='logistic',
            model_name='initial_propensity'
        )
        | estimate_treatment_effects(
            methods=['ate', 'doubly_robust'],
            analysis_name='initial_effects'
        )
    )
    
    print("2. Save Trained Model")
    print("-" * 50)
    
    # Step 2: Save the trained model
    model_filename = 'complete_pipeline_model.joblib'
    saved_pipeline = initial_pipeline | save_causal_model(['all'], model_filename)
    print(f"Model saved to: {model_filename}")
    
    print("3. Load Model and Add New Features")
    print("-" * 50)
    
    # Step 3: Load the model and add new features
    # First, add new features to the data
    data['age_squared'] = data['age'] ** 2
    data['income_log'] = np.log(data['income'])
    data['education_income_interaction'] = data['education'] * data['income'] / 10000
    
    # Load the model with the updated data
    loaded_pipeline = (
        CausalPipe.from_dataframe(data)  # Start with data that includes new features
        | load_causal_model(model_filename, 'loaded_model')
    )
    
    # Add these new features to the pipeline
    feature_pipeline = (
        loaded_pipeline
        | add_features(
            feature_columns=['age_squared', 'income_log', 'education_income_interaction'],
            feature_type='covariate',
            feature_name='interaction_features'
        )
    )
    
    print("4. Re-estimate with New Features")
    print("-" * 50)
    
    # Step 4: Re-estimate with new features
    updated_pipeline = (
        feature_pipeline
        | prepare_causal_data(
            treatment_column='treatment',
            outcome_column='outcome',
            covariate_columns=[
                'age', 'income', 'education', 'health_score',
                'age_squared', 'income_log', 'education_income_interaction'
            ]
        )
        | estimate_propensity_scores(
            method='random_forest',
            model_params={'n_estimators': 100, 'random_state': 42},
            model_name='updated_propensity'
        )
        | estimate_treatment_effects(
            methods=['ate', 'att', 'doubly_robust'],
            analysis_name='updated_effects'
        )
    )
    
    print("5. Perform Inference on New Data")
    print("-" * 50)
    
    # Step 5: Generate new data for inference
    np.random.seed(123)
    n_new_samples = 500
    
    new_age = np.random.normal(40, 12, n_new_samples)
    new_income = np.random.lognormal(10.2, 0.6, n_new_samples)
    new_education = np.random.normal(15, 2.5, n_new_samples)
    new_health_score = np.random.normal(6.5, 2.5, n_new_samples)
    
    new_treatment_prob = 1 / (1 + np.exp(-(-1.5 + 0.02*new_age + 0.00001*new_income + 0.15*new_education)))
    new_treatment = np.random.binomial(1, new_treatment_prob, n_new_samples)
    
    new_outcome = (
        45 +  # Different base outcome
        6 * new_treatment +  # Slightly different treatment effect
        0.12 * new_age +
        0.00001 * new_income +
        0.6 * new_education +
        0.4 * new_health_score +
        np.random.normal(0, 6, n_new_samples)
    )
    
    new_data = pd.DataFrame({
        'age': new_age,
        'income': new_income,
        'education': new_education,
        'health_score': new_health_score,
        'treatment': new_treatment,
        'outcome': new_outcome,
        'age_squared': new_age ** 2,
        'income_log': np.log(new_income),
        'education_income_interaction': new_education * new_income / 10000
    })
    
    # Perform inference using the trained model
    inference_pipeline = (
        CausalPipe.from_dataframe(new_data)
        | load_causal_model(model_filename, 'inference_model')
        | inference(
            inference_type='treatment_effect',
            confidence_level=0.95,
            bootstrap_samples=500,
            inference_name='new_data_inference'
        )
    )
    
    print("6. Get Inference Results")
    print("-" * 50)
    
    # Get inference results
    inference_results = get_inference_results()(inference_pipeline)
    print("Inference Results Summary:")
    for analysis_name, results in inference_results.items():
        if isinstance(results, dict) and 'ate' in results:
            ate_estimate = results['ate']['estimate']
            print(f"  {analysis_name}: ATE = {ate_estimate:.3f}")
    
    print("7. Compare Original vs Updated Models")
    print("-" * 50)
    
    # Compare results
    original_ate = initial_pipeline.treatment_effects['initial_effects']['ate']['estimate']
    updated_ate = updated_pipeline.treatment_effects['updated_effects']['ate']['estimate']
    
    print(f"Original Model ATE: {original_ate:.3f}")
    print(f"Updated Model ATE: {updated_ate:.3f}")
    print(f"Difference: {abs(updated_ate - original_ate):.3f}")
    
    # Clean up
    if os.path.exists(model_filename):
        os.remove(model_filename)
        print(f"Cleaned up: {model_filename}")
    
    return {
        'initial_pipeline': initial_pipeline,
        'updated_pipeline': updated_pipeline,
        'inference_pipeline': inference_pipeline,
        'inference_results': inference_results
    }


if __name__ == "__main__":
    print("Running Causal Inference Pipeline Examples...")
    
    print("\n" + "="*70)
    print("Example 1: A/B Testing for Website Feature")
    print("="*70)
    ab_test_model = example_ab_test_website_feature()
    
    print("\n" + "="*70)
    print("Example 2: Observational Study - Education and Income")
    print("="*70)
    education_model = example_observational_study_education()
    
    print("\n" + "="*70)
    print("Example 3: Marketing Campaign Effectiveness")
    print("="*70)
    marketing_results = example_marketing_campaign_analysis()
    marketing_model = marketing_results['original_analysis']  # Use original for summary
    
    print("\n" + "="*70)
    print("Example 4: Policy Intervention Evaluation - Job Training")
    print("="*70)
    policy_model = example_policy_intervention_evaluation()
    
    print("\n" + "="*70)
    print("Example 5: Advanced Causal Analysis with Heterogeneous Effects")
    print("="*70)
    advanced_models = example_advanced_causal_analysis()
    
    print("\n" + "="*70)
    print("Example 6: Complete Pipeline with Save, Load, Add Features, and Inference")
    print("="*70)
    complete_pipeline_results = example_complete_pipeline()
    
    print("\n" + "="*70)
    print("CAUSAL INFERENCE SUMMARY")
    print("="*70)
    
    examples = [
        ('A/B Test Analysis', ab_test_model),
        ('Education Study', education_model),
        ('Marketing Campaign', marketing_model),
        ('Policy Evaluation', policy_model),
        ('Advanced Analysis', advanced_models['health_analysis']),
        ('Complete Pipeline', complete_pipeline_results['initial_pipeline'])
    ]
    
    for name, model in examples:
        n_obs = len(model.data) if model.data is not None else 0
        n_treated = model.data[model.treatment_column].sum() if model.data is not None and model.treatment_column else 0
        n_control = n_obs - n_treated
        
        print(f"\n{name}:")
        print(f"  Total Observations: {n_obs:,}")
        print(f"  Treated: {n_treated:,}, Control: {n_control:,}")
        
        if model.treatment_effects:
            first_analysis = list(model.treatment_effects.keys())[0]
            if 'ate' in model.treatment_effects[first_analysis]:
                ate = model.treatment_effects[first_analysis]['ate']['estimate']
                print(f"  Average Treatment Effect: {ate:.4f}")
        
        if model.ab_test_results:
            first_test = list(model.ab_test_results.keys())[0]
            p_value = model.ab_test_results[first_test]['p_value']
            significant = model.ab_test_results[first_test]['significant']
            print(f"  Statistical Significance: p={p_value:.4f}, Significant: {significant}")
    
    print("\nAll causal inference examples completed successfully!")
    print("\nKey Insights:")
    print("- A/B testing provides the gold standard for causal inference")
    print("- Observational studies require careful handling of selection bias")
    print("- Propensity score methods help reduce confounding")
    print("- Multiple methods should be used for robustness")
    print("- Sensitivity analysis tests robustness to unmeasured confounding")