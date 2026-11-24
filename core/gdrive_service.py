"""
Google Drive Cloud Backup & Folder Synchronization Service
==========================================================
Integrates with the official Google Drive CLI ('gdrive') to:
1. Check OAuth authentication status.
2. Locate or create a dedicated application folder ('JobRadar Career Documents').
3. Upload tailored application documents directly into Google Drive.
4. Retrieve direct Google Drive view URLs for files and parent folders.
"""

import os
import re
import json
import subprocess
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


import shutil

DEFAULT_FOLDER_NAME = "JobRadar Career Documents"


def _run_gdrive_command(args: list) -> Tuple[int, str, str]:
    """Runs a gdrive CLI command safely across Windows/Linux with utf-8 encoding."""
    try:
        gdrive_bin = shutil.which("gdrive") or "gdrive"
        cmd = [gdrive_bin] + args
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
            timeout=45
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def check_auth_status() -> Dict[str, Any]:
    """
    Checks if gdrive CLI is signed in.
    """
    code, stdout, stderr = _run_gdrive_command(["auth", "status"])
    combined = (stdout + " " + stderr).lower()
    is_authed = ("status: logged in" in combined or "logged in" in combined) and ("not logged in" not in combined)
    return {
        "is_authenticated": is_authed,
        "raw_output": stdout or stderr,
        "status_text": "Authenticated" if is_authed else "Not Logged In"
    }


def get_or_create_app_folder(folder_name: str = DEFAULT_FOLDER_NAME) -> Tuple[Optional[str], Optional[str]]:
    """
    Finds the dedicated Google Drive folder or creates it if not found.
    Returns (folder_id, folder_web_url).
    """
    # 1. Search for existing folder
    code, stdout, stderr = _run_gdrive_command([
        "readonly", "search",
        "--name-exact", folder_name,
        "--type", "folder",
        "--json"
    ])

    if code == 0 and stdout:
        try:
            items = json.loads(stdout)
            if isinstance(items, list) and len(items) > 0:
                folder_id = items[0].get("id")
                if folder_id:
                    return folder_id, f"https://drive.google.com/drive/folders/{folder_id}"
            elif isinstance(items, dict) and items.get("id"):
                folder_id = items["id"]
                return folder_id, f"https://drive.google.com/drive/folders/{folder_id}"
        except Exception:
            pass

    # 2. Folder not found -> Create it
    code, stdout, stderr = _run_gdrive_command([
        "mutate", "mkdir", folder_name,
        "--json"
    ])

    if code == 0 and stdout:
        try:
            data = json.loads(stdout)
            folder_id = data.get("id")
            if folder_id:
                return folder_id, f"https://drive.google.com/drive/folders/{folder_id}"
        except Exception:
            pass

    # Fallback parsing regex if non-JSON output
    m = re.search(r"\b(?:ID:\s*|folder\s+)([a-zA-Z0-9_-]{15,})", stdout + stderr)
    if m:
        folder_id = m.group(1)
        return folder_id, f"https://drive.google.com/drive/folders/{folder_id}"

    return None, None


def upload_to_gdrive(local_file_path: str, folder_name: str = DEFAULT_FOLDER_NAME) -> Dict[str, Any]:
    """
    Uploads a local file to the specified Google Drive folder.
    Returns metadata including file_id, drive_file_url, and folder_url.
    """
    abs_path = str(Path(local_file_path).resolve())
    filename = os.path.basename(abs_path)

    if not os.path.exists(abs_path):
        return {
            "status": "error",
            "message": f"Local file not found: {abs_path}",
            "local_path": abs_path,
            "filename": filename
        }

    # Verify authentication
    auth = check_auth_status()
    if not auth["is_authenticated"]:
        return {
            "status": "needs_auth",
            "message": "Google Drive authentication required. Run 'gdrive auth login' or authorize the prompt.",
            "local_path": abs_path,
            "filename": filename
        }

    # Ensure target folder exists
    folder_id, folder_url = get_or_create_app_folder(folder_name)
    upload_args = ["mutate", "upload", abs_path]
    if folder_id:
        upload_args.extend(["--parent", folder_id])
    upload_args.append("--json")

    code, stdout, stderr = _run_gdrive_command(upload_args)
    if code != 0:
        return {
            "status": "error",
            "message": f"Upload failed: {stderr or stdout}",
            "local_path": abs_path,
            "filename": filename
        }

    file_id = None
    try:
        data = json.loads(stdout)
        file_id = data.get("id")
    except Exception:
        pass

    if not file_id:
        m = re.search(r"\(ID:\s*([a-zA-Z0-9_-]+)\)", stdout + stderr)
        if m:
            file_id = m.group(1)

    drive_file_url = f"https://drive.google.com/file/d/{file_id}/view" if file_id else folder_url

    return {
        "status": "success",
        "drive_file_id": file_id,
        "drive_file_name": filename,
        "drive_file_url": drive_file_url,
        "drive_folder_id": folder_id,
        "drive_folder_name": folder_name,
        "drive_folder_url": folder_url,
        "local_path": abs_path,
        "filename": filename
    }
