import asyncio
import httpx
import json

async def debug_add_component():
    """Debug the exact request being sent"""
    
    base_url = "http://localhost:8033"
    workflow_id = "44d6138c-1a31-4983-8b69-1cd9be8800e4"  # Use your actual workflow ID
    
    # Your component data (simplified for testing)
    component_data = [
        {
        "component_type": "question",
        "question": "Which training has the highest drop-off rate (i.e., the number of 'Registered' or 'Approved' statuses that did not result in 'Completed')",
        "description": "This report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown",
        "overview": {
            "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown"
        },
        "chart_config": {
            "format": "vega_lite",
            "reasoning": "A KPI chart is chosen to display the highest drop-off rate as a key performance indicator, even though all training titles have the same drop-off rate of 100.0%. This represents critical information regarding training effectiveness.",
            "batch_used": 0,
            "chart_type": "kpi",
            "data_count": 4,
            "data_sample": {
            "data": [
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
                }
            ],
            "columns": [
                "Training Title",
                "Drop-Off Rate"
            ]
            },
            "chart_schema": {
            "data": {
                "values": [
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Code of Conduct Awareness"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Effective Communication"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Product Knowledge"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Time Management"
                }
                ]
            },
            "mark": {
                "type": "text"
            },
            "title": "Highest Drop-Off Rate Training",
            "encoding": {
                "text": {
                "type": "quantitative",
                "field": "value"
                },
                "color": {
                "type": "nominal",
                "field": "metric"
                }
            },
            "kpi_metadata": {
                "is_dummy": True,
                "kpi_data": {
                "units": [],
                "values": [],
                "metrics": [],
                "targets": []
                },
                "chart_type": "kpi",
                "description": "KPI chart - templates will be created elsewhere",
                "vega_lite_compatible": False,
                "requires_custom_template": True
            }
            },
            "execution_info": {
            "data_count": 4,
            "execution_config": {
                "sort_by": None,
                "max_rows": 10000,
                "page_size": 1000,
                "sort_order": "ASC",
                "enable_pagination": True
            },
            "validation_success": False
            }
        },
        "table_config": {},
        "configuration": {},
        "sql_query": "SELECT training_title AS \"Training Title\", (COUNT(CASE WHEN completed_date IS None THEN 1 END) * 100.0 / COUNT(*)) AS \"Drop-Off Rate\" FROM csod_training_records WHERE lower(transcript_status) IN (lower('Registered'), lower('Approved')) GROUP BY training_title ORDER BY \"Drop-Off Rate\" DESC LIMIT 1",
        "executive_summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown",
        "data_overview": {
            "total_rows": 0,
            "total_batches": 1,
            "batches_processed": 1
        },
        "visualization_data": {
            "data": [
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
            }
            ],
            "columns": [
            "Training Title",
            "Drop-Off Rate"
            ]
        },
        "sample_data": {
            "data": [
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
            }
            ],
            "columns": [
            "Training Title",
            "Drop-Off Rate"
            ]
        },
        "metadata": {
            "project_id": "cornerstone",
            "data_description": "I have given the sql query and question.",
            "processing_stats": {
            "timestamp": "2025-08-20T15:55:13.358800",
            "total_tokens": 0,
            "estimated_cost": 0
            }
        },
        "chart_schema": {
            "data": {
            "values": [
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
                }
            ]
            },
            "mark": {
            "type": "text"
            },
            "title": "Highest Drop-Off Rate Training",
            "encoding": {
            "text": {
                "type": "quantitative",
                "field": "value"
            },
            "color": {
                "type": "nominal",
                "field": "metric"
            }
            },
            "kpi_metadata": {
            "is_dummy": True,
            "kpi_data": {
                "units": [],
                "values": [],
                "metrics": [],
                "targets": []
            },
            "chart_type": "kpi",
            "description": "KPI chart - templates will be created elsewhere",
            "vega_lite_compatible": False,
            "requires_custom_template": True
            }
        },
        "reasoning": "A KPI chart is chosen to display the highest drop-off rate as a key performance indicator, even though all training titles have the same drop-off rate of 100.0%. This represents critical information regarding training effectiveness.",
        "data_count": 4,
        "validation_results": {
            "data_count": 4,
            "execution_config": {
            "sort_by": None,
            "max_rows": 10000,
            "page_size": 1000,
            "sort_order": "ASC",
            "enable_pagination": True
            },
            "validation_success": False
        }
        },
        {
        "component_type": "question",
        "question": "Are there specific users who have a high number of overdue trainings across different curriculums?",
        "description": "This report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
        "overview": {
            "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown"
        },
        "chart_config": {
            "format": "vega_lite",
            "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
            "batch_used": 0,
            "chart_type": "bar",
            "data_count": 487,
            "data_sample": {
            "data": [
                {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
                }
            ],
            "columns": [
                "full_name",
                "overdue_trainings"
            ]
            },
            "chart_schema": {
            "data": {
                "values": [
                {
                    "full_name": "Yvette Reid",
                    "overdue_trainings": "271"
                }
                ]
            },
            "mark": {
                "type": "bar"
            },
            "title": "Overdue Trainings by User",
            "height": 430,
            "encoding": {
                "x": {
                "type": "nominal",
                "field": "full_name",
                "title": "User"
                },
                "y": {
                "type": "quantitative",
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings"
                },
                "tooltip": [
                {
                    "field": "full_name",
                    "title": "User"
                },
                {
                    "field": "overdue_trainings",
                    "title": "Number of Overdue Trainings",
                    "format": ","
                }
                ]
            }
            },
            "execution_info": {
            "data_count": 487,
            "execution_config": {
                "sort_by": None,
                "max_rows": 10000,
                "page_size": 1000,
                "sort_order": "ASC",
                "enable_pagination": True
            },
            "validation_success": False
            }
        },
        "table_config": {},
        "configuration": {},
        "sql_query": "SELECT tr.full_name AS Full_Name, COUNT(*) AS Overdue_Trainings FROM csod_training_records AS tr WHERE tr.due_date < CAST('2025-08-20 00:00:00' AS TIMESTAMP WITH TIME ZONE) GROUP BY tr.full_name HAVING COUNT(*) > 3 ORDER BY Overdue_Trainings DESC",
        "executive_summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
        "data_overview": {
            "total_rows": 0,
            "total_batches": 1,
            "batches_processed": 1
        },
        "visualization_data": {
            "data": [
            {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
            }
            ],
            "columns": [
            "full_name",
            "overdue_trainings"
            ]
        },
        "sample_data": {
            "data": [
            {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
            }
            ],
            "columns": [
            "full_name",
            "overdue_trainings"
            ]
        },
        "metadata": {
            "project_id": "cornerstone",
            "data_description": "I have given the sql query and question.",
            "processing_stats": {
            "timestamp": "2025-08-20T15:52:11.327061",
            "total_tokens": 0,
            "estimated_cost": 0
            }
        },
        "chart_schema": {
            "data": {
            "values": [
                {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
                }
            ]
            },
            "mark": {
            "type": "bar"
            },
            "title": "Overdue Trainings by User",
            "height": 430,
            "encoding": {
            "x": {
                "type": "nominal",
                "field": "full_name",
                "title": "User"
            },
            "y": {
                "type": "quantitative",
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings"
            },
            "tooltip": [
                {
                "field": "full_name",
                "title": "User"
                },
                {
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings",
                "format": ","
                }
            ]
            }
        },
        "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
        "data_count": 487,
        "validation_results": {
            "data_count": 487,
            "execution_config": {
            "sort_by": None,
            "max_rows": 10000,
            "page_size": 1000,
            "sort_order": "ASC",
            "enable_pagination": True
            },
            "validation_success": False
        }
        }
  ]
    
    url = f"{base_url}/api/v1/workflows/{workflow_id}/dashboard/add-component"
    
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(component_data, indent=2)}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Log the exact request being made
            request = client.build_request(
                method="POST",
                url=url,
                json=component_data
            )
            
            print(f"\n=== REQUEST DETAILS ===")
            print(f"Method: {request.method}")
            print(f"URL: {request.url}")
            print(f"Headers: {dict(request.headers)}")
            print(f"Content: {request.content.decode('utf-8') if request.content else 'None'}")
            print(f"======================\n")
            
            # Send the request
            response = await client.send(request)
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Content: {response.text}")
            
            # Try to parse as JSON
            try:
                json_response = response.json()
                print(f"JSON Response: {json.dumps(json_response, indent=2)}")
                return json_response
            except Exception as e:
                print(f"JSON Parse Error: {e}")
                return None
                
    except Exception as e:
        print(f"Request Error: {e}")
        print(f"Error Type: {type(e)}")
        return None

