
![image](https://github.com/user-attachments/assets/06a02b72-493f-4aff-8148-b7c61f21e3d6)


# Automated GitOps Deployment System with Python, Gitea, and Kubernetes

## Overview

This project contains two Python scripts that together automate the flow of:

- Accepting a user-submitted Python file.
- Pushing the file to a self-hosted **Gitea** server by creating a new repository.
- Cloning the repository.
- Deploying a **test Kubernetes pod** to validate the code.
- If the test succeeds, deploying a **production Kubernetes pod**.
- Communicating success/failure results over a **WebSocket** connection.

---

## Components

### 1. `code-submit.py`

- Accepts:
  - A **username**.
  - A **Python file**.
- Pushes the Python file to the self-hosted **Gitea** server.
- Creates a new repository named after the username.
- Opens a **WebSocket connection** to the orchestrator app to receive deployment status updates.

### 2. `orchestrator.py`

- Listens for WebSocket messages from `code-submit.py` app.
- Clones the newly created repository from **Gitea**.
- Creates a kubernetes namespace with the given username
- Deploys a **test Kubernetes pod** that runs the submitted code.
- If the test pod runs successfully:
  - Deploys a **production Kubernetes pod**.
- Sends a success/failure status back to `code-submit.py` app via WebSocket.

---


