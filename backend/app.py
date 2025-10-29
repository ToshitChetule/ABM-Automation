
from flask import Flask, request, jsonify
import os
from flask_cors import CORS
from models.llama_excel import process_excel_with_llama
from models.mistral_pdf import process_pdf_with_mistral

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# 🧠 Helper: Domain-based prompt generator
def get_domain_prompt(industry, product_type):

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

Now analyze the following SKU and return *only* valid lines in the format:
Attribute = Value

    """
    if product_type:
        base_prompt += f" for {product_type}."
    else:
        base_prompt += "."

    # Domain-based specialization
    domain_prompts = {
        "automotive": "Focus on vehicle specifications, engine type, mileage, model, fuel type, transmission, and part numbers.",
        "pharmaceuticals": "Focus on active ingredients, brand name, dosage form, strength, expiry date, and packaging.",
        "electronics": "Focus on model, power, capacity, voltage, wattage, and product specifications.",
        "food_beverages": "Focus on nutritional values, ingredients, flavor, weight, and packaging details.",
        "chemical": "Focus on chemical name, purity, CAS number, molecular weight, and application area."
    }

    # Add specific domain info
    if industry and industry.lower() in domain_prompts:
        base_prompt += " " + domain_prompts[industry.lower()]
    else:
        base_prompt += " Extract all relevant technical and descriptive attributes clearly."

    return base_prompt


@app.route("/process", methods=["POST"])
def process_file():
    """Handle file upload and send it to the correct model."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    filename = file.filename
    if not filename:
        return jsonify({"error": "Invalid filename"}), 400

    # Retrieve extra metadata from frontend
    industry = request.form.get("industry", "general")
    product_type = request.form.get("productType", "")
    domain_prompt = get_domain_prompt(industry, product_type)

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    ext = os.path.splitext(filename)[1].lower()
    print(f"\n📂 Received file: {filename} ({ext})")
    print(f"📍 Saved at: {filepath}")
    print(f"🏭 Industry: {industry}")
    print(f"🧩 Product Type: {product_type}")
    print(f"🧠 Domain Prompt: {domain_prompt}\n")

    try:
        # Choose model based on file extension
        if ext in [".xlsx", ".xls"]:
            print("🚀 Running Excel extraction using LLaMA model...\n")
            result = process_excel_with_llama(filepath, domain_prompt)
            model_used = "LLaMA"

        elif ext == ".pdf":
            print("🚀 Running PDF extraction using Mistral model...\n")
            result = process_pdf_with_mistral(filepath, domain_prompt)
            model_used = "Mistral"

        else:
            return jsonify({"error": f"Unsupported file type: {ext}"}), 400

        # ✅ Logging summary
        print("\n✅ Extraction complete.")
        print(f"🎯 Model used: {model_used}")
        print(f"📊 Columns extracted: {len(result.get('columns', []))}")
        print(f"📈 Rows extracted: {len(result.get('rows', []))}\n")

        # ✅ Return data to frontend
        return jsonify({
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "model_used": model_used,
            "industry": industry,
            "product_type": product_type
        })

    except Exception as e:
        print(f"❌ Error during processing: {str(e)}")
        return jsonify({"error": str(e)}), 500

# @app.route("/refine", methods=["POST"])
# def refine_attributes():
#     """Refine selected attributes using LLaMA with stacked chat context."""
#     try:
#         data = request.get_json()

#         selected_rows = data.get("selectedRows", [])
#         full_table = data.get("fullTable", [])
#         chat_history = data.get("chatHistory", [])

#         if not selected_rows or not chat_history:
#             return jsonify({"error": "Missing selectedRows or chatHistory"}), 400

#         print(f"🧠 Refining {len(selected_rows)} selected rows with chat history of {len(chat_history)} prompts...")

#         from models.llama_excel import refine_with_llama
#         refined_table = refine_with_llama(selected_rows, chat_history, full_table)

#         return jsonify({"rows": refined_table})

#     except Exception as e:
#         print(f"❌ Refinement error: {e}")
#         return jsonify({"error": str(e)}), 500


@app.route("/refine", methods=["POST", "OPTIONS"])
def refine_attributes():
    if request.method == "OPTIONS":
        # Preflight request handling
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

