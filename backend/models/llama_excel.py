import os
import pandas as pd
import ollama
import re
from collections import defaultdict
from difflib import get_close_matches

model_name = "llama3"



def process_excel_with_llama(filepath, domain_prompt=None):
    import difflib

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"❌ Input file '{filepath}' not found!")

    df = pd.read_excel(filepath)
    if "SKU_Description" not in df.columns:
        raise KeyError("Excel must contain a column named 'SKU_Description'")

    domain_context = (
        f"\nDomain Context:\n{domain_prompt}\n"
        if domain_prompt else
        "\nYou are working in a general product data context.\n"
    )

    # ---------------------
    # LLaMA prompt builder
    # ---------------------
    def extract_attributes(description):
        prompt = f"""{domain_prompt}

        SKU Description:
        {description}

        Return only the attribute-value lines, nothing else.
        """


        try:
            response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
            return response["message"]["content"].strip()
        except Exception as e:
            return f"Error: {e}"

    # ---------------------
    # Parser + Normalizer
    # ---------------------
    def parse_attributes(text):
        attr_dict = defaultdict(list)
        for line in text.splitlines():
            match = re.match(r"(.+?)\s*[:=]\s*(.+)", line.strip())
            if match:
                attr, val = match.groups()
                attr_dict[attr.strip()].append(val.strip())
        return attr_dict

    def normalize_attr_name(attr):
        attr = re.sub(r"[^a-zA-Z0-9 ]", "", attr)  # remove *, :, -, etc.
        attr = re.sub(r"\s+", " ", attr).strip()   # collapse multiple spaces
        attr = attr.title()                        # Title Case
        return attr

    # ---------------------
    # Extraction Loop
    # ---------------------
    global_attributes = defaultdict(set)
    total = len(df)
    print(f"📊 Starting extraction for {total} SKUs using LLaMA...", flush=True)

    for i, row in df.iterrows():
        desc = str(row["SKU_Description"]).strip()
        if not desc:
            continue

        print(f"\n🔍 Processing row {i+1}/{total}: {desc}", flush=True)
        raw_output = extract_attributes(desc)
        attr_dict = parse_attributes(raw_output)

        for attr, vals in attr_dict.items():
            normalized_attr = normalize_attr_name(attr)
            for v in vals:
                global_attributes[normalized_attr].add(v.strip())

    # ---------------------
    # 🔍 Fuzzy Duplicate Merge
    # ---------------------
    merged_attributes = defaultdict(set)
    all_attrs = list(global_attributes.keys())

    for attr in all_attrs:
        found_match = False
        for canonical in list(merged_attributes.keys()):
            # High similarity (≥ 0.85) or same stem (Supportphase ≈ Support Phase)
            if difflib.SequenceMatcher(None, attr.lower(), canonical.lower()).ratio() > 0.85:
                merged_attributes[canonical].update(global_attributes[attr])
                found_match = True
                break

        if not found_match:
            merged_attributes[attr].update(global_attributes[attr])

    # ---------------------
    # 🧾 Final Table
    # ---------------------
    rows = []
    max_values = max((len(v) for v in merged_attributes.values()), default=0)
    for attr, vals in merged_attributes.items():
        rows.append([attr] + list(vals) + [""] * (max_values - len(vals)))

    columns = ["Attribute"] + [f"Value{i+1}" for i in range(max_values)]

    print(f"✅ Extraction finished. Total unique merged attributes: {len(rows)}", flush=True)
    return {"columns": columns, "rows": rows}



# def refine_with_llama(selected_rows, chat_history, full_table=None):
#     """
#     Refine only selected attributes using stacked chat memory,
#     while keeping unselected rows unchanged.
#     Works even if refined attributes are renamed by the model.
#     """
#     if not selected_rows:
#         raise ValueError("No selected rows provided for refinement.")

#     refined_rows = []

#     # 🧠 Combine user feedback prompts
#     stacked_prompt = "\n".join(
#         [f"User said: {m['content']}" for m in chat_history if isinstance(m, dict) and 'content' in m]
#     )

#     for row in selected_rows:
#         if not isinstance(row, list) or len(row) == 0:
#             continue

#         attr_name = row[0].strip()
#         values = [v for v in row[1:] if isinstance(v, str) and v.strip()]
#         value_text = ", ".join(values) if values else "N/A"

#         # Build refined prompt
#         full_prompt = f"""
# You are an AI data refinement assistant. The user has already extracted attributes and now wants to refine some based on feedback.

# Conversation so far:
# {stacked_prompt}

# Refine the following attribute and its values using user feedback and context. 
# If you improve or rename the attribute, ensure it's semantically equivalent and relevant.

