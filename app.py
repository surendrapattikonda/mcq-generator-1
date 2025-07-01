from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import spacy
from collections import Counter
import random
from PyPDF2 import PdfReader
from typing import List

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

nlp = spacy.load("en_core_web_md")

def generate_mcqs(text, num_questions=5):
    if text is None:
        return []

    doc = nlp(text)
    sentences = [sent.text for sent in doc.sents]
    num_questions = min(num_questions, len(sentences))
    selected_sentences = random.sample(sentences, num_questions)

    mcqs = []
    for sentence in selected_sentences:
        sent_doc = nlp(sentence)
        nouns = [token.text for token in sent_doc if token.pos_ == "NOUN"]
        if len(nouns) < 2:
            continue

        noun_counts = Counter(nouns)
        subject = noun_counts.most_common(1)[0][0]
        question_stem = sentence.replace(subject, "______")
        answer_choices = [subject]

        distractors = list(set(nouns) - {subject})
        while len(distractors) < 3:
            distractors.append("[Distractor]")

        random.shuffle(distractors)
        for distractor in distractors[:3]:
            answer_choices.append(distractor)

        random.shuffle(answer_choices)
        correct_answer = chr(64 + answer_choices.index(subject) + 1)
        mcqs.append((question_stem, answer_choices, correct_answer))

    return mcqs

def process_pdf(file):
    text = ""
    pdf_reader = PdfReader(file.file)
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text

@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def handle_form(
    request: Request,
    text: str = Form(""),
    num_questions: int = Form(...),
    files: List[UploadFile] = File(default=None)
):
    final_text = text

    if files:
        for file in files:
            if file.filename.endswith(".pdf"):
                final_text += process_pdf(file)
            elif file.filename.endswith(".txt"):
                final_text += (await file.read()).decode("utf-8")

    if not final_text.strip():
        return HTMLResponse("Please upload a file or enter some text.", status_code=400)

    mcqs = generate_mcqs(final_text, num_questions=num_questions)
    mcqs_with_index = [(i + 1, mcq) for i, mcq in enumerate(mcqs)]
    return templates.TemplateResponse("mcqs.html", {"request": request, "mcqs": mcqs_with_index})
