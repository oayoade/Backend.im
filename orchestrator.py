from fastapi import FastAPI, WebSocket
import os
import subprocess
import docker
import asyncio
import json
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
docker_client = docker.from_env()

# AWS Configuration
AWS_REGION = "us-east-1"  # Change to your AWS region
AWS_ACCOUNT_ID = ")**"  # Change to your AWS account ID
ECR_REGISTRY = f"132088440811.dkr.ecr.us-east-1.amazonaws.com"

# Kubernetes (EKS) Configuration
KUBECONFIG_PATH = "/home/ubuntu/.kube/config"  # Change if needed

# Gitea Configuration
GITEA_SERVER = "http://localhost:3000"
GITEA_REPO_OWNER = "oayoade"  # Change this if needed

# Allow all origins (or specify allowed domains)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def aws_ecr_login():
    """Authenticate with AWS ECR."""
    print("🔹 Logging in to AWS ECR...")
    subprocess.run(
        f"aws ecr get-login-password --region {AWS_REGION} | docker login --username AWS --password-stdin {ECR_REGISTRY}",
        shell=True,
        check=True,
    )

def clone_gitea_repo(username: str):
    """Clones the repository for the given username."""
    repo_url = f"{GITEA_SERVER}/{GITEA_REPO_OWNER}/{username}.git"
    repo_dir = f"/tmp/{username}-repo"

    if os.path.exists(repo_dir):
        subprocess.run(["rm", "-rf", repo_dir])

    print(f"🔹 Cloning repo: {repo_url} ...")
    subprocess.run(["git", "clone", repo_url, repo_dir], check=True)
    print(f"✅ Repository cloned to {repo_dir}.")
    return repo_dir

def build_and_push_docker_image(repo_dir: str, username: str):
    """Builds and pushes a Docker image to AWS ECR."""
    image_name = f"{ECR_REGISTRY}/{username}:latest"
    
    aws_ecr_login()
    
    # Check if Dockerfile exists, if not create one
    dockerfile_path = os.path.join(repo_dir, "Dockerfile")
    if not os.path.exists(dockerfile_path):
        print(f"⚠️ No Dockerfile found in {repo_dir}. Creating a default Dockerfile...")
        with open(dockerfile_path, "w") as f:
            f.write("""
            FROM python:3.9
            WORKDIR /app
            COPY . .
            RUN if [-f requirements.txt ]; then 1;fi
            CMD ["python", "app.py"]
            """)

    print(f"🔹 Building Docker image: {image_name} ...")
    docker_client.images.build(path=repo_dir, tag=image_name)

    print(f"🔹 Pushing Docker image: {image_name} ...")
    docker_client.images.push(image_name)

    print(f"✅ Docker image pushed: {image_name}")
    return image_name


def create_eks_namespace(username: str):
    """Creates a Kubernetes namespace for the user."""
    print(f"🔹 Creating Kubernetes namespace: {username}")
    subprocess.run(["kubectl", "create", "namespace", username], check=True)
    print(f"✅ Namespace '{username}' created.")

async def deploy_test_pod(image_name: str, username: str):
    """Deploys a test pod in the namespace and verifies its status."""
    test_pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {username}-test-pod
  namespace: {username}
spec:
  containers:
  - name: test-container
    image: {image_name}
    ports:
    - containerPort: 8000
"""
    test_pod_file = f"/tmp/{username}-test-pod.yaml"
    
    with open(test_pod_file, "w") as f:
        f.write(test_pod_yaml)

    print(f"🔹 Deploying test pod for {username} ...")
    subprocess.run(["kubectl", "apply", "-f", test_pod_file], check=True)

    # Wait and check if the test pod completes successfully
    for _ in range(30):  # Check for up to 30 seconds
        # Get the pod's status using 'kubectl describe pod'
        describe_output = subprocess.run(
            ["kubectl", "describe", "pod", f"{username}-test-pod", "-n", username],
            capture_output=True, text=True
        ).stdout

        # Check if the pod's state is "Completed"
        if "State:          Terminated" in describe_output and "Reason:       Completed" in describe_output:
            print(f"✅ Test pod for {username} completed successfully.")
            return True

        # Check if the pod is still running
        status = subprocess.run(
            ["kubectl", "get", "pod", f"{username}-test-pod", "-n", username, "-o=jsonpath={{.status.phase}}"],
            capture_output=True, text=True
        ).stdout.strip()

        if status == "Running":
            print(f"⏳ Waiting for test pod to complete... (current status: {status})")
        elif status == "Failed":
            print(f"❌ Test pod for {username} failed.")
            return False

        await asyncio.sleep(1)

    print(f"❌ Test pod for {username} did not complete within the expected time.")
    return False

def deploy_production_pod(image_name: str, username: str):
    """Deploys a production pod in the namespace."""
    prod_pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {username}-prod-pod
  namespace: {username}
spec:
  containers:
  - name: prod-container
    image: {image_name}
    ports:
    - containerPort: 8000
"""
    prod_pod_file = f"/tmp/{username}-prod-pod.yaml"
    
    with open(prod_pod_file, "w") as f:
        f.write(prod_pod_yaml)

    print(f"🔹 Deploying production pod for {username} ...")
    subprocess.run(["kubectl", "apply", "-f", prod_pod_file], check=True)
    print(f"✅ Production pod for {username} deployed successfully.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for orchestrating deployment."""
    await websocket.accept()
    print("Client connected.")
    
    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)  # Expecting JSON {"username": "johndoe"}
                username = data.get("username")

                if not username:
                    await websocket.send_text("❌ Username is required.")
                    continue

                print(f"🚀 Deploying app for user: {username} ...")

                # Step 1: Clone repo and build Docker image
                repo_dir = clone_gitea_repo(username)
                image_name = build_and_push_docker_image(repo_dir, username)

                # Step 2: Create EKS namespace
                create_eks_namespace(username)

                # Step 3: Deploy test pod
                if await deploy_test_pod(image_name, username):
                    # Step 4: Deploy production pod if test is successful
                    deploy_production_pod(image_name, username)
                    await websocket.send_text(f"✅ Deployment successful for user: {username}!")
                else:
                    await websocket.send_text(f"❌ Test pod failed. Deployment aborted for user: {username}.")

            except json.JSONDecodeError:
                await websocket.send_text("❌ Invalid message format. Expected JSON {\"username\": \"johndoe\"}")

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("Client disconnected.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
