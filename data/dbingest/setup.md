Setting up Exploit-DB as a datasource in Docker can be achieved by either mounting the Exploit-DB git repository in a container or by utilizing a pre-built Docker image that provides the data via a server or a database. 
Here are the primary methods:
Method 1: Using the Git Repository and SearchSploit (CLI Tool) 
This method involves cloning the official Exploit-DB repository into your container, allowing you to use the searchsploit command-line tool locally within the container.
Clone the Repository: On your host machine, clone the repository.
bash
git clone https://gitlab.com/exploit-database/exploitdb.git /opt/exploit-database
Run a Container with a Volume Mount: Mount the cloned directory as a volume when running your Docker container. This makes the data accessible inside the container.
bash
docker run -it --name edb-container -v /opt/exploit-database:/opt/exploit-database ubuntu:latest /bin/bash
Use SearchSploit Inside the Container: Once inside the container, you can install necessary dependencies (like git and grep) and then use the searchsploit script from the mounted directory.
bash
# Inside the container
apt update && apt install -y git
/opt/exploit-database/searchsploit <search_term>
 
Method 2: Using a Pre-built Server Image (e.g., go-exploitdb)
Several community-maintained Docker images run a server with the Exploit-DB data pre-loaded into a database (SQLite, MySQL, etc.) and provide an API for searching. 
Pull the Image: Pull an image like vuls/go-exploitdb from Docker Hub.
bash
docker pull vulsio/go-exploitdb
Run the Container: Run the image in server mode, exposing a port for access. You can use a volume mount to persist the database between container runs.
bash
mkdir /opt/exploit-db-data
docker run -d -p 1326:1326 -v /opt/exploit-db-data:/var/lib/go-exploitdb --name exploit-db-server vulsio/go-exploitdb server
Access the Datasource: The Exploit-DB data is now accessible via the API on http://localhost:1326. 
Method 3: Integrating into an Existing Security Tool (e.g., Vuls)
If you use a vulnerability scanner like Vuls, it can automatically pull and integrate Exploit-DB data as part of its setup within a Docker environment. The Vuls documentation provides specific instructions for pulling and running their integrated image. 
The best method depends on your use case: Method 1 is good for local command-line access, while Method 2 is better for programmatic access and integration with other services via an API.


--- 
Setup Open CVE in a docker that runs once every week.

-- Check if LLMs are trained using this data

These will be needed for detailed lookups.

Connect with Gopi Ram moorthy (Symmetry)


