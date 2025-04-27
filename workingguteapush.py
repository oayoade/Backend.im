import os
import requests
import base64
import websockets
import asyncio
import json

# Gitea Server Configuration
GITEA_API_URL = "http://localhost:3000/api/v1"
GITEA_ACCESS_TOKEN = "c43e7712079dec3a97f99a2c04653e7f0f479347"  # Change this to your Gitea token
BRANCH_NAME = "main"

# WebSocket Configuration
WEBSOCKET_URL = "ws://localhost:9000/ws"  # Change this to your actual WebSocket URL

def create_gitea_repo(repo_name):
    """Creates a Gitea repository with the provided name."""
    repo_url = f"{GITEA_API_URL}/user/repos"  # API URL for creating repos

    headers = {"Authorization": f"token {GITEA_ACCESS_TOKEN}"}
    payload = {
        "name": repo_name,
        "private": False,
        "auto_init": True  # Initialize the repo with a README
    }

    response = requests.post(repo_url, json=payload, headers=headers)

    if response.status_code == 201:
        print(f"✅ Repository '{repo_name}' created.")
        return repo_name
    elif response.status_code == 409:
        print(f"⚠️ Repository '{repo_name}' already exists. Proceeding with upload...")
        return repo_name
    else:
        print(f"❌ Failed to create repository: {response.text}")
        return None

def push_script_to_gitea(repo_name, script_path):
    """Pushes a Python script to a Gitea repository."""
    headers = {"Authorization": f"token {GITEA_ACCESS_TOKEN}"}

    # Read and encode script content
    with open(script_path, "r") as file:
        script_content = file.read()
    encoded_content = base64.b64encode(script_content.encode()).decode()

    script_name = os.path.basename(script_path)
    file_url = f"{GITEA_API_URL}/repos/oayoade/{repo_name}/contents/{script_name}"

    # Check if the file already exists
    response = requests.get(file_url, headers=headers, params={"ref": BRANCH_NAME})

    payload = {
        "content": encoded_content,
        "message": f"Added or updated {script_name}",
        "branch": BRANCH_NAME
    }

    if response.status_code == 200:
        # File exists, extract SHA for updating
        sha = response.json().get("sha")
        if sha:
            payload["sha"] = sha  # Required for updating

    # Upload the file
    response = requests.post(file_url, json=payload, headers=headers)

    if response.status_code in [200, 201]:
        print(f"✅ Successfully pushed {script_name} to repo '{repo_name}'.")
        return True
    else:
        print(f"❌ Failed to push {script_name}: {response.text}")
        return False

async def send_websocket_message(username, repo_name):
    """Sends repo details via WebSocket and waits for a response."""
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        data = {"username": username, "repo_name": repo_name}
        await websocket.send(json.dumps(data))
        print(f"📨 Sent WebSocket message: {data}")

        # Wait for response
        response = await websocket.recv()
        print(f"📩 Deployment Response: {response}")

if __name__ == "__main__":
    username = input("Enter your username (used as repo name): ").strip()
    script_path = input("Enter the path to your Python script: ").strip()

    if not username:
        print("❌ Username is required.")
    elif not os.path.exists(script_path) or not script_path.endswith(".py"):
        print("❌ Invalid script path. Please provide a valid Python file.")
    else:
        repo_name = create_gitea_repo(username)  # Use username as repo name
        if repo_name:
            if push_script_to_gitea(repo_name, script_path):
                asyncio.run(send_websocket_message(username, repo_name))