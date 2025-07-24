
## Examples Overview

The five examples demonstrate different causal inference scenarios:

### 1. A/B Testing (Gold Standard)
- **Scenario**: Website checkout flow experiment
- **Key Feature**: Random assignment eliminates confounding
- **Analysis**: Simple comparison of treatment vs. control groups
- **Why it works**: Randomization ensures groups are comparable

### 2. Observational Study (Education & Income)
- **Scenario**: College education effect on income
- **Challenge**: Selection bias (family background affects both education choice and income)
- **Solution**: Propensity score matching to find comparable individuals
- **Key insight**: Naive comparison overestimates education's effect due to confounding

### 3. Marketing Campaign Analysis
- **Scenario**: Targeted marketing campaign effectiveness
- **Challenge**: Non-random targeting (high-value customers selected)
- **Solution**: Multiple methods (IPW, matching, doubly robust)
- **Key insight**: Shows how targeting bias inflates naive estimates

### 4. Policy Evaluation (Job Training)
- **Scenario**: Employment program effectiveness
- **Challenge**: Self-selection (motivated people more likely to participate)
- **Solution**: Comprehensive matching and robustness checks
- **Key insight**: Demonstrates cost-benefit analysis using causal estimates

### 5. Advanced Analysis (Wellness Program)
- **Scenario**: Multiple outcomes and heterogeneous effects
- **Challenge**: Complex selection and varying treatment effects
- **Solution**: Sophisticated modeling with sensitivity analysis

## Propensity Scores Explained

**Definition**: The probability of receiving treatment given observed characteristics.

**Purpose**: 
- Creates a single "balancing score" from multiple covariates
- Allows matching/weighting individuals with similar treatment probabilities
- Reduces dimensionality problem in matching

**How it works**:
1. **Estimate**: Model treatment assignment as function of covariates
2. **Apply**: Use scores for matching, weighting, or stratification
3. **Balance**: Ensures treated/control groups are comparable on observables

**Key Assumption**: All confounders are observed and included in the propensity model.

## Covariate Analysis & Selection

### Why Number of Covariates Matters

**The Bias-Variance Trade-off**:

**Too Few Covariates**:
- **Risk**: Omitted variable bias
- **Problem**: Miss important confounders
- **Result**: Biased treatment effect estimates
- **Example**: Estimating education effects without including family income

**Too Many Covariates**:
- **Risk**: Overfitting and poor matches
- **Problem**: Curse of dimensionality
- **Result**: Few good matches, increased variance
- **Example**: Including hundreds of irrelevant variables

**Optimal Balance**:
- Include all true confounders
- Exclude irrelevant variables
- Consider sample size limitations

### How to Decide Which Covariates to Include

#### 1. **Domain Knowledge (Most Important)**
- **Confounders**: Variables that affect both treatment assignment AND outcome
- **Examples**:
  - Education study: Family income, parent education, ability
  - Marketing: Customer value, purchase history, engagement
  - Job training: Demographics, skills, employment history

#### 2. **Causal Reasoning**
Ask three questions for each potential covariate:
- Does it influence treatment assignment?
- Does it influence the outcome?
- Is it a confounder (affects both)?

**Include**: True confounders
**Exclude**: 
- Pure predictors of treatment only
- Pure predictors of outcome only (unless improving precision)
- Colliders (caused by both treatment and outcome)

#### 3. **Statistical Considerations**

**Sample Size Rules**:
- **Small samples** (n < 500): Be very selective, focus on strongest confounders
- **Medium samples** (500-5000): Include moderate confounders
- **Large samples** (n > 5000): Can include weaker confounders

**Balance Assessment**:
- Check if adding covariates improves balance
- Remove variables that don't improve matching quality
- Monitor standardized mean differences

#### 4. **Practical Guidelines**

**Start Conservative**:
- Begin with 3-5 strongest confounders
- Add variables incrementally
- Check balance at each step

**Prioritize by Strength**:
1. **Strong confounders**: Large effects on both treatment and outcome
2. **Moderate confounders**: Medium effects
3. **Weak confounders**: Small effects (include only with large samples)