# Return only in this exact format:
# Attribute = Value

# Attribute: {attr_name}
# Values: {value_text}
# """

#         try:
#             response = ollama.chat(
#                 model=model_name,
#                 messages=[{"role": "user", "content": full_prompt}]
#             )

#             output = response["message"]["content"].strip()
#             match = re.match(r"(.+?)\s*[:=]\s*(.+)", output)
#             if match:
#                 new_attr = match.group(1).strip()
#                 new_val = match.group(2).strip()
#                 refined_rows.append([new_attr, new_val])
#             else:
#                 print(f"⚠️ No valid refinement pattern found for: {attr_name}")
#                 refined_rows.append(row)

#         except Exception as e:
#             print(f"⚠️ Error refining '{attr_name}': {e}")
#             refined_rows.append(row)

#     # ✅ Merge refined rows with full table — safe and fuzzy matching
#     if full_table:
#         print("🧩 Merging refined rows with full table...")
#         updated_rows = []
#         used_refinements = set()

#         for orig_row in full_table:
#             orig_attr = orig_row[0]
#             match = get_close_matches(orig_attr.lower(), [r[0].lower() for r in refined_rows], n=1, cutoff=0.85)

#             if match:
#                 matched_attr = match[0]
#                 refined_row = next((r for r in refined_rows if r[0].lower() == matched_attr), None)
#                 if refined_row:
#                     updated_rows.append(refined_row)
#                     used_refinements.add(matched_attr)
#                 else:
#                     updated_rows.append(orig_row)
#             else:
#                 updated_rows.append(orig_row)

#         # Add any refined rows that didn't match (new/renamed)
#         for r in refined_rows:
#             if r[0].lower() not in used_refinements:
#                 updated_rows.append(r)

#         print(f"✅ Refinement complete. Total updated rows: {len(refined_rows)}.")
#         return updated_rows

#     return refined_rows

def refine_with_llama(selected_rows, chat_history, full_table):
    import ollama

    prompt = (
        f"You are refining a table of attributes and values. "
        f"Here are the rows the user selected: {selected_rows}. "
        f"The user instruction is: {chat_history[-1]['content']}. "
        f"Return ONLY the corrected attribute name and value pairs "
        f"in plain JSON array format, like this:\n"
        f'[["Attribute", "Value"], ["Another Attribute", "Value"]]'
    )

    response = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
    output_text = response['message']['content']

    import json
    try:
        refined_rows = json.loads(output_text)
    except json.JSONDecodeError:
        # fallback: try to extract only attribute/value pairs from text
        lines = [line for line in output_text.split("\n") if "=" in line]
        refined_rows = []
        for line in lines:
            parts = line.split("=")
            if len(parts) >= 2:
                refined_rows.append([parts[0].strip(), "=".join(parts[1:]).strip()])

    # ✅ Replace the selected rows in the original full_table
    for i, row in enumerate(selected_rows):
        # Find index of this row in the full_table
        if row in full_table:
            idx = full_table.index(row)
            if i < len(refined_rows):
                full_table[idx] = refined_rows[i]

    return full_table

# import os
# import pandas as pd
# import ollama
# import re
# from collections import defaultdict
# from difflib import get_close_matches
# import difflib

# model_name = "llama3"


# def process_excel_with_llama(filepath, domain_prompt=None):
#     """Extract clean attribute-value pairs from SKU Excel using LLaMA."""
#     if not os.path.exists(filepath):
#         raise FileNotFoundError(f"❌ File not found: {filepath}")

#     df = pd.read_excel(filepath)
#     if "SKU_Description" not in df.columns:
#         raise KeyError("Excel must contain a column named 'SKU_Description'")

#     print(f"📊 Starting LLaMA extraction for {len(df)} rows...")

#     def extract_attributes(description):
#         prompt = f"""
# {domain_prompt}

# SKU Description:
# {description}

# Return only attribute-value lines in this format:
# Attribute = Value
# """
#         try:
#             response = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}])
#             return response["message"]["content"].strip()
#         except Exception as e:
#             print(f"⚠️ LLaMA error: {e}")
#             return ""

#     def parse_attributes(text):
#         attr_dict = defaultdict(list)
#         for line in text.splitlines():
#             match = re.match(r"(.+?)\s*[:=]\s*(.+)", line.strip())
#             if match:
#                 attr, val = match.groups()
#                 attr_dict[attr.strip()].append(val.strip())
#         return attr_dict

#     def normalize_attr_name(attr):
#         attr = re.sub(r"[^a-zA-Z0-9 ]", "", attr)
#         attr = re.sub(r"\s+", " ", attr).strip()
#         return attr.title()

