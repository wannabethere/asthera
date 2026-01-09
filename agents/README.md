uvicorn main:app --reload --host 0.0.0.0 --port 8020 --workers 4
https://blog.gopenai.com/fine-tuning-a-text-to-sql-llm-for-reasoning-using-grpo-ec2c1b55278f
https://deepwiki.com/search/find-all-files-where-streaming_cf6cacfb-6b54-4dc9-b562-28a12c339cad
https://deepwiki.com/onyx-dot-app/onyx
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8020 --workers 4 > uvicorn.log 2>&1 & echo $! > run.pid

sudo dnf install -y python3.11 python3.11-pip


nohup uvicorn main:app --reload --host 0.0.0.0 --port 8025 --workers 4 > uvicorn.log 2>&1 &
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8025 --workers 4 > uvicorn.log 2>&1 & echo $! > run.pid
docker run -d -v  ./structured-data:/data -p 8888:8000 chromadb/chroma:0.6.3
docker run -d -v ./unstructured-data:/data -p 8015:8000 chromadb/chroma:0.5.13

find . -type d -name __pycache__ -exec rm -r {} +
find . -type d -name "__MACOSX" -print0 | xargs -0 rm -rf


scp -i ~/Downloads/flowharmonic.pem agents.zip  
scp -i ~/Downloads/flowharmonic.pem agents.zip ec2-user@ec2-54-161-71-105.compute-1.amazonaws.com:~/.
scp -i  files ec2-user@ec2-44-202-8-38.compute-1.amazonaws.com:~/.
scp -i ~/Downloads/flowharmonic.pem agents.zip ec2-user@ec2-44-202-8-38.compute-1.amazonaws.com:~/.
scp -i ~/Download       ec2-user@ec2-18-204-196-65.compute-1.amazonaws.com:~/.

sameerm@Sameers-iMac genieml % scp -i ~/Downloads/flowharmonic.pem agents.zip  ec2-user@ec2-44-202-8-38.compute-1.amazonaws.com:~/.
agents.zip                                                                                                                                                                                                                                                                                                                                100% 3515KB   3.2MB/s   00:01    
sameerm@Sameers-iMac genieml % scp -i ~/Downloads/flowharmonic.pem agents.zip  ec2-user@ec2-18-204-196-65.compute-1.amazonaws.com:~/.
agents.zip                

ec2-user@100.26.125.159


https://ec2-54-161-71-105.compute-1.amazonaws.com/dashboards/dashboard-U13E13890/staticdashboards


for dataservices:
sudo yum install postgresql-devel python3-devel gcc
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8035 --workers 4 > dataservices.log 2>&1 & echo $! > run.pid

nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8045 --workers 4 > workflowservices.log 2>&1 & echo $! > run.pid

nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8005 --workers 4 > server.log 2>&1 & echo $! > run.pid

nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8055 --workers 4 > dashboardservice.log 2>&1 & echo $! > run.pid

nohup sh -c 'HOST=0.0.0.0 PORT=9001 npm start' > app.log 2>&1 & echo $! > run.pid


https://github.com/llm-d/llm-d

 'columns': ['Full_Name', 'User_ID', 'Division', 'Assigned_Date', 'Completed_Date', 'Due_Date', 'is_completed', 'is_satisfied_late'], 'table_name': 'csod_training_records'}


http://ec2-54-147-109-184.compute-1.amazonaws.com:8585/users/admin/access-token
 admin

 eyJraWQiOiJHYjM4OWEtOWY3Ni1nZGpzLWE5MmotMDI0MmJrOTQzNTYiLCJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJvcGVuLW1ldGFkYXRhLm9yZyIsInN1YiI6ImFkbWluIiwicm9sZXMiOlsiQWRtaW4iXSwiZW1haWwiOiJhZG1pbkBvcGVuLW1ldGFkYXRhLm9yZyIsImlzQm90IjpmYWxzZSwidG9rZW5UeXBlIjoiUEVSU09OQUxfQUNDRVNTIiwiaWF0IjoxNzYzMzQ2NzA2LCJleHAiOjE3Njg1MzA3MDZ9.wU2VR9b60SBA-Qp7TvaqxSwpHaqskg5kgWgyeclFz7vVC4NEZygEgEdp_l9q87R-sSr9BK_t2iJ2Nrkz0hCr2SqWRYdywT3KREX_vnVX6uNxeRJHXyplk2dHE9WL6b9KCZA1PjlX59XxiGg5sK9Q6ScT8XpfulVd-c2VrKXkTS3JmmNcRxuIs86x1sZNgWXH2ipnxTwYGZX-Y_S7lpN9hcvSJMnHc69pxfdG_3PFdsZRiC3s5nuM3EoHD3FeISR8SPXPzw71MjxabjevQzqXaNWPqagbsswEFfOydVmiieWI1Gfh9rqAFud9_U2KcoaY3fVfnet9lk4xFfV0yTHFKQ


 # Run full workflow (all steps)
python workflow_executor.py asset_risk_workflow.json --output-dir ./output/asset_risk_pipe

# Run only silver layer generation
python workflow_executor.py asset_risk_workflow.json --output-dir ./output/asset_risk_pipe --modeling_type silver

# Run only gold layer generation (requires silver to be complete)
python workflow_executor.py asset_risk_workflow.json --output-dir ./output/asset_risk_pipe --modeling_type gold

# Run only transformation layer generation
python workflow_executor.py asset_risk_workflow.json --output-dir ./output/asset_risk_pipe --modeling_type transform


SELECT ROUND((COUNT(DISTINCT CASE WHEN t.completionDate IS NOT NULL THEN t.userID END)::DECIMAL / COUNT(DISTINCT t.userID)) * 100, 2) AS completion_rate FROM Transcript_csod AS t JOIN Activity_csod AS a ON t.loID = a.loID WHERE a.isCompliance = 'true' AND t.registrationDate >= DATE_TRUNC('quarter', CURRENT_DATE) AND t.registrationDate < DATE_TRUNC('quarter', CURRENT_DATE) + INTERVAL '3 months';