-- =====================================================
-- Workday Employee Skills Development Table
-- =====================================================
-- This table tracks employee skill development outcomes
-- linked to training programs without foreign key constraints
-- =====================================================

CREATE TABLE workday_employee_skills_development (
    -- Primary identifier
    id                          SERIAL PRIMARY KEY,
    
    -- Employee information
    employee_id                 VARCHAR(50) NOT NULL,
    employee_name               VARCHAR(255) NOT NULL,
    manager_id                  VARCHAR(50),
    manager_name                VARCHAR(255),
    division                    VARCHAR(100) NOT NULL,
    job_title                   VARCHAR(255) NOT NULL,
    job_level                   VARCHAR(50) NOT NULL,
    hire_date                   DATE NOT NULL,
    
    -- Skill information
    skill_name                  VARCHAR(255) NOT NULL,
    skill_category              VARCHAR(50) NOT NULL CHECK (skill_category IN ('Technical', 'Leadership', 'Compliance', 'Soft Skills', 'Digital')),
    competency_framework        VARCHAR(255),
    skill_criticality           VARCHAR(20) NOT NULL CHECK (skill_criticality IN ('Critical', 'Important', 'Beneficial')),
    
    -- Proficiency tracking
    pre_training_proficiency    INTEGER NOT NULL CHECK (pre_training_proficiency >= 1 AND pre_training_proficiency <= 5),
    post_training_proficiency   INTEGER NOT NULL CHECK (post_training_proficiency >= 1 AND post_training_proficiency <= 5),
    target_proficiency          INTEGER NOT NULL CHECK (target_proficiency >= 1 AND target_proficiency <= 5),
    
    -- Training program linkage
    training_curriculum_id      VARCHAR(100),
    training_curriculum_title   TEXT NOT NULL,
    
    -- Assessment information
    skill_assessment_date       DATE NOT NULL,
    assessment_method           VARCHAR(50) NOT NULL CHECK (assessment_method IN ('Self-Assessment', 'Manager Review', 'Certification', 'Practical Test', 'Peer Review')),
    
    -- Certification tracking
    certification_earned        VARCHAR(255),
    certification_expiry_date   DATE,
    
    -- Financial information
    cost_center                 VARCHAR(50),
    training_cost               DECIMAL(10,2) NOT NULL CHECK (training_cost >= 0),
    
    -- Performance and development
    performance_rating          DECIMAL(3,1) CHECK (performance_rating >= 1.0 AND performance_rating <= 5.0),
    career_development_plan     VARCHAR(100),
    succession_plan_role        VARCHAR(255),
    
    -- Audit fields
    created_at                  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Calculated fields (computed columns)
    proficiency_improvement     INTEGER GENERATED ALWAYS AS (post_training_proficiency - pre_training_proficiency) STORED,
    target_gap                  INTEGER GENERATED ALWAYS AS (target_proficiency - post_training_proficiency) STORED,
    is_skill_proficient         BOOLEAN GENERATED ALWAYS AS (post_training_proficiency >= target_proficiency) STORED,
    tenure_months               INTEGER,
    roi_indicator               DECIMAL(10,2)
);

-- =====================================================
-- Indexes for Performance
-- =====================================================

-- Primary lookup indexes
CREATE INDEX idx_workday_employee_id ON workday_employee_skills_development(employee_id);
CREATE INDEX idx_workday_division ON workday_employee_skills_development(division);
CREATE INDEX idx_workday_skill_category ON workday_employee_skills_development(skill_category);
CREATE INDEX idx_workday_curriculum_title ON workday_employee_skills_development(training_curriculum_title);

-- Performance analysis indexes
CREATE INDEX idx_workday_skill_criticality ON workday_employee_skills_development(skill_criticality);
CREATE INDEX idx_workday_assessment_date ON workday_employee_skills_development(skill_assessment_date);
CREATE INDEX idx_workday_manager_name ON workday_employee_skills_development(manager_name);

-- Composite indexes for common queries
CREATE INDEX idx_workday_employee_skill ON workday_employee_skills_development(employee_id, skill_name);
CREATE INDEX idx_workday_division_category ON workday_employee_skills_development(division, skill_category);
CREATE INDEX idx_workday_proficiency_gap ON workday_employee_skills_development(target_gap) WHERE target_gap > 0;
CREATE INDEX idx_workday_critical_gaps ON workday_employee_skills_development(skill_criticality, target_gap) WHERE skill_criticality = 'Critical' AND target_gap > 0;

-- Certification tracking
CREATE INDEX idx_workday_certifications ON workday_employee_skills_development(certification_earned) WHERE certification_earned IS NOT NULL AND certification_earned != '';
CREATE INDEX idx_workday_cert_expiry ON workday_employee_skills_development(certification_expiry_date) WHERE certification_expiry_date IS NOT NULL;

-- =====================================================
-- Constraints and Business Rules
-- =====================================================

-- Ensure assessment date is after hire date
ALTER TABLE workday_employee_skills_development 
ADD CONSTRAINT chk_assessment_after_hire 
CHECK (skill_assessment_date >= hire_date);

-- Ensure certification expiry is after assessment (if certification exists)
ALTER TABLE workday_employee_skills_development 
ADD CONSTRAINT chk_cert_expiry_logic 
CHECK (
    (certification_earned IS NULL OR certification_earned = '') 
    OR 
    (certification_expiry_date IS NOT NULL AND certification_expiry_date > skill_assessment_date)
);

-- Ensure logical proficiency progression
ALTER TABLE workday_employee_skills_development 
ADD CONSTRAINT chk_proficiency_logic 
CHECK (post_training_proficiency >= pre_training_proficiency OR post_training_proficiency = pre_training_proficiency);

-- =====================================================
-- Table Comments
-- =====================================================

