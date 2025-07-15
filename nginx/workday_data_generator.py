import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import json

class WorkdaySkillsGenerator:
    """
    Simplified class-based approach for generating Workday skills development data.
    """
    
    def __init__(self):
        """Initialize the generator with configuration data."""
        self.setup_configurations()
        
    def setup_configurations(self):
        """Set up all configuration dictionaries and mappings."""
        
        # Skill mappings by curriculum
        self.skill_mappings = {
            "Onboarding for New Hires": {
                "Company Culture Knowledge": {"category": "Soft Skills", "criticality": "Important"},
                "Communication Skills": {"category": "Soft Skills", "criticality": "Important"},
                "Time Management": {"category": "Soft Skills", "criticality": "Beneficial"},
                "Code of Conduct Compliance": {"category": "Compliance", "criticality": "Critical"}
            },
            "Compliance Training": {
                "Regulatory Compliance": {"category": "Compliance", "criticality": "Critical"},
                "Data Privacy Knowledge": {"category": "Compliance", "criticality": "Critical"},
                "Product Knowledge": {"category": "Technical", "criticality": "Important"},
                "Risk Management": {"category": "Compliance", "criticality": "Important"}
            },
            "Leadership Basics": {
                "Team Leadership": {"category": "Leadership", "criticality": "Critical"},
                "Performance Management": {"category": "Leadership", "criticality": "Important"},
                "Coaching Skills": {"category": "Leadership", "criticality": "Important"},
                "Strategic Thinking": {"category": "Leadership", "criticality": "Beneficial"}
            },
            "Sales Training": {
                "Sales Techniques": {"category": "Technical", "criticality": "Critical"},
                "Customer Relationship Management": {"category": "Technical", "criticality": "Critical"},
                "Negotiation Skills": {"category": "Soft Skills", "criticality": "Important"},
                "Market Analysis": {"category": "Technical", "criticality": "Beneficial"}
            }
        }
        
        # Other configurations
        self.frameworks = {
            "Customer Support": "Customer Excellence Framework",
            "Administration": "Operational Excellence Framework", 
            "Engineering": "Technical Excellence Framework",
            "Marketing": "Marketing Excellence Framework",
            "Sales": "Sales Excellence Framework"
        }
        
        self.assessment_methods = ["Self-Assessment", "Manager Review", "Certification", "Practical Test", "Peer Review"]
        
        self.job_levels = {
            "Manager": ["Project Manager", "HR Manager", "IT Manager"],
            "Senior IC": ["Sales Executive", "Senior Engineer", "Marketing Specialist"],
            "Individual Contributor": ["Customer Service Rep", "Software Engineer", "Data Analyst"]
        }
        
        self.cost_ranges = {
            "Onboarding for New Hires": (600, 1000),
            "Compliance Training": (400, 600),
            "Leadership Basics": (1200, 1800),
            "Sales Training": (1000, 1400)
        }
    
    def generate_skill_record(self, training_row: pd.Series, skill_name: str, record_id: int) -> dict:
        """
        Generate a single skill development record.
        
        Args:
            training_row: Row from CSOD training data
            skill_name: Name of the skill being developed
            record_id: Unique identifier for the record
            
        Returns:
            dict: Complete skill development record
        """
        skill_info = self.skill_mappings[training_row['curriculum_title']][skill_name]
        
        # Date calculations
        completed_date = pd.to_datetime(training_row['completed_date'])
        assessment_date = completed_date + timedelta(days=random.randint(7, 30))
        hire_date = completed_date - timedelta(days=random.randint(30, 1460))
        
        # Proficiency calculations
        pre_prof = random.randint(1, 3)
        target_prof = self._calculate_target_proficiency(skill_info['criticality'])
        post_prof = self._calculate_post_proficiency(pre_prof, training_row.get('satisfied_late', False))
        
        # Cost calculation
        cost_range = self.cost_ranges.get(training_row['curriculum_title'], (500, 1000))
        training_cost = round(random.uniform(cost_range[0], cost_range[1]), 2)
        
        # Certification logic
        has_cert = self._should_have_certification(skill_info['category'], post_prof, target_prof)
        
        return {
            'id': record_id,
            'employee_id': training_row['user_id'],
            'employee_name': training_row['full_name'],
            'manager_id': f"MGR{random.randint(10000, 99999)}",
            'manager_name': training_row['manager_name'],
            'division': training_row['division'],
            'job_title': training_row['position'],
            'job_level': self._get_job_level(training_row['position']),
            'hire_date': hire_date.strftime('%Y-%m-%d'),
            'skill_name': skill_name,
            'skill_category': skill_info['category'],
            'competency_framework': self.frameworks.get(training_row['division'], "General Framework"),
            'pre_training_proficiency': pre_prof,
            'post_training_proficiency': post_prof,
            'target_proficiency': target_prof,
            'skill_criticality': skill_info['criticality'],
            'training_curriculum_id': f"CURR_{training_row['curriculum_title'].replace(' ', '_').upper()}",
            'training_curriculum_title': training_row['curriculum_title'],
            'skill_assessment_date': assessment_date.strftime('%Y-%m-%d'),
            'assessment_method': random.choice(self.assessment_methods),
            'certification_earned': f"{skill_name} Certification" if has_cert else "",
            'certification_expiry_date': (assessment_date + timedelta(days=random.randint(365, 1095))).strftime('%Y-%m-%d') if has_cert else "",
            'cost_center': f"CC_{training_row['division'].replace(' ', '_').upper()}",
            'training_cost': training_cost,
            'performance_rating': round(random.uniform(2.5, 4.8), 1),
            'career_development_plan': random.choice(["Leadership Track", "Technical Track", ""]) if random.random() < 0.4 else "",
            'succession_plan_role': "Senior Manager" if "Manager" in training_row['position'] and random.random() < 0.3 else "",
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            # Calculated fields
            'proficiency_improvement': post_prof - pre_prof,
            'target_gap': target_prof - post_prof,
            'is_skill_proficient': post_prof >= target_prof,
            'tenure_months': random.randint(6, 65),
            'roi_indicator': round((post_prof - pre_prof) / training_cost * 1000, 2) if post_prof > pre_prof else 0
        }
    
    def _calculate_target_proficiency(self, criticality: str) -> int:
        """Calculate target proficiency based on skill criticality."""
        if criticality == "Critical":
            return random.randint(4, 5)
        elif criticality == "Important":
            return random.randint(3, 4)
        else:  # Beneficial
            return random.randint(3, 4)
    
    def _calculate_post_proficiency(self, pre_prof: int, was_late: bool) -> int:
        """Calculate post-training proficiency based on pre-proficiency and completion timeliness."""
        improvement_chance = 0.7 if was_late else 0.85
        if random.random() < improvement_chance:
            improvement = random.randint(1, 2)
            return min(5, pre_prof + improvement)
        return pre_prof
    
    def _should_have_certification(self, category: str, post_prof: int, target_prof: int) -> bool:
        """Determine if certification should be awarded."""
        if post_prof < target_prof:
            return False
        
        cert_rates = {"Compliance": 0.8, "Technical": 0.4, "Leadership": 0.3, "Soft Skills": 0.2}
        return random.random() < cert_rates.get(category, 0.2)
    
    def _get_job_level(self, position: str) -> str:
        """Determine job level from position title."""
        if any(title in position for title in self.job_levels["Manager"]):
            return "Manager"
        elif any(title in position for title in self.job_levels["Senior IC"]):
            return "Senior IC"
        else:
            return "Individual Contributor"
    
    def generate_from_csv(self, csod_csv_path: str, output_path: str = "workday_skills.csv", limit: int = 2000) -> pd.DataFrame:
        """
        Generate Workday skills data from CSOD CSV file.
        
        Args:
            csod_csv_path: Path to CSOD training records CSV
            output_path: Path for output CSV file
            limit: Maximum number of completed training records to process
            
        Returns:
            pd.DataFrame: Generated skills development data
        """
        print(f"Loading CSOD data from {csod_csv_path}...")
        csod_df = pd.read_csv(csod_csv_path)
        
        # Filter for completed training
        completed = csod_df[csod_df['transcript_status'] == 'Completed'].head(limit)
        print(f"Processing {len(completed)} completed training records...")
        
        records = []
        record_id = 1
        
        for idx, training_row in completed.iterrows():
            curriculum = training_row['curriculum_title']
            
            if curriculum not in self.skill_mappings:
                continue
                
            # Select 1-2 skills per training
            available_skills = list(self.skill_mappings[curriculum].keys())
            selected_skills = random.sample(available_skills, min(random.randint(1, 2), len(available_skills)))
            
            for skill_name in selected_skills:
                record = self.generate_skill_record(training_row, skill_name, record_id)
                records.append(record)
                record_id += 1
            
            if (idx + 1) % 500 == 0:
                print(f"Processed {idx + 1} training records, generated {len(records)} skill records")
        
        # Create DataFrame and save
        df = pd.DataFrame(records)
        df.to_csv(output_path, index=False)
        
        print(f"\n✅ Generated {len(df)} records and saved to {output_path}")
        self._print_summary(df)
        
        return df
    
    def _print_summary(self, df: pd.DataFrame):
        """Print summary statistics of generated data."""
        print(f"\n=== SUMMARY STATISTICS ===")
        print(f"Total records: {len(df)}")
        print(f"Unique employees: {df['employee_id'].nunique()}")
        print(f"Average proficiency improvement: {df['proficiency_improvement'].mean():.2f}")
        print(f"Skills meeting target: {df['is_skill_proficient'].sum()} ({df['is_skill_proficient'].mean()*100:.1f}%)")
        print(f"Average training cost: ${df['training_cost'].mean():.2f}")
        print(f"Average ROI indicator: {df['roi_indicator'].mean():.2f}")
        
        print(f"\nSkill categories:")
        print(df['skill_category'].value_counts())
        
        print(f"\nDivision distribution:")
        print(df['division'].value_counts())

