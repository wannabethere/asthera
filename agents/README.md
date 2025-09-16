uvicorn main:app --reload --host 0.0.0.0 --port 8020 --workers 4
https://blog.gopenai.com/fine-tuning-a-text-to-sql-llm-for-reasoning-using-grpo-ec2c1b55278f
https://deepwiki.com/search/find-all-files-where-streaming_cf6cacfb-6b54-4dc9-b562-28a12c339cad
https://deepwiki.com/onyx-dot-app/onyx


nohup uvicorn main:app --reload --host 0.0.0.0 --port 8025 --workers 4 > uvicorn.log 2>&1 &
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8025 --workers 4 > uvicorn.log 2>&1 & echo $! > run.pid
docker run -d -v  ./structured-data:/data -p 8888:8000 chromadb/chroma:0.6.3
docker run -d -v ./unstructured-data:/data -p 8015:8000 chromadb/chroma:0.5.13

find . -type d -name __pycache__ -exec rm -r {} +
find . -type d -name "__MACOSX" -print0 | xargs -0 rm -rf


scp -i ~/Downloads/flowharmonic.pem agents.zip ec2-user@ec2-54-161-71-105.compute-1.amazonaws.com:~/.

https://ec2-54-161-71-105.compute-1.amazonaws.com/dashboards/dashboard-U13E13890/staticdashboards


for dataservices:
sudo yum install postgresql-devel python3-devel gcc
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8035 --workers 4 > dataservices.log 2>&1 & echo $! > run.pid

nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8045 --workers 4 > workflowservices.log 2>&1 & echo $! > run.pid

https://github.com/llm-d/llm-d

 'columns': ['Full_Name', 'User_ID', 'Division', 'Assigned_Date', 'Completed_Date', 'Due_Date', 'is_completed', 'is_satisfied_late'], 'table_name': 'csod_training_records'}