#     global_attributes = defaultdict(set)

#     for i, row in df.iterrows():
#         desc = str(row["SKU_Description"]).strip()
#         if not desc:
#             continue
#         print(f"🔍 Row {i+1}: {desc[:100]}...")
#         raw_output = extract_attributes(desc)
#         attr_dict = parse_attributes(raw_output)
#         for attr, vals in attr_dict.items():
#             normalized = normalize_attr_name(attr)
#             for v in vals:
#                 global_attributes[normalized].add(v.strip())

#     # 🧠 Merge duplicates (semantic)
#     merged = defaultdict(set)
#     all_attrs = list(global_attributes.keys())

#     for attr in all_attrs:
#         found = False
#         for canonical in list(merged.keys()):
#             if difflib.SequenceMatcher(None, attr.lower(), canonical.lower()).ratio() > 0.85:
#                 merged[canonical].update(global_attributes[attr])
#                 found = True
#                 break
#         if not found:
#             merged[attr].update(global_attributes[attr])

#     rows = []
#     max_values = max((len(v) for v in merged.values()), default=0)
#     for attr, vals in merged.items():
#         rows.append([attr] + list(vals) + [""] * (max_values - len(vals)))

#     columns = ["Attribute"] + [f"Value{i+1}" for i in range(max_values)]

#     print(f"✅ Extraction finished — {len(rows)} unique attributes.")
#     return {"columns": columns, "rows": rows}


# # ==================================================================
# # 🧠 ADVANCED REFINEMENT LOGIC
# # ==================================================================
# def refine_with_llama(selected_rows, chat_history, full_table=None):
#     """
#     Smart refinement using multi-turn conversation context.
#     Only modifies selected rows, merges refined results into full table.
#     """
#     if not selected_rows or not chat_history:
#         raise ValueError("Missing selected rows or chat history")

#     latest_feedback = chat_history[-1]["content"]

#     # Combine full chat for deeper refinement context
#     stacked_context = "\n".join(
#         [f"User: {m['content']}" for m in chat_history if 'content' in m]
#     )

#     refined_rows = []

#     for row in selected_rows:
#         if not isinstance(row, list) or len(row) == 0:
#             continue

#         attr = row[0].strip()
#         values = [v for v in row[1:] if v]
#         val_text = ", ".join(values) if values else "N/A"

#         refine_prompt = f"""
# You are refining extracted attribute-value pairs based on user feedback.

# ### INPUT
# Attribute: {attr}
# Values: {val_text}

# ### USER FEEDBACK CONTEXT
# {stacked_context}

# ### TASK
# - Apply the user's most recent feedback correctly and consistently.
# - Fix, rename, or clean up attributes and values semantically.
# - Preserve correct ones unless feedback suggests otherwise.
# - Never output commentary, examples, or explanation.

# ### OUTPUT FORMAT (STRICT)
# Attribute = Value
# """

#         try:
#             response = ollama.chat(model=model_name, messages=[{"role": "user", "content": refine_prompt}])
#             output = response["message"]["content"].strip()

#             match = re.match(r"(.+?)\s*[:=]\s*(.+)", output)
#             if match:
#                 new_attr = match.group(1).strip()
#                 new_val = match.group(2).strip()
#                 refined_rows.append([new_attr, new_val])
#                 print(f"🔁 Refined → {attr} → {new_attr} = {new_val}")
#             else:
#                 print(f"⚠️ No valid pattern from model for {attr}: {output}")
#                 refined_rows.append(row)
#         except Exception as e:
#             print(f"⚠️ Refinement error for '{attr}': {e}")
#             refined_rows.append(row)

#     # 🔄 Merge refined with full table
#     if full_table:
#         updated_rows = []
#         used = set()

#         for orig_row in full_table:
#             orig_attr = orig_row[0]
#             match = get_close_matches(orig_attr.lower(), [r[0].lower() for r in refined_rows], n=1, cutoff=0.85)

#             if match:
#                 matched_attr = match[0]
#                 refined_row = next((r for r in refined_rows if r[0].lower() == matched_attr), None)
#                 if refined_row:
#                     updated_rows.append(refined_row)
#                     used.add(matched_attr)
#                 else:
#                     updated_rows.append(orig_row)
#             else:
#                 updated_rows.append(orig_row)

#         # Add new or renamed rows
#         for r in refined_rows:
#             if r[0].lower() not in used:
#                 updated_rows.append(r)

#         print(f"✅ Refinement complete. {len(refined_rows)} rows refined.")
#         return updated_rows

#     return refined_rows