**Variable Types**:
- **Demographics**: Age, gender, location (usually important)
- **Behavioral**: Past behavior, preferences (often strong predictors)
- **Contextual**: Time, environment, external factors
- **Instrumental**: Variables affecting treatment but not outcome directly

### Quality vs. Quantity Trade-offs

#### **Matching Quality**
- More covariates = harder to find good matches
- Check overlap in propensity score distributions
- Monitor match quality metrics

#### **Sample Size Preservation**
- Too many covariates can eliminate too many observations
- Balance between bias reduction and sample retention
- Consider stratification instead of exact matching

#### **Computational Considerations**
- More covariates = longer computation time
- Some methods (like exact matching) become infeasible
- Consider variable reduction techniques

### Red Flags in Covariate Selection

**Avoid These**:
- **Post-treatment variables**: Measured after treatment assignment
- **Colliders**: Variables caused by both treatment and outcome
- **Perfect predictors**: Variables that perfectly predict treatment
- **Highly correlated sets**: Include only one from correlated groups

### Example Decision Process

**Marketing Campaign Example**:

**Definite Include** (Strong confounders):
- Customer income (affects targeting and purchase ability)
- Purchase history (affects targeting and future purchases)
- Engagement score (affects targeting and likelihood to convert)

**Probably Include** (Moderate confounders):
- Demographics (age, location)
- Account tenure
- Channel preferences

**Maybe Include** (Weak/uncertain):
- Website behavior details
- Email preferences
- Social media activity

**Definitely Exclude**:
- Post-campaign behaviors
- Variables with missing data for most observations
- Highly specific variables with little predictive power

### Validation Approach

**Iterative Process**:
1. Start with core confounders
2. Check balance and overlap
3. Add variables if they improve balance
4. Remove if they worsen matching quality
5. Test sensitivity to covariate choices
6. Compare results across different covariate sets

The goal is finding the **minimum set of covariates** that adequately controls for confounding while maintaining good matching quality and sufficient sample size. This requires both domain expertise and empirical validation through balance tests and sensitivity analysis.


## How to Read Covariate Balance Results

### **Before Matching (health_original_balance)**
```
Balanced variables: 0/6
Unbalanced: age, annual_income, education_years, baseline_health_status, rural_location, social_support_score
```

**What this means:**
- **0/6**: None of the covariates are balanced between treatment and control groups
- **Unbalanced variables**: All 6 covariates show significant differences between treated and control groups
- **Interpretation**: Strong evidence of selection bias - people who joined the wellness program are systematically different from those who didn't

### **After Matching (health_nn_balance)**
```
Balanced variables: 4/6
Unbalanced: annual_income, social_support_score
```

**What this means:**
- **4/6**: Matching successfully balanced 4 out of 6 covariates
- **Still unbalanced**: annual_income and social_support_score remain significantly different between groups
- **Interpretation**: Matching improved balance substantially but didn't eliminate all differences

## Understanding Balance Quality

### **Standardized Mean Difference (SMD) Thresholds**
- **SMD < 0.1**: Well balanced (good)
- **0.1 ≤ SMD < 0.2**: Moderately unbalanced (concerning)
- **SMD ≥ 0.2**: Severely unbalanced (problematic)

### **Why Some Variables Remain Unbalanced**

1. **Insufficient overlap**: Treatment and control groups have very different distributions
2. **Sample size limitations**: Not enough observations to find good matches
3. **Matching method limitations**: Nearest neighbor may not be optimal for these variables
4. **Strong selection effects**: These variables were key drivers of treatment assignment

## How to Improve Balance

### **1. Adjust Matching Parameters**

**Tighten the caliper:**
```python
| apply_matching(
    method='nearest_neighbor',
    n_neighbors=1,
    caliper=0.05,  # Stricter matching (was 0.15)
    matching_name='tighter_matched'
)
```

**Use more neighbors:**
```python
| apply_matching(
    method='nearest_neighbor',
    n_neighbors=3,  # More neighbors for better balance
    caliper=0.1,
    matching_name='multi_neighbor_matched'
)
```

### **2. Try Different Matching Methods**

**Stratified matching:**
```python
| apply_matching(
    method='stratified',  # Often better for continuous variables
    matching_name='stratified_matched'
)
```

