import os
import sys
import json
import shutil
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from llm_agent.generator import generate_app_code
from github import Github  # pip install PyGithub
import time
import uuid
import subprocess

# --- Ensure parent directory is on sys.path ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# --- Initialize FastAPI ---
app = FastAPI(title="Student LLM App Deployment API")

# --- Enable CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Load environment variables ---
STUDENT_SECRET = os.getenv("STUDENT_SECRET")  # secret you shared with instructor
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")      # personal access token
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")  # your GitHub username

# --- Utility functions ---
def save_code_to_file(code: str, task: str):
    """Save generated code to a folder based on task."""
    folder = os.path.join(parent_dir, "generated_app", task)
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, "app.py")
    with open(file_path, "w") as f:
        f.write(code)
    return folder, file_path

def create_readme(task: str, brief: str):
    """Create README.md for the repo."""
    content = f"# {task}\n\n## Brief\n{brief}\n\n## Usage\nRun:\n```\nuvicorn app:app --reload\n```\n"
    return content

def add_mit_license(folder: str):
    license_text = """MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy...
"""
    with open(os.path.join(folder, "LICENSE"), "w") as f:
        f.write(license_text)

def init_git_and_push(folder: str, repo_name: str):
    """Initialize git repo, commit, push to GitHub."""
    g = Github(GITHUB_TOKEN)
    user = g.get_user()
    repo = user.create_repo(repo_name, private=False, auto_init=False)
    
    # Copy folder contents to temp dir and git init
    subprocess.run(["git", "init"], cwd=folder)
    subprocess.run(["git", "add", "."], cwd=folder)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=folder)
    subprocess.run(["git", "branch", "-M", "main"], cwd=folder)
    subprocess.run(["git", "remote", "add", "origin", repo.clone_url], cwd=folder)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=folder)

    # Enable GitHub Pages (branch main)
    repo.edit(has_pages=True)
    pages_url = f"https://{GITHUB_USERNAME}.github.io/{repo_name}/"
    return repo.clone_url, "main", pages_url

def post_to_evaluation_url(data: dict, url: str):
    """Post repo metadata to evaluation URL with retries."""
    retries = [1,2,4,8]
    for r in retries:
        try:
            resp = requests.post(url, json=data, headers={"Content-Type":"application/json"})
            if resp.status_code == 200:
                return True
        except Exception as e:
            print("Error posting to evaluation_url:", e)
        time.sleep(r)
    return False

# --- Main API endpoint ---
@app.post("/generate-app/")
async def generate_app(request: Request):
    """
    Receives a student task request JSON, verifies secret,
    generates app using AI Pipe, pushes to GitHub, and
    pings evaluation_url.
    """
    try:
        data = await request.json()
    except Exception as e:
        return {"error": f"Invalid JSON: {e}"}

    # Verify required fields
    for field in ["email","secret","task","round","nonce","brief","evaluation_url"]:
        if field not in data:
            return {"error": f"Missing field: {field}"}

    if data["secret"] != STUDENT_SECRET:
        return {"error": "Invalid secret"}

    task = data["task"]
    brief = data["brief"]

    # Generate code via AI Pipe
    code = generate_app_code(brief)

    # Save generated code
    folder, file_path = save_code_to_file(code, task)

    # Create README.md
    readme_path = os.path.join(folder, "README.md")
    with open(readme_path, "w") as f:
        f.write(create_readme(task, brief))

    # Add MIT license
    add_mit_license(folder)

    # Initialize git and push to GitHub
    repo_url, commit_sha, pages_url = init_git_and_push(folder, repo_name=task)

    # Prepare payload for evaluation_url
    payload = {
        "email": data["email"],
        "task": data["task"],
        "round": data["round"],
        "nonce": data["nonce"],
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url
    }

    # POST to evaluation_url
    success = post_to_evaluation_url(payload, data["evaluation_url"])
    if not success:
        return {"error": "Failed to post to evaluation_url after retries"}

    return {"message": "Task completed successfully", "repo_url": repo_url, "pages_url": pages_url}