# Also test with requests library to compare
def debug_with_requests():
    """Compare with requests library"""
    import requests
    
    base_url = "http://localhost:8033"
    workflow_id = "44d6138c-1a31-4983-8b69-1cd9be8800e4"
    
    component_data = [
        {
        "component_type": "question",
        "question": "Which training has the highest drop-off rate (i.e., the number of 'Registered' or 'Approved' statuses that did not result in 'Completed')",
        "description": "This report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown",
        "overview": {
            "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown"
        },
        "chart_config": {
            "format": "vega_lite",
            "reasoning": "A KPI chart is chosen to display the highest drop-off rate as a key performance indicator, even though all training titles have the same drop-off rate of 100.0%. This represents critical information regarding training effectiveness.",
            "batch_used": 0,
            "chart_type": "kpi",
            "data_count": 4,
            "data_sample": {
            "data": [
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
                }
            ],
            "columns": [
                "Training Title",
                "Drop-Off Rate"
            ]
            },
            "chart_schema": {
            "data": {
                "values": [
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Code of Conduct Awareness"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Effective Communication"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Product Knowledge"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Time Management"
                }
                ]
            },
            "mark": {
                "type": "text"
            },
            "title": "Highest Drop-Off Rate Training",
            "encoding": {
                "text": {
                "type": "quantitative",
                "field": "value"
                },
                "color": {
                "type": "nominal",
                "field": "metric"
                }
            },
            "kpi_metadata": {
                "is_dummy": True,
                "kpi_data": {
                "units": [],
                "values": [],
                "metrics": [],
                "targets": []
                },
                "chart_type": "kpi",
                "description": "KPI chart - templates will be created elsewhere",
                "vega_lite_compatible": False,
                "requires_custom_template": True
            }
            },
            "execution_info": {
            "data_count": 4,
            "execution_config": {
                "sort_by": None,
                "max_rows": 10000,
                "page_size": 1000,
                "sort_order": "ASC",
                "enable_pagination": True
            },
            "validation_success": False
            }
        },
        "table_config": {},
        "configuration": {},
        "sql_query": "SELECT training_title AS \"Training Title\", (COUNT(CASE WHEN completed_date IS None THEN 1 END) * 100.0 / COUNT(*)) AS \"Drop-Off Rate\" FROM csod_training_records WHERE lower(transcript_status) IN (lower('Registered'), lower('Approved')) GROUP BY training_title ORDER BY \"Drop-Off Rate\" DESC LIMIT 1",
        "executive_summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown",
        "data_overview": {
            "total_rows": 0,
            "total_batches": 1,
            "batches_processed": 1
        },
        "visualization_data": {
            "data": [
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
            }
            ],
            "columns": [
            "Training Title",
            "Drop-Off Rate"
            ]
        },
        "sample_data": {
            "data": [
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
            }
            ],
            "columns": [
            "Training Title",
            "Drop-Off Rate"
            ]
        },
        "metadata": {
            "project_id": "cornerstone",
            "data_description": "I have given the sql query and question.",
            "processing_stats": {
            "timestamp": "2025-08-20T15:55:13.358800",
            "total_tokens": 0,
            "estimated_cost": 0
            }
        },
        "chart_schema": {
            "data": {
            "values": [
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
                }
            ]
            },
            "mark": {
            "type": "text"
            },
            "title": "Highest Drop-Off Rate Training",
            "encoding": {
            "text": {
                "type": "quantitative",
                "field": "value"
            },
            "color": {
                "type": "nominal",
                "field": "metric"
            }
            },
            "kpi_metadata": {
            "is_dummy": True,
            "kpi_data": {
                "units": [],
                "values": [],
                "metrics": [],
                "targets": []
            },
            "chart_type": "kpi",
            "description": "KPI chart - templates will be created elsewhere",
            "vega_lite_compatible": False,
            "requires_custom_template": True
            }
        },
        "reasoning": "A KPI chart is chosen to display the highest drop-off rate as a key performance indicator, even though all training titles have the same drop-off rate of 100.0%. This represents critical information regarding training effectiveness.",
        "data_count": 4,
        "validation_results": {
            "data_count": 4,
            "execution_config": {
            "sort_by": None,
            "max_rows": 10000,
            "page_size": 1000,
            "sort_order": "ASC",
            "enable_pagination": True
            },
            "validation_success": False
        }
        },
        {
        "component_type": "question",
        "question": "Are there specific users who have a high number of overdue trainings across different curriculums?",
        "description": "This report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
        "overview": {
            "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown"
        },
        "chart_config": {
            "format": "vega_lite",
            "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
            "batch_used": 0,
            "chart_type": "bar",
            "data_count": 487,
            "data_sample": {
            "data": [
                {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
                }
            ],
            "columns": [
                "full_name",
                "overdue_trainings"
            ]
            },
            "chart_schema": {
            "data": {
                "values": [
                {
                    "full_name": "Yvette Reid",
                    "overdue_trainings": "271"
                }
                ]
            },
            "mark": {
                "type": "bar"
            },
            "title": "Overdue Trainings by User",
            "height": 430,
            "encoding": {
                "x": {
                "type": "nominal",
                "field": "full_name",
                "title": "User"
                },
                "y": {
                "type": "quantitative",
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings"
                },
                "tooltip": [
                {
                    "field": "full_name",
                    "title": "User"
                },
                {
                    "field": "overdue_trainings",
                    "title": "Number of Overdue Trainings",
                    "format": ","
                }
                ]
            }
            },
            "execution_info": {
            "data_count": 487,
            "execution_config": {
                "sort_by": None,
                "max_rows": 10000,
                "page_size": 1000,
                "sort_order": "ASC",
                "enable_pagination": True
            },
            "validation_success": False
            }
        },
        "table_config": {},
        "configuration": {},
        "sql_query": "SELECT tr.full_name AS Full_Name, COUNT(*) AS Overdue_Trainings FROM csod_training_records AS tr WHERE tr.due_date < CAST('2025-08-20 00:00:00' AS TIMESTAMP WITH TIME ZONE) GROUP BY tr.full_name HAVING COUNT(*) > 3 ORDER BY Overdue_Trainings DESC",
        "executive_summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
        "data_overview": {
            "total_rows": 0,
            "total_batches": 1,
            "batches_processed": 1
        },
        "visualization_data": {
            "data": [
            {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
            }
            ],
            "columns": [
            "full_name",
            "overdue_trainings"
            ]
        },
        "sample_data": {
            "data": [
            {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
            }
            ],
            "columns": [
            "full_name",
            "overdue_trainings"
            ]
        },
        "metadata": {
            "project_id": "cornerstone",
            "data_description": "I have given the sql query and question.",
            "processing_stats": {
            "timestamp": "2025-08-20T15:52:11.327061",
            "total_tokens": 0,
            "estimated_cost": 0
            }
        },
        "chart_schema": {
            "data": {
            "values": [
                {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
                }
            ]
            },
            "mark": {
            "type": "bar"
            },
            "title": "Overdue Trainings by User",
            "height": 430,
            "encoding": {
            "x": {
                "type": "nominal",
                "field": "full_name",
                "title": "User"
            },
            "y": {
                "type": "quantitative",
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings"
            },
            "tooltip": [
                {
                "field": "full_name",
                "title": "User"
                },
                {
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings",
                "format": ","
                }
            ]
            }
        },
        "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
        "data_count": 487,
        "validation_results": {
            "data_count": 487,
            "execution_config": {
            "sort_by": None,
            "max_rows": 10000,
            "page_size": 1000,
            "sort_order": "ASC",
            "enable_pagination": True
            },
            "validation_success": False
        }
        }
  ]
    
    url = f"{base_url}/api/v1/workflows/{workflow_id}/dashboard/add-component"
    
    print(f"\n=== REQUESTS LIBRARY TEST ===")
    try:
        response = requests.post(url, json=component_data, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        if response.headers.get('content-type', '').startswith('application/json'):
            print(f"JSON: {response.json()}")
    except Exception as e:
        print(f"Requests error: {e}")

if __name__ == "__main__":
    print("Testing httpx request...")
    result = asyncio.run(debug_add_component())
    
    print("\n" + "="*50)
    
    print("Testing requests library...")
    debug_with_requests()