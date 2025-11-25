-- Transformation: silver_to_gold_gold_top_5_business_units_by_attack_surface
-- Source: silver.gold_top_5_business_units_by_attack_surface
-- Target: gold.gold_gold_top_5_business_units_by_attack_surface
-- Description: Transform gold_top_5_business_units_by_attack_surface from silver to gold

-- Metric: top_5_business_units_by_attack_surface: Ranking of the top 5 business units based on total attack surface count
WITH ranked_business_units AS (
    SELECT 
        business_unit,
        COUNT(*) AS total_attack_surface,
        MAX(vulnerability_score) AS highest_vulnerability_score
    FROM 
        attack_surface_table
    GROUP BY 
        business_unit
    HAVING 
        COUNT(*) > 0  -- Only include business units with at least one attack surface element
),
ranked_with_ranks AS (
    SELECT 
        business_unit,
        total_attack_surface,
        highest_vulnerability_score,
        RANK() OVER (ORDER BY total_attack_surface DESC, highest_vulnerability_score DESC) AS rank
    FROM 
        ranked_business_units
)
SELECT 
    business_unit,
    total_attack_surface,
    highest_vulnerability_score
FROM 
    ranked_with_ranks
WHERE 
    rank <= 5  -- Select top 5 business units
ORDER BY 
    rank;  -- Order by rank for final output

-- Insert the results into the target table
INSERT INTO gold_top_5_business_units_by_attack_surface (business_unit, total_attack_surface, highest_vulnerability_score)
SELECT 
    business_unit,
    total_attack_surface,
    highest_vulnerability_score
FROM 
    ranked_with_ranks
WHERE 
    rank <= 5;  -- Ensure only top 5 are inserted