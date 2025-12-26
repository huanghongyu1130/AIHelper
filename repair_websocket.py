
import os

file_path = r"d:\AIHelper\websocket_server.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 1. Identify the duplicate block
# We know the duplicate block starts at line 447 (1-indexed) -> 446 (0-indexed)
# and ends at line 572 (1-indexed) -> 571 (0-indexed)
# Let's verify context.
# Line 446 (0-indexed) should be indentation + """使用 LLM 從文本中提取知識 (實體和關係)"""
# Line 574 (0-indexed) should be @app.post("/api/upload-pdf")

# Adjusting for 0-based index from 'view_file' output
start_index = 446
end_index = 574 # This is where @app.post starts (line 575 in view_file)

print(f"Line at {start_index}: {lines[start_index]}")
print(f"Line at {end_index}: {lines[end_index]}")

if '@app.post("/api/upload-pdf")' in lines[end_index]:
    print("Found the correct range for deletion.")
    # Delete the block
    del lines[start_index:end_index]
else:
    print("Range check failed. Attempting to find ranges dynamically.")
    # Dynamic search
    try:
        idx_start = -1
        idx_end = -1
        for i, line in enumerate(lines):
            if i > 400 and '"""使用 LLM 從文本中提取知識 (實體和關係)"""' in line and i < 500:
                # We expect this to appear TWICE.
                # Once at 324 (index 323)
                # Once at 447 (index 446)
                # But wait, lines[start_index] corresponds to the duplicate.
                pass
        
        # Start searching for the @app.post line which marks the end of the duplicate block
        for i, line in enumerate(lines):
            if '@app.post("/api/upload-pdf")' in line:
                idx_end = i
                break
        
        # The duplicate starts after the first valid function closes.
        # The valid function closes at line 446 (index 445) with "    }"
        idx_end_of_valid = -1
        for i in range(idx_end - 1, idx_end - 200, -1):
             if lines[i].strip() == '}':
                 # This might be the end of the duplicate function? 
                 # No, we want the end of the VALID function.
                 # Let's stick to the line numbers from view_file which are usually reliable unless file changed.
                 pass
    except Exception as e:
        print(e)

# Re-verify with fixed indices if manual check logic is too complex
# Using the lines directly from previous view_file
# Line 446 in file (index 445 in list) is "    }"
# Line 447 in file (index 446 in list) is "    """使用 LLM 從文本中提取知識 (實體和關係)"""
# Line 575 in file (index 574 in list) is "@app.post("/api/upload-pdf")"

# So we want to delete from index 446 UP TO index 574 (exclusive)
# So lines[446:574] should be removed.

print(f"Removing lines {446+1} to {574}")
del lines[446:574]

# 2. Fix double try
# Scan for the double try pattern
content = "".join(lines)
content = content.replace("    try:\n    try:", "    try:")
# Also fix indentation if any
content = content.replace("    try:\n        try:", "    try:")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Repair complete.")
