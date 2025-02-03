import streamlit as st
import openai
import json
import pandas as pd
from utils import extract_text_from_file, extract_email_and_name
import authentication
import re
# -------------------- Resume Analysis Dashboard --------------------
def resume_analysis_dashboard():
    job_description = ""
    col1, col2 = st.columns(2)
    with col1:
        st.write("### Enter the Job Description:")
        job_description = st.text_area("Job Description", height=200)
    with col2:
        st.write("### Upload Resumes (PDF, DOCX, or TXT):")
        uploaded_files = st.file_uploader("Drag and drop files here",
                                          type=["pdf", "docx", "txt"],
                                          accept_multiple_files=True,
                                          key="resume_uploader")
    submit_button = st.button(
        "Submit",
        type="primary",
        disabled=not (job_description and uploaded_files)
    )
    results = []
    if submit_button:
        with st.spinner("Analyzing resumes..."):
            for uploaded_file in uploaded_files:
                try:
                    resume_text = extract_text_from_file(uploaded_file)
                    analysis = analyze_resume_with_jd(job_description, resume_text)
                    fit_score, fit, skills, explanation = parse_llm_output(analysis)
                    name, email = extract_email_and_name(resume_text)
                    results.append({
                        "Candidate Name": name,
                        "Email": email,
                        "Fit Score": fit_score,
                        "Fit": fit,
                        "Matched Skills": skills,
                        "Explanation": explanation,
                    })
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {e}")
        # Log the usage
        if results:
            authentication.log_usage(st.session_state.user_info['email'], len(uploaded_files))
    if results:
        results_sorted = sorted(results, key=lambda x: x["Fit Score"], reverse=True)
        df_sorted = pd.DataFrame(results_sorted)
        st.subheader("Ranked Candidates")
        st.dataframe(df_sorted, height=400)
        csv_data = df_sorted.to_csv(index=False).encode("utf-8")
        st.download_button(label=":inbox_tray: Download Results as CSV",
                           data=csv_data,
                           file_name="ranked_resume_analysis_results.csv",
                           mime="text/csv")
# -------------------- LLM Analysis --------------------
def analyze_resume_with_jd(jd, resume_text):
    if not resume_text.strip():
        return {"error": "Resume text is empty."}
    prompt = f"""
  You are an AI recruitment assistant analyzing resumes against job descriptions. Only match the skills explicitly listed in the Job Description and mentioned in the candidate's resume
  ### Job Description:
  {jd}
  ### Resume:
  {resume_text}
  **Scoring Criteria (0-100):**
  1. **Tech Skills (60%)**: Compare job-required technical skills with resume skills.
    - **Project-Based Skills (45%)**: Extract and match skills from project descriptions with JD requirements.
    - **General Skills (15%)**: Consider listed skills outside of projects.
    - Prioritize core skills in programming languages, frameworks, and tools mentioned in the JD.
  2. **Experience - Based on Designation (10%)**:
    - If experienced: Evaluate past roles, years in industry, and job relevance.
    - If fresher: Consider projects, internships, and specialization.
  3. **Education (20%)**:
    - Check if the degree aligns with JD requirements.
    - Consider relevant certifications and coursework.
  4. **Location (5%)**:
    - Check if the candidate is in a preferred location.
    - If fresher, **specialization + location** matters.
  5. **Additional (5%)**:
    - Extra certifications, courses, or trainings.
  **Fit Classification:**
  - **Fit: Yes** (if score ≥ 70)
  - **Fit: No** (if score < 70)
  **Matched Skills:** Extract and list relevant skills that align with the JD.
  **Explanation:** Provide a short reason why the candidate is or isn’t a good fit.
  ### Output Format (in JSON, no other text allowed):
  {{
    "Fit Score": "XX",
    "Fit": "Yes/No",
    "Matched Skills": ["Skill1", "Skill2", "Skill3"],
    "Explanation": "Candidate has strong skills in X and Y but lacks experience in Z..."
  }}
  """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "system", "content": "You are an expert AI recruitment assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0,
        )
        response_text = response["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            raise ValueError("Invalid JSON format received.")
    except Exception as e:
        return {"error": f"Error parsing LLM output: {str(e)}"}
# -------------------- Parsing LLM Output --------------------
def parse_llm_output(output):
    try:
        if "error" in output:
            return 0, "No", [], output["error"]
        return int(output.get("Fit Score", 0)), output.get("Fit", "No"), output.get("Matched Skills", []), output.get("Explanation", "No explanation provided.")
    except Exception as e:
        return 0, "No", [], f"Error parsing output: {e}"










