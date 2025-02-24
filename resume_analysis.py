import streamlit as st
import json
import pandas as pd
from utils import extract_text_from_file
import authentication
from openai import OpenAI
import os

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("API_KEY"))


# -- Resume Analysis Dashboard --
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
        disabled=not (job_description and uploaded_files))

    # Initialize session state variables
    if "results" not in st.session_state:
        st.session_state.results = []
    if "resume_texts" not in st.session_state:
        st.session_state.resume_texts = {}
    if "interview_questions" not in st.session_state:
        st.session_state.interview_questions = None
    if "selected_candidate" not in st.session_state:
        st.session_state.selected_candidate = None
    if "interview_questions_and_answers" not in st.session_state:
        st.session_state.interview_questions_and_answers = []

    # Process resumes when the submit button is clicked
    if submit_button:
        with st.spinner("Analyzing resumes..."):
            st.session_state.results = []
            st.session_state.resume_texts = {}
            for uploaded_file in uploaded_files:
                try:
                    resume_text = extract_text_from_file(uploaded_file)
                    analysis = analyze_resume_with_jd(job_description,
                                                      resume_text)
                    fit_score, fit, skills, explanation, name, email = parse_llm_output(
                        analysis)
                    st.session_state.results.append({
                        "Candidate Name": name,
                        "Email": email,
                        "Fit Score": fit_score,
                        "Fit": fit,
                        "Matched Skills": skills,
                        "Explanation": explanation,
                    })
                    st.session_state.resume_texts[name] = resume_text
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {e}")

        # Log usage if results are generated
        if st.session_state.results:
            authentication.log_usage(st.session_state.user_info['email'],
                                     len(uploaded_files))

    # Display ranked candidates if results are available
    if st.session_state.results:
        results_sorted = sorted(st.session_state.results,
                                key=lambda x: x["Fit Score"],
                                reverse=True)
        df_sorted = pd.DataFrame(results_sorted)
        st.subheader("Ranked Candidates")
        st.dataframe(df_sorted, height=400)

        # Download results as CSV
        csv_data = df_sorted.to_csv(index=False).encode("utf-8")
        st.download_button(label=":inbox_tray: Download Results as CSV",
                           data=csv_data,
                           file_name="ranked_resume_analysis_results.csv",
                           mime="text/csv")

        # -- Interview Questions Section --
        st.subheader("Generate Interview Questions")
        candidate_names = [
            result["Candidate Name"] for result in results_sorted
        ]

        # Use session state to store the selected candidate
        selected_candidate = st.selectbox(
            "Select a candidate to generate interview questions:",
            candidate_names,
            index=candidate_names.index(st.session_state.selected_candidate)
            if st.session_state.selected_candidate else 0)
        st.session_state.selected_candidate = selected_candidate

        if selected_candidate:
            resume_text = st.session_state.resume_texts.get(
                selected_candidate, "")
            if resume_text:
                # Extract matched skills for the selected candidate
                matched_skills = next(
                    (result["Matched Skills"]
                     for result in st.session_state.results
                     if result["Candidate Name"] == selected_candidate), [])

                # Check if there are matched skills before generating questions
                if matched_skills:
                    if st.button("Generate Interview Questions and Answers"):
                        with st.spinner(
                                "Generating interview questions and answers..."
                        ):
                            st.session_state.interview_questions_and_answers = generate_interview_questions_and_answers(
                                job_description, resume_text, matched_skills)
                else:
                    st.warning(
                        "No matched skills found for this candidate. Cannot generate interview questions."
                    )

                # Display generated questions and answers
                if st.session_state.interview_questions_and_answers:
                    st.write("### Suggested Interview Questions and Answers:")
                    st.write(st.session_state.interview_questions_and_answers)


