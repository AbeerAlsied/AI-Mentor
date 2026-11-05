import os
import re
import sqlite3
import hashlib
from datetime import datetime

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


# ==========================================
# 1. APP CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="AI Mentor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "ai_mentor.db"
MODEL_NAME = "gpt-4o-mini"


# ==========================================
# 2. CUSTOM CSS
# ==========================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Cairo', sans-serif;
}

.stApp {
    background-color: #0b1020;
    color: #ffffff;
}

section[data-testid="stSidebar"] {
    background-color: #11182b;
    border-right: 1px solid #26334d;
}

.hero {
    background: linear-gradient(135deg, #18284b, #34235c);
    padding: 35px;
    border-radius: 20px;
    text-align: center;
    border: 1px solid #42547c;
    margin-bottom: 25px;
}

.hero h1 {
    color: #ffffff;
    font-size: 42px;
    font-weight: 800;
}

.hero p {
    color: #c4d2ee;
    font-size: 16px;
}

.info-card {
    background: #151f35;
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #293956;
    margin-bottom: 12px;
}

.info-card h3 {
    color: #8dafff;
}

.small-text {
    color: #aab8d0;
    font-size: 13px;
}

.stButton > button {
    border-radius: 10px;
    border: 1px solid #566b9c;
    font-weight: 600;
}

.stChatMessage {
    border-radius: 14px;
}

h1, h2, h3 {
    color: #ffffff;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 3. DATABASE
# ==========================================

def get_connection():

    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False,
        timeout=30
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    return conn


conn = get_connection()


# ==========================================
# 4. SESSION MANAGEMENT
# ==========================================

if "session_id" not in st.session_state:

    st.session_state.session_id = hashlib.sha256(
        os.urandom(32)
    ).hexdigest()


if "messages" not in st.session_state:

    st.session_state.messages = []


if "page" not in st.session_state:

    st.session_state.page = "Chat"


if "feedback" not in st.session_state:

    st.session_state.feedback = {}


if "pending_question" not in st.session_state:

    st.session_state.pending_question = None


SESSION_ID = st.session_state.session_id


# ==========================================
# 5. DATABASE FUNCTIONS
# ==========================================

def save_knowledge(title, content):

    if not title.strip() or not content.strip():
        return False

    conn.execute(
        """
        INSERT INTO knowledge
        (session_id, title, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            SESSION_ID,
            title.strip(),
            content.strip(),
            datetime.now().isoformat()
        )
    )

    conn.commit()

    return True


def get_knowledge():

    cursor = conn.execute(
        """
        SELECT id, title, content, created_at
        FROM knowledge
        WHERE session_id = ?
        ORDER BY id DESC
        """,
        (SESSION_ID,)
    )

    return cursor.fetchall()


def delete_knowledge(item_id):

    conn.execute(
        """
        DELETE FROM knowledge
        WHERE id = ? AND session_id = ?
        """,
        (item_id, SESSION_ID)
    )

    conn.commit()


def save_message(role, message):

    conn.execute(
        """
        INSERT INTO conversations
        (session_id, role, message, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            SESSION_ID,
            role,
            message,
            datetime.now().isoformat()
        )
    )

    conn.commit()


# ==========================================
# 6. KNOWLEDGE SEARCH
# ==========================================

def search_knowledge(question, limit=4):

    knowledge = get_knowledge()

    if not knowledge:
        return []

    def tokenize(text):

        return set(
            re.findall(r'\w+', text.lower())
        )

    question_words = tokenize(question)

    results = []

    for item in knowledge:

        item_id, title, content, created = item

        document_words = tokenize(
            title + " " + content
        )

        common = question_words.intersection(
            document_words
        )

        score = len(common)

        if score > 0:

            results.append(
                (score, title, content)
            )

    results.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return results[:limit]


# ==========================================
# 7. PDF READER
# ==========================================

def extract_pdf_text(pdf_file):

    reader = PdfReader(pdf_file)

    pages = []

    for page in reader.pages:

        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


# ==========================================
# 8. OPENAI API
# ==========================================

def get_api_key():

    key = os.environ.get("OPENAI_API_KEY", "")

    if key:
        return key

    try:

        return st.secrets["OPENAI_API_KEY"]

    except Exception:

        return ""


api_key = get_api_key()


# ==========================================
# 9. AI SYSTEM PROMPT
# ==========================================

SYSTEM_PROMPT = """
You are AI Mentor, an intelligent educational assistant.

YOUR IDENTITY:

You are a professional AI assistant specialized ONLY
in Artificial Intelligence and closely related fields.

YOUR SPECIALIZATIONS:

- Artificial Intelligence
- Machine Learning
- Deep Learning
- Neural Networks
- Generative AI
- Natural Language Processing
- Computer Vision
- Python for AI
- AI Programming
- Data Science related to AI
- AI Tools and Applications
- AI Research
- AI Projects
- AI Ethics
- Large Language Models

==========================================
LANGUAGE AND DIALECT UNDERSTANDING
==========================================

You must support Arabic and English fluently.

1. Automatically identify the language used by the user.

2. Reply in the same language used by the user.

3. Understand Modern Standard Arabic (Fusha).

4. Understand informal Arabic and colloquial language.

5. Understand Sudanese Arabic specifically,
including expressions such as:

- يا زول
- وريني
- شنو
- كيف
- داير
- عايز
- عايزة
- ما عارف
- شديد
- كويس
- أها
- هسي
- كده
- مافي
- زاتو

6. Understand Egyptian, Gulf, Levantine,
and North African Arabic dialects.

7. Understand mixed Arabic-English messages.

8. Never force the user to write in formal Arabic.

9. If the user writes in Sudanese Arabic,
respond naturally in clear and friendly Sudanese Arabic.

10. If the user writes in English,
respond in clear and natural English.

11. Preserve technical AI terms in English
when appropriate, and explain them simply.

12. Do not criticize the user's spelling,
grammar, or dialect.

13. Understand common typing mistakes
and informal expressions using context.

==========================================
TEACHING STYLE
==========================================

1. Explain complex AI concepts simply.

2. Adapt explanations to the user's level.

3. Provide practical examples.

4. Explain technical terms clearly.

5. Help users understand AI programming.

6. Write, explain, and debug AI-related code.

7. Be patient, friendly, and educational.

8. Avoid unnecessarily complicated explanations.

==========================================
SPECIALIZATION RULES
==========================================

1. Only answer questions related to Artificial
Intelligence and closely related technical topics.

2. If a question is completely unrelated to AI,
politely explain that your specialization is AI.

3. Do not reject general programming questions
when they are clearly connected to AI projects.

4. Never pretend to know something you do not know.

5. Do not invent technical facts or references.

==========================================
PERSONAL KNOWLEDGE
==========================================

The user may provide personal information
through the Knowledge Library.

Use relevant information when answering questions.

Treat saved information as reference material,
not as guaranteed truth.

If information is missing, explain that clearly.

Never claim that you have permanently retrained
your underlying AI model.

Saved information is stored in a knowledge database
and can be retrieved when relevant.

==========================================
USER KNOWLEDGE LIBRARY
==========================================

Use the following information when relevant:

"""


# ==========================================
# 10. AI RESPONSE FUNCTION
# ==========================================

def get_ai_response(question, history):

    if not api_key:

        return (
            "⚠️ لم يتم إعداد مفتاح OpenAI API.\n\n"
            "يرجى إضافة OPENAI_API_KEY في إعدادات "
            "Secrets الخاصة بالتطبيق."
        )

    try:

        client = OpenAI(
            api_key=api_key,
            timeout=60.0,
            max_retries=2
        )

        knowledge_results = search_knowledge(
            question
        )

        knowledge_context = ""

        if knowledge_results:

            knowledge_context = "\n\n".join(
                [
                    f"Title: {title}\nInformation: {content}"
                    for score, title, content
                    in knowledge_results
                ]
            )

        system_prompt = (
            SYSTEM_PROMPT
            + knowledge_context
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        for item in history[-12:]:

            messages.append({
                "role": item["role"],
                "content": item["content"]
            })

        messages.append({
            "role": "user",
            "content": question
        })

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=messages,

            temperature=0.5,

            max_tokens=2000

        )

        answer = response.choices[0].message.content

        return answer or "لم أتمكن من إنشاء إجابة."

    except Exception:

        return (
            "حدث خطأ أثناء الاتصال بخدمة الذكاء الاصطناعي.\n\n"
            "يرجى التأكد من صحة مفتاح API "
            "واتصال الإنترنت، ثم المحاولة مرة أخرى."
        )


# ==========================================
# 11. SIDEBAR
# ==========================================

with st.sidebar:

    st.markdown(
        """
        <h1 style='text-align:center;color:#8dafff;'>
        🤖 AI Mentor
        </h1>

        <p style='text-align:center;color:#aab8d0;'>
        Your Personal AI Expert
        </p>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown("### 🧭 Navigation")

    if st.button(
        "💬 AI Chat",
        use_container_width=True
    ):

        st.session_state.page = "Chat"
        st.rerun()

    if st.button(
        "🧠 Knowledge Library",
        use_container_width=True
    ):

        st.session_state.page = "Library"
        st.rerun()

    if st.button(
        "📚 My Learning",
        use_container_width=True
    ):

        st.session_state.page = "Learning"
        st.rerun()

    if st.button(
        "ℹ️ About AI Mentor",
        use_container_width=True
    ):

        st.session_state.page = "About"
        st.rerun()

    st.divider()

    st.markdown("### ⚙️ Settings")

    if st.button(
        "🗑️ New Conversation",
        use_container_width=True
    ):

        st.session_state.messages = []

        st.rerun()

    if api_key:

        st.success("AI Engine Connected")

    else:

        st.warning("API Key Not Configured")

    st.divider()

    st.markdown(
        """
        <p class='small-text' style='text-align:center;'>
        AI Mentor v1.1<br>
        Arabic & English Support
        </p>
        """,
        unsafe_allow_html=True
    )


# ==========================================
# 12. MAIN HEADER
# ==========================================

st.markdown(
    """
    <div class="hero">

        <h1>🤖 AI Mentor</h1>

        <p>
        Your Personal Artificial Intelligence Expert
        </p>

        <p>
        Ask. Learn. Explore. Grow.
        </p>

        <p>
        العربية | English | Arabic Dialects
        </p>

    </div>
    """,
    unsafe_allow_html=True
)


# ==========================================
# 13. CHAT PAGE
# ==========================================

if st.session_state.page == "Chat":

    st.subheader("💬 AI Assistant")

    st.caption(
        "اسأل عن الذكاء الاصطناعي بأي لغة أو لهجة."
    )

    st.markdown("### ✨ Explore AI")

    col1, col2, col3 = st.columns(3)

    with col1:

        if st.button(
            "🧠 What is AI?",
            use_container_width=True
        ):

            st.session_state.pending_question = (
                "What is Artificial Intelligence?"
            )

    with col2:

        if st.button(
            "💻 تعلم Machine Learning",
            use_container_width=True
        ):

            st.session_state.pending_question = (
                "اشرح لي Machine Learning بطريقة بسيطة."
            )

    with col3:

        if st.button(
            "🐍 Python for AI",
            use_container_width=True
        ):

            st.session_state.pending_question = (
                "How is Python used in Artificial Intelligence?"
            )

    st.divider()

    # Display messages

    for index, message in enumerate(
        st.session_state.messages
    ):

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message["role"] == "assistant":

                st.feedback(
                    "thumbs",
                    key=f"rating_{index}"
                )

    # User input

    question = st.chat_input(
        "اكتب سؤالك هنا... Ask anything about AI"
    )

    if st.session_state.pending_question:

        question = st.session_state.pending_question

        st.session_state.pending_question = None

    if question:

        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        save_message("user", question)

        with st.chat_message("user"):

            st.markdown(question)

        with st.chat_message("assistant"):

            with st.spinner("AI Mentor is thinking... 🤖"):

                answer = get_ai_response(
                    question,
                    st.session_state.messages[:-1]
                )

                st.markdown(answer)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        save_message("assistant", answer)

        st.rerun()


# ==========================================
# 14. KNOWLEDGE LIBRARY
# ==========================================

elif st.session_state.page == "Library":

    st.subheader("🧠 Knowledge Library")

    st.write(
        "أضيفي معلومات جديدة ليتمكن AI Mentor "
        "من الرجوع إليها عند الإجابة."
    )

    tab1, tab2 = st.tabs([
        "✍️ Add Information",
        "📄 Upload PDF"
    ])

    with tab1:

        with st.form("knowledge_form"):

            title = st.text_input(
                "Information Title"
            )

            content = st.text_area(
                "Write your AI knowledge here",
                height=200
            )

            submitted = st.form_submit_button(
                "💾 Save Knowledge"
            )

            if submitted:

                if save_knowledge(title, content):

                    st.success(
                        "Information saved successfully!"
                    )

                else:

                    st.error(
                        "Please enter both title and content."
                    )

    with tab2:

        uploaded_file = st.file_uploader(
            "Upload an AI-related PDF",
            type=["pdf"]
        )

        if uploaded_file:

            if st.button("📥 Read and Save PDF"):

                try:

                    pdf_text = extract_pdf_text(
                        uploaded_file
                    )

                    if pdf_text.strip():

                        if save_knowledge(
                            uploaded_file.name,
                            pdf_text[:50000]
                        ):

                            st.success(
                                "PDF information saved successfully!"
                            )

                    else:

                        st.warning(
                            "No readable text found in this PDF."
                        )

                except Exception:

                    st.error(
                        "Could not read this PDF."
                    )

    st.divider()

    st.markdown("### 📚 Saved Knowledge")

    saved_items = get_knowledge()

    if saved_items:

        for item in saved_items:

            item_id, title, content, created = item

            with st.expander(f"📄 {title}"):

                st.write(content[:1500])

                st.caption(
                    f"Added: {created[:16]}"
                )

                if st.button(
                    "🗑️ Delete",
                    key=f"delete_{item_id}"
                ):

                    delete_knowledge(item_id)

                    st.rerun()

    else:

        st.info(
            "Your knowledge library is currently empty."
        )


# ==========================================
# 15. LEARNING PAGE
# ==========================================

elif st.session_state.page == "Learning":

    st.subheader("📚 My Learning")

    st.write(
        "Explore important Artificial Intelligence topics."
    )

    topics = {

        "Artificial Intelligence":
        "The science of creating machines that perform tasks requiring human intelligence.",

        "Machine Learning":
        "A field of AI that enables computers to learn patterns from data.",

        "Deep Learning":
        "A branch of Machine Learning based on multi-layer neural networks.",

        "Neural Networks":
        "Computational models inspired by the structure of the human brain.",

        "Generative AI":
        "AI systems capable of generating text, images, audio and other content.",

        "Natural Language Processing":
        "A field of AI that helps computers understand and process human language.",

        "Computer Vision":
        "A field of AI that enables machines to interpret visual information."
    }

    for topic, description in topics.items():

        with st.expander(f"🔹 {topic}"):

            st.write(description)

            if st.button(
                f"Ask AI Mentor about {topic}",
                key=f"learn_{topic}"
            ):

                st.session_state.page = "Chat"

                st.session_state.pending_question = (
                    f"Explain {topic} in detail with examples."
                )

                st.rerun()


# ==========================================
# 16. ABOUT PAGE
# ==========================================

elif st.session_state.page == "About":

    st.subheader("ℹ️ About AI Mentor")

    st.markdown(
        """
        <div class="info-card">

        <h3>🤖 What is AI Mentor?</h3>

        AI Mentor is an intelligent educational
        assistant specialized in Artificial Intelligence.

        It helps users understand AI concepts,
        explore technologies, learn programming,
        and build their own AI projects.

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### ⭐ Main Features")

    features = [

        "AI-powered conversations",

        "Arabic and English support",

        "Arabic dialect understanding",

        "Sudanese Arabic support",

        "Personal Knowledge Library",

        "PDF document reading",

        "Knowledge retrieval",

        "AI programming assistance",

        "Learning resources",

        "Conversation history"

    ]

    for feature in features:

        st.write(f"✅ {feature}")

    st.markdown("### 🎯 Our Mission")

    st.write(
        "Making Artificial Intelligence easier "
        "to understand, learn and explore."
    )

    st.divider()

    st.caption(
        "AI Mentor | Version 1.1"
    )


# ==========================================
# 17. FOOTER
# ==========================================

st.divider()

st.markdown(
    """
    <p style='text-align:center;color:#8291ad;font-size:13px;'>

    🤖 AI Mentor | Your Personal AI Expert

    <br>

    Arabic & English | Powered by AI

    </p>
    """,
    unsafe_allow_html=True
)
