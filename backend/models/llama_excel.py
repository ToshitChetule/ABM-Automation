import os
import pandas as pd
import ollama
import re
from collections import defaultdict
import uuid
import threading
from progress_map import progress_map, result_map

model_name = "llama3"

def process_excel_with_llama_job(filepath, domain_prompt, job_id):
    try:
        progress_map[job_id] = 0

        if not os.path.exists(filepath):
            result_map[job_id] = {"error": f"Input file '{filepath}' not found!"}
            return

        df = pd.read_excel(filepath)
        if "SKU_Description" not in df.columns:
            result_map[job_id] = {"error": "Excel must contain column 'SKU_Description'"}
            return

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

        for i, row in df.iterrows():
            #print(f"\n🔍 Processing row {i+1}/{total}: {desc}", flush=True)
            desc = str(row["SKU_Description"]).strip()
            if not desc:
                continue
            percent_complete = int((i / total) * 100)
            progress_map[job_id] = percent_complete
            raw_output = extract_attributes(desc)
            attr_dict = parse_attributes(raw_output)

            for attr, vals in attr_dict.items():
                for v in vals:
                    global_attributes[attr].add(v)

        progress_map[job_id] = 100
        rows = []
        max_values = max((len(v) for v in global_attributes.values()), default=0)
        for attr, vals in global_attributes.items():
            rows.append([attr] + list(vals) + [""] * (max_values - len(vals)))

        columns = ["Attribute"] + [f"Value{i+1}" for i in range(max_values)]
        result_map[job_id] = {
            "columns": columns,
            "rows": rows,
            "job_id": job_id
        }
    except Exception as e:
        result_map[job_id] = {"error": str(e)}

def launch_excel_processing(filepath, domain_prompt):
    job_id = str(uuid.uuid4())
    t = threading.Thread(target=process_excel_with_llama_job, args=(filepath, domain_prompt, job_id))
    t.start()
    return job_id