# Utility functions
def validate_relationships(csod_df: pd.DataFrame, workday_df: pd.DataFrame) -> dict:
    """
    Validate the relationship connections between CSOD and Workday data.
    
    Args:
        csod_df: CSOD training records DataFrame
        workday_df: Workday skills development DataFrame
        
    Returns:
        dict: Validation results
    """
    results = {}
    
    # Employee ID matching
    csod_employees = set(csod_df['user_id'].unique())
    workday_employees = set(workday_df['employee_id'].unique())
    
    results['employee_match_rate'] = len(workday_employees.intersection(csod_employees)) / len(workday_employees)
    results['employees_in_both'] = len(workday_employees.intersection(csod_employees))
    results['employees_only_workday'] = len(workday_employees - csod_employees)
    
    # Curriculum matching
    csod_curricula = set(csod_df['curriculum_title'].unique())
    workday_curricula = set(workday_df['training_curriculum_title'].unique())
    
    results['curriculum_match_rate'] = len(workday_curricula.intersection(csod_curricula)) / len(workday_curricula)
    
    # Division consistency
    csod_divisions = set(csod_df['division'].unique())
    workday_divisions = set(workday_df['division'].unique())
    
    results['division_consistency'] = workday_divisions.issubset(csod_divisions)
    
    return results