COMMENT ON TABLE workday_employee_skills_development IS 'Employee skills development tracking and competency assessment data from Workday HCM system';

-- Column comments
COMMENT ON COLUMN workday_employee_skills_development.employee_id IS 'Unique employee identifier matching CSOD user_id for cross-system analysis';
COMMENT ON COLUMN workday_employee_skills_development.skill_category IS 'Category of skill: Technical, Leadership, Compliance, Soft Skills, Digital';
COMMENT ON COLUMN workday_employee_skills_development.skill_criticality IS 'Business criticality: Critical (essential for role), Important (valuable), Beneficial (nice to have)';
COMMENT ON COLUMN workday_employee_skills_development.pre_training_proficiency IS 'Skill proficiency level before training (1=Beginner, 2=Developing, 3=Proficient, 4=Advanced, 5=Expert)';
COMMENT ON COLUMN workday_employee_skills_development.post_training_proficiency IS 'Skill proficiency level after training completion (1-5 scale)';
COMMENT ON COLUMN workday_employee_skills_development.target_proficiency IS 'Target proficiency level required for role (1-5 scale)';
COMMENT ON COLUMN workday_employee_skills_development.training_curriculum_title IS 'Title of training curriculum from CSOD that developed this skill';
COMMENT ON COLUMN workday_employee_skills_development.assessment_method IS 'Method used to assess skill proficiency';
COMMENT ON COLUMN workday_employee_skills_development.training_cost IS 'Cost associated with the training program in USD';
COMMENT ON COLUMN workday_employee_skills_development.proficiency_improvement IS 'Calculated improvement in proficiency (post - pre)';
COMMENT ON COLUMN workday_employee_skills_development.target_gap IS 'Calculated gap to target proficiency (target - post)';
COMMENT ON COLUMN workday_employee_skills_development.is_skill_proficient IS 'Whether employee has reached target proficiency level';
COMMENT ON COLUMN workday_employee_skills_development.roi_indicator IS 'Return on investment indicator (proficiency improvement per $1000 spent)';

-- =====================================================
-- Triggers for Automatic Updates
-- =====================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_workday_skills_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at on row changes
CREATE TRIGGER trigger_workday_skills_updated_at
    BEFORE UPDATE ON workday_employee_skills_development
    FOR EACH ROW
    EXECUTE FUNCTION update_workday_skills_updated_at();

-- =====================================================
-- Views for Common Analytics
-- =====================================================

-- Skills gap priority view
CREATE VIEW v_workday_skills_gaps AS
SELECT 
    skill_name,
    skill_category,
    skill_criticality,
    COUNT(*) as employees_with_gap,
    AVG(target_gap) as avg_gap_level,
    COUNT(DISTINCT division) as divisions_affected,
    AVG(training_cost) as avg_training_cost
FROM workday_employee_skills_development 
WHERE target_gap > 0
GROUP BY skill_name, skill_category, skill_criticality
ORDER BY 
    CASE skill_criticality 
        WHEN 'Critical' THEN 1 
        WHEN 'Important' THEN 2 
        ELSE 3 
    END,
    avg_gap_level DESC;

-- Employee skills portfolio view
CREATE VIEW v_workday_employee_portfolio AS
SELECT 
    employee_id,
    employee_name,
    division,
    job_title,
    COUNT(*) as total_skills_assessed,
    COUNT(CASE WHEN is_skill_proficient THEN 1 END) as skills_meeting_target,
    ROUND(
        COUNT(CASE WHEN is_skill_proficient THEN 1 END) * 100.0 / COUNT(*), 1
    ) as proficiency_achievement_rate,
    AVG(proficiency_improvement) as avg_improvement,
    SUM(training_cost) as total_training_investment,
    COUNT(CASE WHEN certification_earned IS NOT NULL AND certification_earned != '' THEN 1 END) as active_certifications
FROM workday_employee_skills_development
GROUP BY employee_id, employee_name, division, job_title;

-- Division competency overview
CREATE VIEW v_workday_division_competency AS
SELECT 
    division,
    competency_framework,
    COUNT(DISTINCT employee_id) as employees,
    COUNT(*) as total_assessments,
    AVG(post_training_proficiency) as avg_proficiency,
    COUNT(CASE WHEN is_skill_proficient THEN 1 END) * 100.0 / COUNT(*) as proficiency_rate,
    AVG(training_cost) as avg_cost_per_skill,
    COUNT(CASE WHEN skill_criticality = 'Critical' AND target_gap > 0 THEN 1 END) as critical_gaps
FROM workday_employee_skills_development
GROUP BY division, competency_framework
ORDER BY division;

-- =====================================================
-- Sample Data Validation Queries
-- =====================================================

-- Validate data quality
/*
-- Check for data anomalies
SELECT 'Proficiency Logic Issues' as check_type, COUNT(*) as issue_count
FROM workday_employee_skills_development 
WHERE post_training_proficiency < pre_training_proficiency

UNION ALL

SELECT 'Missing Certifications with High Proficiency', COUNT(*)
FROM workday_employee_skills_development 
WHERE is_skill_proficient = true 
  AND skill_category = 'Compliance' 
  AND (certification_earned IS NULL OR certification_earned = '')

UNION ALL

SELECT 'High Cost Training with No Improvement', COUNT(*)
FROM workday_employee_skills_development 
WHERE training_cost > 1500 AND proficiency_improvement = 0;
*/

-- =====================================================
-- Grants and Security (Customize as needed)
-- =====================================================

-- Grant appropriate permissions
-- GRANT SELECT ON workday_employee_skills_development TO reporting_role;
-- GRANT SELECT ON v_workday_skills_gaps TO manager_role;
-- GRANT INSERT, UPDATE ON workday_employee_skills_development TO hr_admin_role;