**Optimal matching (if available):**
- Finds globally optimal matches
- Better balance but computationally expensive

### **3. Refine Propensity Score Model**

**Add interaction terms:**
```python
# Include interactions between problematic variables
covariate_columns=[
    'age', 'annual_income', 'education_years', 
    'baseline_health_status', 'rural_location', 
    'social_support_score',
    'income_x_education',  # Interaction term
    'age_x_health_status'  # Interaction term
]
```

**Use more flexible models:**
```python
| estimate_propensity_scores(
    method='random_forest',  # More flexible than logistic
    model_params={
        'n_estimators': 200,
        'max_depth': 10,
        'min_samples_split': 20
    }
)
```

### **4. Exclude Problematic Observations**

**Remove extreme values:**
- Exclude observations in non-overlapping regions
- Focus on area of common support

**Trimming approach:**
```python
# Remove observations with extreme propensity scores
df_trimmed = df[(df['propensity_score'] >= 0.1) & 
                (df['propensity_score'] <= 0.9)]
```

### **5. Use Alternative Methods**

**Inverse Probability Weighting (IPW):**
- Can handle imbalance better than matching
- Uses all observations with appropriate weights

**Doubly Robust Methods:**
- Combine propensity scores with outcome modeling
- More robust to remaining imbalance

### **6. Subgroup Analysis**

**Restrict to balanced subgroups:**
```python
# Focus on observations where balance is achievable
balanced_subset = df[
    (df['annual_income'] >= income_threshold_low) & 
    (df['annual_income'] <= income_threshold_high)
]
```

## When is Imperfect Balance Acceptable?

### **Severity Assessment**

**Low Concern (Probably OK):**
- SMD < 0.15 for remaining unbalanced variables
- Unbalanced variables are weak confounders
- Multiple methods give similar results
- Sensitivity analysis shows robust results

**High Concern (Needs Action):**
- SMD > 0.2 for remaining unbalanced variables
- Unbalanced variables are strong confounders
- Large differences in baseline outcomes
- Results are sensitive to these imbalances

### **Contextual Factors**

**Sample Size:**
- Large samples: Can afford to be more selective
- Small samples: May need to accept some imbalance

**Variable Importance:**
- Critical confounders must be balanced
- Less important variables can remain somewhat unbalanced

**Study Design:**
- Exploratory analysis: More tolerance for imbalance
- Policy evaluation: Higher standards for balance

## Practical Action Plan for Your Results

### **Immediate Steps:**

1. **Check SMD values** for annual_income and social_support_score
   - If SMD < 0.15: Probably acceptable
   - If SMD > 0.2: Needs improvement

2. **Try stratified matching:**
   ```python
   | apply_matching(
       method='stratified',
       matching_name='stratified_alternative'
   )
   ```

3. **Use doubly robust estimation:**
   ```python
   | estimate_treatment_effects(
       methods=['doubly_robust'],  # More robust to imbalance
       outcome_model='random_forest'
   )
   ```

### **If Problems Persist:**

1. **Examine overlap:**
   - Plot propensity score distributions
   - Identify non-overlapping regions
   - Consider excluding extreme cases

2. **Variable transformation:**
   - Log-transform annual_income (often right-skewed)
   - Standardize social_support_score

3. **Sensitivity analysis:**
   - Test how sensitive results are to remaining imbalance
   - Use multiple matching methods
   - Compare with IPW results

### **Reporting Standards**

**Good Practice:**
- Report balance for all methods tried
- Show SMD values, not just binary balanced/unbalanced
- Discuss limitations of remaining imbalance
- Use sensitivity analysis to test robustness

**Red Flags to Avoid:**
- Ignoring substantial remaining imbalance
- Cherry-picking the method that gives desired results
- Not testing sensitivity to covariate balance

The key principle is that **perfect balance is the goal, but substantial improvement with remaining minor imbalances may be acceptable** if you can demonstrate robustness through sensitivity analysis and multiple methods.


## How to Determine Covariate Columns from a Dataset

### **Step 1: Systematic Covariate Identification**

#### **Domain Knowledge Approach**
Start by asking these questions for each variable in your dataset:

**Confounder Identification Questions:**
1. **Treatment Assignment**: Does this variable influence who gets treated?
2. **Outcome Influence**: Does this variable directly affect the outcome?
3. **Temporal Order**: Was this measured before treatment assignment?
4. **Causal Pathway**: Is this variable on the causal path between treatment and outcome?

#### **Variable Classification Process**

**Include as Covariates (Confounders):**
- Demographics that affect both treatment selection and outcome
- Pre-treatment behaviors/characteristics
- Socioeconomic factors
- Geographic/contextual variables
- Baseline measures of the outcome

**Exclude:**
- Post-treatment variables
- Variables caused by both treatment and outcome (colliders)
- Perfect predictors of treatment
- Variables with excessive missing data
- Purely random identifiers

### **Step 2: Interaction Terms - When and Why**

#### **Why Include Interactions?**

**Problem with Main Effects Only:**
- Assumes each covariate affects treatment/outcome independently
- Real world: Variables often interact with each other
- **Example**: Income effect on treatment may depend on education level

**When Interactions Matter:**
1. **Multiplicative Effects**: High income + high education = disproportionately higher treatment probability
2. **Threshold Effects**: Education only matters above certain income level
3. **Substitution Effects**: Variables can compensate for each other

#### **How to Identify Important Interactions**

**Theoretical Reasoning:**
- **income_x_education**: Wealthy, educated people may have very different treatment-seeking behavior
- **age_x_health_status**: Health problems may matter more for older people
- **rural_location_x_income**: Income effects may differ by geography

**Empirical Clues:**
- Variables with high correlation might interact
- Variables that cluster together in treatment assignment
- Domain research suggesting interactive effects

### **Step 3: Systematic Interaction Selection**

#### **High-Priority Interactions**

**Socioeconomic Interactions:**
- income × education
- income × location (urban/rural)
- education × age

**Health-Related Interactions:**
- age × baseline_health_status
- health_status × social_support
- rural_location × access_to_care

**Behavioral Interactions:**
- motivation × social_support
- previous_experience × education
- risk_tolerance × income

#### **Selection Criteria**

**Include Interactions When:**
1. **Strong theoretical justification** exists
2. **Variables are moderately correlated** (0.3-0.7)
3. **Both variables are strong predictors** of treatment
4. **Sample size is sufficient** (rule of thumb: 10-15 observations per parameter)
5. **Improves propensity model fit** significantly

**Avoid Interactions When:**
- Variables are uncorrelated (< 0.2)
- Sample size is small
- Creates perfect separation in propensity model
- Variables are already highly correlated (> 0.8)

### **Step 4: Practical Implementation Process**

#### **Data Exploration Phase**

**Examine Treatment Assignment Patterns:**
- Cross-tabulate categorical variables with treatment
- Plot continuous variables by treatment group
- Look for non-linear relationships
- Identify variables that cluster together

**Example Analysis:**
- Do high-income, high-education people have very different treatment rates?
- Are older people with poor health treated differently than younger people with poor health?
- Does the effect of social support depend on rural vs. urban location?

#### **Interaction Term Creation**

**Continuous × Continuous:**
- income_x_education = annual_income × education_years
- Often center variables first: (income - mean_income) × (education - mean_education)

**Continuous × Binary:**
- age_x_rural = age × rural_location (0 or 1)
- Gives age effect specifically for rural residents

**Binary × Binary:**
- rural_x_male = rural_location × gender_male
- Creates four categories: urban_female, urban_male, rural_female, rural_male

### **Step 5: Validation and Refinement**

#### **Model Performance Checks**

**Propensity Model Fit:**
- Does including interactions improve AUC/R-squared?
- Check for overfitting with cross-validation
- Ensure model converges and is stable

**Balance Improvement:**
- Do interactions help balance previously unbalanced variables?
- Check if overall balance improves
- Monitor for creation of new imbalances

#### **Sample Size Considerations**

**Parameter Count Rules:**
- Main effects: 6 variables
- Two-way interactions: Potentially 15 more terms (6 choose 2)
- Rule of thumb: 10-15 observations per parameter
- For 21 parameters, need ~300+ observations

