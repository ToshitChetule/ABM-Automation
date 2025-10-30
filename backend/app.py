from flask import Flask, request, jsonify
import os
from flask_cors import CORS
from models.llama_excel import launch_excel_processing
from models.mistral_pdf import process_pdf_with_mistral
from progress_map import progress_map, result_map

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_domain_prompt(industry, product_type):
    """You are a precise and domain-aware SKU data extraction assistant.
    Your goal is to read one product's SKU description and output a clean,
    structured list of attributes and their values.

    ### OUTPUT FORMAT (STRICT)
    Each line must be exactly:
    Attribute = Value

    ### RULES
    1. Do not include any headings, bullets, or sentences.
    2. Each attribute must appear only once. Merge duplicates (semantic or textual).
    3. If multiple values exist for the same attribute, separate them with commas (",").
    4. Attribute names must be in Title Case and human-readable (e.g., "Operating System", "CPU Count").
    5. Do not invent values. Only extract those clearly mentioned or strongly implied.
    6. If a value looks like a list or range, normalize it (e.g., "1-2", "64 GB, 128 GB").
    7. Never output commentary like "Here is the result" or "Based on description".
    8. Each line should be clean: no quotes, colons, dashes, or extra text.
    9. Focus on technical and descriptive attributes only (not marketing text or pricing).

    ### CONTEXT
    Industry: {industry if industry else "general"}
    Product Type: {product_type if product_type else "unspecified"}

    Now analyze the following SKU and return *only* valid lines in the format:
    Attribute = Value
    """
    
    
    base_prompt = f"""You are a precise and domain-aware SKU data extraction assistant.
Your goal is to read one product's SKU description and output a clean,
structured list of attributes and their values.

### OUTPUT FORMAT (STRICT)
Each line must be exactly:
Attribute = Value

### RULES
1. Do not include any headings, bullets, or sentences.
2. Each attribute must appear only once. Merge duplicates (semantic or textual).
3. If multiple values exist for the same attribute, separate them with commas (",").
4. Attribute names must be in Title Case and human-readable (e.g., "Operating System", "CPU Count").
5. Do not invent values. Only extract those clearly mentioned or strongly implied.
6. If a value looks like a list or range, normalize it (e.g., "1-2", "64 GB, 128 GB").
7. Never output commentary like "Here is the result" or "Based on description".
8. Each line should be clean: no quotes, colons, dashes, or extra text.
9. Focus on technical and descriptive attributes only (not marketing text or pricing).

### CONTEXT
Industry: {industry if industry else "general"}
Product Type: {product_type if product_type else "unspecified"}

IBM is a global leader in the Technology, Media & Telecommunications industry. It provides solutions including AI/ML platforms (WatsonX), Hybrid Multicloud 
(Red Hat OpenShift), Integration Software (WebMethods), IT Infrastructure, Automation (Instana), and Security Solutions. IBM’s products and services target 
Fortune 1000 and regulated industries, and are delivered via enterprise contracts and managed services worldwide. Pricing models include consumption-based, 
user-based, subscription, and project-based approaches.
 
When analyzing SKU descriptions, you may encounter these important attributes (definitions included for clarity):
License Model: How usage rights are provided (e.g., subscription, perpetual)
Deployment Method: How/where delivered or hosted (cloud, on-premises, SaaS)
Hyperscaler: The underlying cloud platform (e.g., AWS, Azure, GCP)
Model: The specific product designation or version
Edition: The feature tier or version (Standard, Enterprise, Premium)
Support Type: Level of tech support included (Basic, 24x7)
Environment Type: Usage setting (production, development, test)
Quantity: Number of units billed (users, vCPUs, GBs)
Contract Length: Duration of the agreement (e.g., 12 months)
Billing Frequency: How often billing occurs (monthly, annually)
Billing Method: Charging approach (consumption, flat fee)
Licensing Term: License validity period (annual, perpetual)
Chargeable Unit: Metric for billing (user, API call, vCPU)
Overage Premium Rate: Charge rate for excess usage
Service Level Agreements (SLA): Committed uptime/performance levels
SLA Credits: Compensation if SLAs are not met
Renewal Approach: How renewal is handled (manual, automatic)
Route to Market: Channel for sale (direct, partner)
Pricing Model: Structure for pricing (subscription, pay-as-you-go)
 
Task:
Given a SKU Description, extract all possible attributes and their corresponding values. Attributes may include (but are not limited to) features, 
technical specifications, licensing details, components, and billing methods. For each attribute, list all relevant values.
 
Format:
Output should be in the following format:
Attribute1  -  Value11    Value12    Value13
Attribute2  -  Value21    Value22    Value23    Value24
(No extra explanations or commentary—just the attributes and values organized in a tabular format as shown.)
 
Example:
Input SKU Description:
"IBM WatsonX AI/ML Platform, Consumption-based billing, Supports Red Hat OpenShift; Includes 10 vCPUs, 100GB Storage, Annual Subscription."
 
Output:
Billing Method: Consumption-based, Annual Subscription
Core Product: WatsonX, Red Hat OpenShift
CPUs: 10 vCPUs
Storage: 100GB
 
Instructions for the Model:
Carefully read each SKU Description. Identify all distinct attributes and list every value associated with each attribute, as shown in the example above. If multiple values exist for a single attribute, include each one in the same row.

Now analyze the following SKU and return *only* valid lines in the format:
Attribute = Value

    """
    if product_type:
        base_prompt += f" for {product_type}."
    else:
        base_prompt += "."
    domain_prompts = {
        "automotive": "Focus on vehicle specifications, engine type, mileage, model, fuel type, transmission, and part numbers.",
        "pharmaceuticals": "Focus on active ingredients, brand name, dosage form, strength, expiry date, and packaging.",
        "electronics": "Focus on model, power, capacity, voltage, wattage, and product specifications.",
        "food_beverages": "Focus on nutritional values, ingredients, flavor, weight, and packaging details.",
        "chemical": "Focus on chemical name, purity, CAS number, molecular weight, and application area."
    }
    if industry and industry.lower() in domain_prompts:
        base_prompt += " " + domain_prompts[industry.lower()]
    else:
        base_prompt += " Extract all relevant technical and descriptive attributes clearly."
    return base_prompt