# -- LLM Analysis --
def analyze_resume_with_jd(jd, resume_text):
    if not resume_text.strip():
        return {"error": "Resume text is empty."}
    prompt = f"""
    You are an AI recruitment assistant analyzing resumes against job descriptions. Only match the skills explicitly listed in the Job Description and mentioned in the candidate's resume.

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
    **Candidate Name:** Extract the candidate's name from the resume.
    **Email:** Extract the candidate's email from the resume.

    ### Output Format (in JSON, no other text allowed):
    {{
        "Candidate Name": "Name of the Candidate",
        "Email": "Candidate's Email",
        "Fit Score": "XX",
        "Fit": "Yes/No",
        "Matched Skills": ["Skill1", "Skill2", "Skill3"],
        "Explanation": "Candidate has strong skills in X and Y but lacks experience in Z..."
    }}
    """
    try:
        response = client.chat.completions.create(
            model="o3-mini",
            messages=[{
                "role": "system",
                "content": "You are an expert AI recruitment assistant."
            }, {
                "role": "user",
                "content": prompt
            }],
            response_format={"type": "json_object"},
        )
        response_text = response.choices[0].message.content
        return json.loads(response_text)  # Directly parse the JSON response
    except Exception as e:
        return {"error": f"Error parsing LLM output: {str(e)}"}


# - Parsing LLM Output -
def parse_llm_output(output):
    try:
        if "error" in output:
            return (0, "No", [], output["error"], "Unknown", "N/A")
        # Ensure the output has the expected keys
        fit_score = int(output.get("Fit Score", 0))
        fit = output.get("Fit", "No")
        matched_skills = output.get("Matched Skills", [])
        explanation = output.get("Explanation", "No explanation provided.")
        candidate_name = output.get("Candidate Name", "Unknown")
        email = output.get("Email", "N/A")
        return (fit_score, fit, matched_skills, explanation, candidate_name,
                email)
    except Exception as e:
        st.error(f"Error parsing output: {e}")
        return 0, "No", [], f"Error parsing output: {e}", "Unknown", "N/A"


# -- Generate Interview Questions --
def generate_interview_questions_and_answers(jd, resume_text, matched_skills):
    """
    Generates basic interview questions and answers based on the matched skills from the resume and job description.

    Args:
        jd (str): The job description.
        resume_text (str): The text extracted from the candidate's resume.
        matched_skills (list): A list of skills matched between the resume and job description.

    Returns:
        str: Formatted string containing questions and suggested answers.
    """
    prompt = f"""
    You are an AI recruitment assistant tasked with generating phone interview questions and suggested answers for the TA team to assess a candidate's suitability based on the job description, the candidate's resume, and the matched skills.

    ### Job Description:
    {jd}

    ### Resume:
    {resume_text}

    ### Matched Skills:
    {', '.join(matched_skills)}

     **Instructions:**
    - Generate 10 basic interview questions specifically focused on the **project skills** mentioned in the candidate's resume.
    - Focus on the skills that the candidate has used in their projects, as described in their resume.
    - Ensure that the questions are straightforward and relevant to the practical application of these skills in real-world projects.
    - Provide clear and concise suggested answers for each question.
    - Avoid complex or advanced questions; focus on fundamental concepts and practical applications related to the project skills.

    ### Output Format (JSON):
    {{
        "questions": [
            {{
                question: "Question 1",
                "answer": "Suggested answer for Question 1"
            }},
            {{
                question: "Question 1",
                "answer": "Suggested answer for Question 2"
            }},
            ...
        ]
    }}
    """
    try:
        response = client.chat.completions.create(
            model="o3-mini",
            messages=[{
                "role": "system",
                "content": "You are an expert AI recruitment assistant."
            }, {
                "role": "user",
                "content": prompt
            }],
            response_format={"type": "json_object"},
        )
        response_json = json.loads(response.choices[0].message.content)
        questions_and_answers = response_json.get("questions", [])
        formatted_output = []
        for i, qa in enumerate(questions_and_answers):
            formatted_output.append(f"**{i+1}. {qa['question']}**\n")
            formatted_output.append(f"Suggested Answer: {qa['answer']}\n\n")
        return "\n".join(formatted_output)
    except Exception as e:
        return f"Error generating interview questions and answers: {str(e)}"