**Prioritization Strategy:**
1. Start with most theoretically important interactions
2. Add interactions that improve balance most
3. Stop when sample size becomes limiting factor

### **Step 6: Common Patterns by Domain**

#### **Healthcare/Wellness Studies**
**Typical Interactions:**
- age × baseline_health_status
- income × insurance_status
- education × health_literacy
- rural_location × access_measures

#### **Education Studies**
**Typical Interactions:**
- family_income × parent_education
- ability × motivation
- school_quality × family_support
- age × previous_experience

#### **Marketing/Business**
**Typical Interactions:**
- income × product_category
- age × digital_savviness
- location × channel_preference
- loyalty_status × promotion_sensitivity

### **Decision Framework Example**

**For Wellness Program Dataset:**

**Definite Interactions to Test:**
1. **income_x_education**: Wealthy, educated people may be most likely to join
2. **age_x_health_status**: Health problems more motivating for older adults
3. **rural_x_income**: Income effects may differ by location access

**Possible Interactions:**
4. **education_x_social_support**: Educated people may leverage social networks differently
5. **age_x_rural**: Older rural residents may have different access patterns

**Probably Skip:**
- **health_status_x_social_support**: Less clear theoretical justification
- **education_x_rural**: Weaker expected interaction

### **Red Flags to Avoid**

**Don't Include Interactions That:**
- Create perfect prediction of treatment
- Result in very small cell sizes
- Are purely data-driven without theory
- Make the model unstable or non-convergent
- Create multicollinearity problems

### **Validation Approach**

**Before Finalizing:**
1. **Test multiple interaction sets** and compare balance results
2. **Use cross-validation** to avoid overfitting
3. **Check robustness** across different matching methods
4. **Compare treatment effects** with and without interactions
5. **Ensure clinical/business interpretability** of results

The key is balancing **theoretical justification**, **empirical evidence**, and **practical constraints** (sample size, model stability) when selecting both main effect covariates and their interactions.



# Evaluating Quality of Causal Inference

## **1. Internal Validity Assessment**

### **Confounding Control Quality**

#### **Covariate Balance Evaluation**
```
=== Balance Quality Metrics ===

Excellent (SMD < 0.05):
✓ All important confounders balanced
✓ Overlap region covers 80%+ of sample
✓ No systematic differences remain

Good (SMD < 0.1): 
✓ Most confounders balanced
✓ Minor imbalances in less critical variables
✓ Overlap covers 60-80% of sample

Concerning (SMD 0.1-0.2):
⚠ Some important confounders remain unbalanced
⚠ Moderate selection bias likely persists
⚠ Results need sensitivity analysis

Poor (SMD > 0.2):
✗ Major confounders severely unbalanced
✗ Strong selection bias remains
✗ Causal conclusions unreliable
```

#### **Propensity Score Quality**
- **AUC Score**: 0.5-0.6 (good overlap), 0.7-0.8 (moderate), >0.9 (concerning lack of overlap)
- **Distribution Overlap**: Substantial overlap between treated/control propensity distributions
- **Common Support**: Sufficient observations in overlap region

### **Selection Bias Diagnostics**

#### **Before vs. After Comparison**
```
Example Quality Assessment:

BEFORE Matching:
- Balanced variables: 0/8 covariates
- Average |SMD|: 0.45 (severe imbalance)
- Overlap: 40% of sample in common support

AFTER Matching: 
- Balanced variables: 6/8 covariates  
- Average |SMD|: 0.08 (good balance)
- Overlap: 75% of sample matched
- Quality Score: Good ✓
```

#### **Residual Confounding Tests**
- Check if known non-confounders are balanced (falsification test)
- Examine time trends before treatment
- Test for balance on outcome predictors not used in matching

## **2. Statistical Validity**

### **Power and Precision Analysis**

#### **Effect Size Precision**
```
Treatment Effect Quality Assessment:

High Precision:
✓ Narrow confidence intervals (width < 0.5 × effect size)
✓ Statistical power > 80%
✓ Adequate sample size after matching

Moderate Precision:
~ Reasonable confidence intervals 
~ Power 60-80%
~ Some precision lost in matching

Low Precision:
✗ Very wide confidence intervals
✗ Power < 60%
✗ Small effective sample size
```