def create_sample_integration_queries() -> dict:
    """
    Create sample SQL queries for integrating CSOD and Workday data.
    
    Returns:
        dict: Dictionary of sample SQL queries
    """
    queries = {
        "training_effectiveness": """
        SELECT 
            c.curriculum_title,
            COUNT(c.id) as total_assignments,
            COUNT(CASE WHEN c.transcript_status = 'Satisfied' THEN 1 END) as completions,
            AVG(w.proficiency_improvement) as avg_skill_improvement,
            AVG(w.training_cost) as avg_cost,
            AVG(w.roi_indicator) as avg_roi
        FROM csod_training_records c
        LEFT JOIN workday_employee_skills_development w 
            ON c.user_id = w.employee_id 
            AND c.curriculum_title = w.training_curriculum_title
        GROUP BY c.curriculum_title
        ORDER BY avg_roi DESC;
        """,
        
        "employee_learning_journey": """
        SELECT 
            c.user_id,
            c.full_name,
            c.curriculum_title,
            c.completed_date,
            w.skill_name,
            w.pre_training_proficiency,
            w.post_training_proficiency,
            w.proficiency_improvement,
            w.is_skill_proficient
        FROM csod_training_records c
        INNER JOIN workday_employee_skills_development w 
            ON c.user_id = w.employee_id 
            AND c.curriculum_title = w.training_curriculum_title
        WHERE c.transcript_status = 'Satisfied'
        ORDER BY c.user_id, c.completed_date;
        """,
        
        "division_skills_gap": """
        SELECT 
            w.division,
            w.skill_name,
            w.skill_criticality,
            COUNT(*) as employees_assessed,
            AVG(w.target_gap) as avg_gap,
            COUNT(CASE WHEN w.target_gap > 0 THEN 1 END) as employees_with_gaps
        FROM workday_employee_skills_development w
        WHERE w.skill_criticality = 'Critical'
        GROUP BY w.division, w.skill_name, w.skill_criticality
        HAVING AVG(w.target_gap) > 0
        ORDER BY w.division, avg_gap DESC;
        """
    }
    
    return queries

# Quick usage example
def quick_generate(csod_file: str, limit: int = 1000) -> pd.DataFrame:
    """
    Quick function to generate Workday data with minimal configuration.
    
    Args:
        csod_file: Path to CSOD CSV file
        limit: Number of records to process
        
    Returns:
        pd.DataFrame: Generated Workday skills data
    """
    generator = WorkdaySkillsGenerator()
    return generator.generate_from_csv(csod_file, limit=limit)

if __name__ == "__main__":
    # Example usage
    generator = WorkdaySkillsGenerator()
    
    # Generate data (update path as needed)
    workday_data = generator.generate_from_csv(
        "/Users/sameerm/Downloads/csod_training_records_202507071832.csv",
        "workday_employee_skills_development.csv",
        limit=50000
    )
    
    # Show sample integration queries
    queries = create_sample_integration_queries()
    print("\n=== SAMPLE INTEGRATION QUERIES ===")
    for name, query in queries.items():
        print(f"\n-- {name.upper().replace('_', ' ')} --")
        print(query)