@app.route("/process", methods=["POST"])
def process_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    filename = file.filename
    if not filename:
        return jsonify({"error": "Invalid filename"}), 400

    industry = request.form.get("industry", "general")
    product_type = request.form.get("productType", "")
    domain_prompt = get_domain_prompt(industry, product_type)

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext in [".xlsx", ".xls"]:
            job_id = launch_excel_processing(filepath, domain_prompt)
            model_used = "LLaMA"
            # Do NOT wait for results! Return immediately with job_id:
            return jsonify({
                "job_id": job_id,
                "model_used": model_used,
                "industry": industry,
                "product_type": product_type,
                # DO NOT send columns/rows yet!
            }), 202

        elif ext == ".pdf":
            # For simplicity, keep old synchronous logic
            job_id = str(uuid.uuid4())
            result = process_pdf_with_mistral(filepath, domain_prompt, job_id=job_id)
            model_used = "Mistral"
            return jsonify({
                "columns": result.get("columns", []),
                "rows": result.get("rows", []),
                "model_used": model_used,
                "industry": industry,
                "product_type": product_type,
                "job_id": job_id,
            })

        else:
            return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    percent_complete = progress_map.get(job_id, 0)
    return jsonify({'progress': percent_complete})

@app.route('/result/<job_id>', methods=['GET'])
def get_result(job_id):
    if job_id in result_map:
        return jsonify(result_map[job_id])
    else:
        return jsonify({"error": "Job not completed yet"}), 202

@app.route("/refine", methods=["POST", "OPTIONS"])
def refine_attributes():
    if request.method == "OPTIONS":
        return jsonify({"status": "OK"}), 200
    try:
        data = request.get_json()
        selected_rows = data.get("selectedRows")
        full_table = data.get("fullTable")
        chat_history = data.get("chatHistory")
        if not selected_rows or not chat_history:
            return jsonify({"error": "Missing selectedRows or chatHistory"}), 400
        from models.llama_excel import refine_with_llama
        refined_rows = refine_with_llama(selected_rows, chat_history, full_table)
        return jsonify({"rows": refined_rows}), 200
    except Exception as e:
        print(f"❌ Refinement error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