#### **Multiple Testing Considerations**
- Correct for multiple outcomes/subgroups
- Pre-specify primary vs. secondary analyses
- Report both corrected and uncorrected p-values

### **Significance vs. Practical Significance**

#### **Effect Size Interpretation**
```
Practical Significance Framework:

Cohen's Guidelines (Continuous Outcomes):
- Small effect: d = 0.2
- Medium effect: d = 0.5  
- Large effect: d = 0.8

Business/Policy Context:
- Cost-benefit ratio
- Number needed to treat
- Population-level impact
```

## **3. Robustness Assessment**

### **Method Triangulation**

#### **Cross-Method Validation**
```
Robustness Quality Matrix:

Excellent Robustness:
✓ All methods (matching, IPW, doubly robust) agree within 10%
✓ Different matching algorithms give similar results
✓ Various covariate specifications consistent

Good Robustness:
✓ Most methods agree within 20%  
✓ Direction and significance consistent
✓ Minor variations in magnitude

Poor Robustness:
✗ Methods disagree substantially (>30%)
✗ Different directions or significance
✗ High sensitivity to specification choices
```

#### **Sensitivity Analysis Quality**
- **Hidden Confounding**: How strong would unmeasured confounder need to be?
- **Specification Sensitivity**: Results stable across different model choices?
- **Sample Sensitivity**: Results hold in different subsamples?

### **Assumption Testing**

#### **Key Assumptions Checklist**
```
Assumption Quality Assessment:

1. Unconfoundedness (No unmeasured confounding):
   □ All major confounders identified theoretically
   □ Falsification tests pass
   □ Sensitivity analysis shows robustness
   □ Quality: High/Medium/Low

2. Overlap/Common Support:
   □ Substantial propensity score overlap
   □ No perfect predictors of treatment
   □ Adequate sample in overlap region  
   □ Quality: High/Medium/Low

3. Stable Unit Treatment Value (SUTVA):
   □ No spillover effects between units
   □ Treatment definition consistent
   □ No interference patterns
   □ Quality: High/Medium/Low
```

## **4. External Validity**

### **Generalizability Assessment**

#### **Population Representativeness**
- **Target Population**: Who do results apply to?
- **Sample Selection**: How representative is the analyzed sample?
- **Matching Impact**: What population do matched results represent?

#### **Setting and Context**
- **Geographic Generalizability**: Results hold across locations?
- **Temporal Generalizability**: Effects stable over time?
- **Implementation Generalizability**: Results hold with different implementation?

### **Effect Heterogeneity**

#### **Subgroup Analysis Quality**
```
Heterogeneity Assessment:

Well-Powered Subgroups:
✓ Pre-specified subgroups based on theory
✓ Adequate power in each subgroup (n>100)
✓ Consistent patterns across related subgroups

Exploratory Subgroups:
~ Interesting patterns but underpowered
~ Multiple testing concerns
~ Hypothesis-generating rather than confirmatory

Poor Subgroup Analysis:
✗ Post-hoc data mining
✗ Very small subgroups (n<50)
✗ Inconsistent or implausible patterns
```

## **5. Practical Validity**

### **Effect Size Meaningfulness**

#### **Clinical/Business Significance**
```
Practical Impact Assessment:

Healthcare Example:
- Statistical: p<0.001, effect = 0.3 units
- Clinical: Reduces hospital stays by 0.5 days
- Economic: Saves $1,200 per patient
- Quality Rating: High practical significance

Marketing Example:
- Statistical: p=0.02, effect = 1.2% conversion increase  
- Business: +12 conversions per 1,000 customers
- Economic: +$50,000 annual revenue
- Quality Rating: Moderate practical significance
```

#### **Cost-Benefit Analysis**
- **Implementation Costs**: What does the intervention cost?
- **Benefit Magnitude**: How large are the benefits?
- **Break-even Analysis**: When does intervention pay for itself?

### **Actionability Assessment**

#### **Decision-Making Quality**
- **Clear Recommendations**: Results lead to clear actions?
- **Risk Assessment**: Downside risks identified and quantified?
- **Implementation Feasibility**: Can the intervention be realistically implemented?

