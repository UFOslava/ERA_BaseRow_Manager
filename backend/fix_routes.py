import os

file_path = "backend/app/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# I need to extract the WI TEMPLATES ROUTES and put them before return app.
start_idx = content.find("    # WI TEMPLATES ROUTES")
end_idx = content.find("if __name__ == '__main__':")

if start_idx != -1 and end_idx != -1:
    wi_routes = content[start_idx:end_idx].strip()
    # remove them from the end
    content = content[:start_idx] + content[end_idx:]
    
    # insert before return app
    return_app_idx = content.rfind("    return app")
    
    if return_app_idx != -1:
        # pad wi_routes with 4 spaces for each line
        indented_routes = "\n".join("    " + line if line.strip() else "" for line in wi_routes.split("\n"))
        content = content[:return_app_idx] + indented_routes + "\n\n    return app" + content[return_app_idx+14:]
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Routes moved successfully.")
else:
    print("Routes not found.")
