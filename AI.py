
import io
import json
import re
from PyPDF2 import PdfReader
from docx import Document
from openai import OpenAI
from google.colab import files
from sklearn.metrics import precision_score, recall_score, f1_score

# --- Initialize OpenAI ---
api_key = input("Paste your OpenAI API key: ").strip()
client = OpenAI(api_key=api_key)
model_choice = "gpt-4"

# --- Extract text from file ---
def extract_text(file_bytes, filename):
    try:
        if filename.lower().endswith('.pdf'):
            print(f"Reading PDF: {filename}")
            return "\n".join([page.extract_text() or "" for page in PdfReader(io.BytesIO(file_bytes)).pages])
        elif filename.lower().endswith('.docx'):
            print(f"Reading DOCX: {filename}")
            return "\n".join([para.text for para in Document(io.BytesIO(file_bytes)).paragraphs])
        elif filename.lower().endswith('.txt'):
            print(f"Reading TXT: {filename}")
            return file_bytes.decode('utf-8')
        else:
            print(f"Unsupported file type: {filename}")
            return None
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return None

# --- Analyze resume vs JD using OpenAI ---
def analyze(cv_text, jd_text):
    try:
        prompt = f"""Compare the following resume and job description. Return ONLY a valid JSON with these keys:
- fit_score (number from 0-100)
- matching_skills: list of 3 items, each like {{ "skill": "...", "percentage": number }}
- missing_skills: list of 3 strings
- questions: list of 3 items, each like {{ "question": "...", "options": ["...", "...", "...", "..."], "correct": [0, 2] }}

Resume:
{cv_text[:4000]}

Job Description:
{jd_text[:4000]}
"""

        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are an expert resume and job match evaluator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

        content = response.choices[0].message.content
        match = re.search(r'\{.*\}', content, re.DOTALL)
        json_str = match.group(0) if match else content
        return json.loads(json_str)

    except Exception as e:
        print("Error during OpenAI API call or parsing:", e)
        return {"fit_score": 0, "matching_skills": [], "missing_skills": [], "questions": []}

# --- Main ---
def main():
    print("Step 1: Upload your resume")
    uploaded = files.upload()
    cv_file = next(iter(uploaded))
    cv_text = extract_text(uploaded[cv_file], cv_file)
    if not cv_text:
        print("Failed to extract resume text.")
        return

    results = []
    print("\nNow upload 3 job descriptions one by one")

    for i in range(1, 4):
        print(f"\nUpload Job Description {i}")
        uploaded = files.upload()
        jd_file = next(iter(uploaded))
        jd_text = extract_text(uploaded[jd_file], jd_file)

        if not jd_text:
            print(f"Skipping JD {i}, failed to extract.")
            results.append({"fit_score": 0})
            continue

        print(f"Analyzing JD {i}...")
        result = analyze(cv_text, jd_text)
        results.append(result)

    # --- Show results ---
    threshold = 65
    predicted = []
    print("\n--- Evaluation Results ---")

    for i, res in enumerate(results, 1):
        score = res.get("fit_score", 0)
        predicted.append(1 if score >= threshold else 0)

        print(f"\nJD {i} Fit Score: {score}%")
        print("Matching Skills:")
        for skill in res.get("matching_skills", []):
            print(f"- {skill.get('skill')}: {skill.get('percentage')}%")
        print("Missing Skills:", res.get("missing_skills", []))

    # --- Evaluation Metrics ---
    ground_truth = [1, 0, 1]  # <- EDIT THIS AS NEEDED
    print("\nPredicted Labels:", predicted)
    print("Ground Truth Labels:", ground_truth)

    precision = precision_score(ground_truth, predicted)
    recall = recall_score(ground_truth, predicted)
    f1 = f1_score(ground_truth, predicted)

    print(f"\nPrecision: {precision:.2f}")
    print(f"Recall:    {recall:.2f}")
    print(f"F1 Score:  {f1:.2f}")

# Run it
if __name__ == "__main__":
    main()