## **6. Comprehensive Quality Framework**

### **Overall Quality Scoring System**

#### **Dimension Weights**
```
Quality Assessment Framework:

Internal Validity (40%):
- Confounding control: ___/25 points
- Selection bias reduction: ___/15 points

Statistical Validity (25%):
- Power and precision: ___/15 points  
- Multiple testing: ___/10 points

Robustness (20%):
- Method triangulation: ___/10 points
- Sensitivity analysis: ___/10 points

External Validity (10%):
- Generalizability: ___/10 points

Practical Validity (5%):
- Effect meaningfulness: ___/5 points

Total Quality Score: ___/100 points
```

#### **Quality Categories**
```
Overall Assessment:

Excellent (85-100 points):
✓ Strong causal evidence
✓ High confidence in results  
✓ Ready for policy/business decisions
✓ Suitable for high-stakes applications

Good (70-84 points):
✓ Solid causal evidence
✓ Reasonable confidence
✓ Suitable for most applications
✓ Minor limitations acknowledged

Fair (55-69 points):
~ Suggestive evidence
~ Moderate confidence
~ Useful for hypothesis generation
~ Significant limitations present

Poor (<55 points):
✗ Weak causal evidence
✗ Low confidence in results
✗ Not suitable for decision-making
✗ Major methodological problems
```

## **7. Red Flags and Warning Signs**

### **Major Quality Issues**

#### **Fatal Flaws**
```
Immediate Disqualifiers:

1. No Overlap:
   ✗ Treated and control groups completely separate
   ✗ No common support region
   ✗ Perfect prediction of treatment

2. Severe Imbalance:
   ✗ Major confounders with SMD > 0.5
   ✗ Balance actually worsens after matching
   ✗ Large baseline outcome differences

3. Specification Sensitivity:
   ✗ Results flip sign with minor changes
   ✗ Estimates vary by >100% across methods
   ✗ Statistical significance highly unstable

4. Assumption Violations:
   ✗ Clear evidence of unmeasured confounding
   ✗ Spillover effects present
   ✗ Treatment definition inconsistent
```

### **Warning Signs**

#### **Proceed with Caution**
- Effect size exactly matches researcher expectations
- Only one method reported without comparison
- Sensitivity analysis omitted or limited  
- Subgroup analyses not pre-specified
- No discussion of limitations

## **8. Quality Reporting Standards**

### **Essential Reporting Elements**

#### **Transparency Checklist**
```
Required Reporting Elements:

□ CONSORT/STROBE compliance for study design
□ Complete covariate balance tables (before/after)
□ Propensity score distribution plots
□ Multiple estimation methods compared
□ Sensitivity analysis results
□ Effect sizes with confidence intervals
□ Limitations and assumptions discussed
□ Code and data availability statement
```

#### **Reproducibility Standards**
- Analysis code made available
- Random seeds specified
- Software versions documented
- Data processing steps detailed

## **Quality Assessment in Practice**

### **Example Quality Evaluation**

```
Study: Wellness Program Impact Analysis

Internal Validity: 22/25 points
- Excellent balance achieved (6/6 covariates balanced)
- Strong overlap (85% of sample in common support)
- Minor: Income still slightly unbalanced (SMD=0.09)

Statistical Validity: 18/25 points  
- Good power (85%) and precision
- Appropriate significance testing
- Minor: No multiple testing correction applied

Robustness: 16/20 points
- Three methods agree closely (ATE: 0.42-0.48)
- Sensitivity analysis shows robustness to moderate confounding
- Minor: Only tested linear outcome models

External Validity: 7/10 points
- Reasonably representative sample
- Limited geographic diversity
- Temporal generalizability unclear

Practical Validity: 4/5 points
- Effect size practically meaningful
- Clear business case established

Overall Quality: 67/85 = 79% (Good Quality)

Recommendation: Results provide solid evidence for causal effect. 
Suitable for business decision-making with noted limitations.
```

The key principle is that **high-quality causal inference requires excellence across multiple dimensions**, not just statistical significance. A comprehensive evaluation considers the entire inferential chain from design through interpretation.