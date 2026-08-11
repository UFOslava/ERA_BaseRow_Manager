import os
import re
import json
from datetime import datetime
from docx import Document
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Cm

KNOWN_TOKENS = {
    "item_pn", "pn", "revision", "description", "ext_pn", "date",
    "step_number", "main_action", "instruction_text",
    "step_image", "item_image",
    "steps", "step", "part", "part_name", "part_qty",
    "tool", "tool_name", "tool_qty", "unique_tools",
    "parts", "tools",
    "for", "endfor", "if", "endif"
}

def scan_template(file_path):
    doc = Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text += cell.text + "\n"
                
    # Find all {{ ... }} and {% ... %}
    pattern = re.compile(r'\{\{(.*?)\}\}|\{\%(.*?)\%\}')
    matches = pattern.findall(text)
    
    found_tokens = set()
    invalid_tokens = set()
    
    for match in matches:
        token = match[0] if match[0] else match[1]
        token = token.strip()
        if not token:
            continue
            
        # Strip pipe filters
        if "|" in token:
            token = token.split("|")[0].strip()
            
        # Handle loops
        parts = token.split()
        if parts:
            if parts[0] in ("for", "endfor", "if", "endif"):
                found_tokens.add(parts[0])
                if parts[0] == "for" and len(parts) >= 4:
                    # e.g., for step in steps
                    found_tokens.add(parts[1])
                    found_tokens.add(parts[3])
                    if parts[3] not in KNOWN_TOKENS and not parts[3].startswith("step."):
                        invalid_tokens.add(parts[3])
                continue
                
        # Basic variable
        base_token = parts[0] if parts else token
        # Strip object dots
        if "." in base_token:
            base_token = base_token.split(".")[0]
            
        found_tokens.add(base_token)
        if base_token not in KNOWN_TOKENS:
            invalid_tokens.add(base_token)
            
    return {
        "valid": len(invalid_tokens) == 0,
        "found": list(found_tokens),
        "invalid": list(invalid_tokens)
    }

def evaluate_instruction_text(step):
    text = step.get("Instruction Text", "")
    parts = step.get("parts", [])
    tools = step.get("tools", [])
    
    if "[PARTS]" in text:
        parts_str = ", ".join([f"{p['part_name']} ({p['part_qty']}x)" for p in parts])
        text = text.replace("[PARTS]", parts_str)
        
    if "[TOOLS]" in text:
        tools_str = ", ".join([f"{t['tool_name']}" for t in tools])
        text = text.replace("[TOOLS]", tools_str)
        
    return text

def render_wi_document(template_path, output_path, item, steps):
    doc = DocxTemplate(template_path)
    
    # Process unique tools
    all_tools = {}
    for step in steps:
        for tool in step.get("tools", []):
            tname = tool["tool_name"]
            all_tools[tname] = all_tools.get(tname, 0) + tool["tool_qty"]
            
    unique_tools = [{"tool_name": name, "tool_qty": qty} for name, qty in all_tools.items()]
    
    # Prepare steps context
    context_steps = []
    for i, step in enumerate(steps):
        # We need absolute path for image if exists, but we might not have it locally
        # The prompt says "step_image: InlineImage(doc, step_img_path, width=Cm(image_width)) or ''"
        # We'll skip actual image rendering for now unless paths are available, or mock it if empty
        step_ctx = {
            "step_number": i + 1,
            "main_action": step.get("Main Action", ""),
            "instruction_text": evaluate_instruction_text(step),
            "parts": [{"part_name": p["part_name"], "part_qty": p["part_qty"]} for p in step.get("parts", [])],
            "tools": [{"tool_name": t["tool_name"], "tool_qty": t["tool_qty"] if t["tool_qty"] > 1 else ""} for t in step.get("tools", [])]
        }
        
        # Image handling mocked
        step_image_path = step.get("local_image_path")
        if step_image_path and os.path.exists(step_image_path):
            step_ctx["step_image"] = InlineImage(doc, step_image_path, width=Cm(8))
        else:
            step_ctx["step_image"] = ""
            
        context_steps.append(step_ctx)
        
    context = {
        "item_pn": item.get("Part Number", ""),
        "pn": item.get("Part Number", ""),
        "revision": item.get("Revision", ""),
        "description": item.get("Description", ""),
        "ext_pn": item.get("External PN", ""),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "item_image": "",
        "steps": context_steps,
        "unique_tools": unique_tools
    }
    
    item_image_path = item.get("local_image_path")
    if item_image_path and os.path.exists(item_image_path):
        context["item_image"] = InlineImage(doc, item_image_path, width=Cm(8))
        
    doc.render(context)
    doc.save(output_path)
    return context
