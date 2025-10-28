import os
import pandas as pd
import ollama
import re
from collections import defaultdict
from difflib import get_close_matches

model_name = "llama3"

# -------------------------------------------------------------
# Excel Processing using LLaMA
# -------------------------------------------------------------
def process_excel_with_llama(filepath, domain_prompt=None):
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

    def extract_attributes(description):
        prompt = f"""
        You are an expert IT product data analyst and SKU intelligence system with deep understanding of how global software, hardware, and cloud vendors structure their SKUs.

        {domain_context}

        Given a single SKU description, extract *all possible* attributes and their values using the format:
        Attribute = Value

        Rules:
        1. Output strictly in the format `Attribute = Value` (no bullets or extra text)
        2. Expand abbreviations and decode structured SKUs using domain expertise
        3. Combine multiple values under same attribute with commas
        4. Strictly, there should be no duplicate values

        SKU: "{description}"
        """
        try:
            response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
            return response["message"]["content"].strip()
        except Exception as e:
            return f"Error: {e}"

    def parse_attributes(text):
        attr_dict = defaultdict(list)
        for line in text.splitlines():
            match = re.match(r"(.+?)\s*[:=]\s*(.+)", line.strip())
            if match:
                attr, val = match.groups()
                attr_dict[attr.strip()].append(val.strip())
        return attr_dict

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
            for v in vals:
                global_attributes[attr].add(v)

    rows = []
    max_values = max((len(v) for v in global_attributes.values()), default=0)
    for attr, vals in global_attributes.items():
        rows.append([attr] + list(vals) + [""] * (max_values - len(vals)))

    columns = ["Attribute"] + [f"Value{i+1}" for i in range(max_values)]
    print(f"✅ Extraction finished. Total attributes: {len(rows)}", flush=True)
    return {"columns": columns, "rows": rows}

def refine_with_llama(selected_rows, chat_history, full_table=None):
    """
    Refine only selected attributes using stacked chat memory,
    while keeping unselected rows unchanged.
    Works even if refined attributes are renamed by the model.
    """
    if not selected_rows:
        raise ValueError("No selected rows provided for refinement.")

    refined_rows = []

    # 🧠 Combine user feedback prompts
    stacked_prompt = "\n".join(
        [f"User said: {m['content']}" for m in chat_history if isinstance(m, dict) and 'content' in m]
    )

    for row in selected_rows:
        if not isinstance(row, list) or len(row) == 0:
            continue

        attr_name = row[0].strip()
        values = [v for v in row[1:] if isinstance(v, str) and v.strip()]
        value_text = ", ".join(values) if values else "N/A"

        # Build refined prompt
        full_prompt = f"""
You are an AI data refinement assistant. The user has already extracted attributes and now wants to refine some based on feedback.

Conversation so far:
{stacked_prompt}

Refine the following attribute and its values using user feedback and context. 
If you improve or rename the attribute, ensure it's semantically equivalent and relevant.

Return only in this exact format:
Attribute = Value

Attribute: {attr_name}
Values: {value_text}
"""

        try:
            response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": full_prompt}]
            )

            output = response["message"]["content"].strip()
            match = re.match(r"(.+?)\s*[:=]\s*(.+)", output)
            if match:
                new_attr = match.group(1).strip()
                new_val = match.group(2).strip()
                refined_rows.append([new_attr, new_val])
            else:
                print(f"⚠️ No valid refinement pattern found for: {attr_name}")
                refined_rows.append(row)

        except Exception as e:
            print(f"⚠️ Error refining '{attr_name}': {e}")
            refined_rows.append(row)

    # ✅ Merge refined rows with full table — safe and fuzzy matching
    if full_table:
        print("🧩 Merging refined rows with full table...")
        updated_rows = []
        used_refinements = set()

        for orig_row in full_table:
            orig_attr = orig_row[0]
            match = get_close_matches(orig_attr.lower(), [r[0].lower() for r in refined_rows], n=1, cutoff=0.85)

            if match:
                matched_attr = match[0]
                refined_row = next((r for r in refined_rows if r[0].lower() == matched_attr), None)
                if refined_row:
                    updated_rows.append(refined_row)
                    used_refinements.add(matched_attr)
                else:
                    updated_rows.append(orig_row)
            else:
                updated_rows.append(orig_row)

        # Add any refined rows that didn't match (new/renamed)
        for r in refined_rows:
            if r[0].lower() not in used_refinements:
                updated_rows.append(r)

        print(f"✅ Refinement complete. Total updated rows: {len(refined_rows)}.")
        return updated_rows

    return refined_rows