import sys, os

def extract_blueprint(header, bp_name, out_file):
    bridge_path = "application/bridge_server.py"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(bridge_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if header in line:
            start_idx = i - 1
            break
            
    if start_idx != -1:
        for i in range(start_idx + 10, len(lines)):
            if lines[i].startswith("# ====================================================================="):
                if header not in lines[i]:
                    end_idx = i
                    break
                    
    if start_idx == -1 or end_idx == -1:
        print(f"Failed to find bounds for {header}")
        return False
        
    extracted = lines[start_idx:end_idx]
    
    # generate blueprint file
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context\n")
        f.write("import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil\n")
        f.write("import urllib.request as _urllib_req\n")
        f.write("from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL\n\n")
        f.write(f"{bp_name} = Blueprint('{bp_name}', __name__)\n\n")
        
        for line in extracted:
            line = line.replace("@app.route", f"@{bp_name}.route")
            line = line.replace("@app.before_request", f"@{bp_name}.before_request")
            line = line.replace("@app.after_request", f"@{bp_name}.after_request")
            f.write(line)
            
    # patch bridge_server.py
    new_lines = lines[:start_idx] + ["\n# --- Refactored to " + out_file + " ---\n"] + lines[end_idx:]
    
    # Add registration before app.run
    entry_idx = -1
    for i, line in enumerate(new_lines):
        if "app.run(" in line:
            entry_idx = i
            break
            
    if entry_idx != -1:
        mod_name = os.path.basename(out_file)[:-3]
        new_lines.insert(entry_idx, f"    try:\n        from routes.{mod_name} import {bp_name}\n        app.register_blueprint({bp_name})\n    except Exception as e:\n        print(f'Registration failed: {{e}}')\n")
    
    with open(bridge_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        
    # test syntax
    import importlib.util
    spec = importlib.util.spec_from_file_location(bp_name, out_file)
    try:
        mod = importlib.util.module_from_spec(spec)
        compile(open(out_file, "r").read(), out_file, 'exec')
        print(f"Success extracting {bp_name}!")
        return True
    except SyntaxError as e:
        print(f"Syntax error in {out_file}: {e}")
        with open(bridge_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.remove(out_file)
        return False

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("header", help="Header to look for")
parser.add_argument("bp_name", help="Blueprint variable name")
parser.add_argument("out_file", help="Output python file path")
args = parser.parse_args()

extract_blueprint(args.header, args.bp_name, args.out_file)
