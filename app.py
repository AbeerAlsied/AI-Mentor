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
        check_same_thread=False
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


def get_conversation_history():

    cursor = conn.execute(
        """
        SELECT role, message
        FROM conversations
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (SESSION_ID,)
    )

    return cursor.fetchall()


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
# 8. OPENAI CLIENT
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
            timeout=60.0
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

        system_prompt = """
You are AI Mentor, a specialized artificial
intelligence educational assistant.

YOUR IDENTITY:
You are an expert assistant specializing ONLY
in Artificial Intelligence and its related fields.

YOUR SPECIALIZATIONS:
- Artificial Intelligence
- Machine Learning
- Deep Learning
- Neural Networks
- Generative AI
- Natural Language Processing
- Computer Vision
- Python for AI
- AI programming
- Data Science related to AI
- AI tools and applications
- AI research and projects
- AI ethics and responsible AI

IMPORTANT RULES:

1. Only answer questions related to AI and
   closely related technical topics.

2. If the user asks about an unrelated topic,
   politely explain that you specialize in
   Artificial Intelligence.

3. Never pretend that you know something
   that you do not know.

4. Explain difficult concepts in simple language
   when the user is a beginner.

5. You can write, explain, and debug AI-related
   programming code.

6. Support Arabic and English.
   Reply in the language used by the user.

7. Use clear headings and examples when useful.

8. The knowledge provided below comes from
   the user's personal knowledge library.
   Use it when relevant, but do not assume
   it is always correct.

9. If the supplied knowledge does not answer
   the question, use your existing AI knowledge.

10. Never claim that you have permanently
    retrained your underlying AI model.
    Explain that saved information is stored
    in a knowledge database.

USER KNOWLEDGE LIBRARY:

""" + knowledge_context

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        # Keep recent conversation context

        for item in history[-12:]:

            messages.append(item)

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

    except Exception as error:

        return (
            "حدث خطأ أثناء الاتصال بخدمة الذكاء الاصطناعي.\n\n"
            "يرجى المحاولة مرة أخرى.\n\n"
            f"تفاصيل الخطأ: {str(error)[:300]}"
        )


# ==========================================
# 9. SIDEBAR
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

    if st.button("💬 AI Chat", use_container_width=True):

        st.session_state.page = "Chat"

    if st.button("🧠 Knowledge Library", use_container_width=True):

        st.session_state.page = "Library"

    if st.button("📚 My Learning", use_container_width=True):

        st.session_state.page = "Learning"

    if st.button("ℹ️ About AI Mentor", use_container_width=True):

        st.session_state.page = "About"

    st.divider()

    st.markdown("### ⚙️ Settings")

    if st.button("🗑️ New Conversation", use_container_width=True):

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
        AI Mentor v1.0<br>
        Specialized AI Assistant
        </p>
        """,
        unsafe_allow_html=True
    )


# ==========================================
# 10. HOME HEADER
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

    </div>
    """,
    unsafe_allow_html=True
)


# ==========================================
# 11. CHAT PAGE
# ==========================================

if st.session_state.page == "Chat":

    st.subheader("💬 AI Assistant")

    st.caption(
        "Ask anything about Artificial Intelligence."
    )

    # Suggested questions

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
            "💻 Learn Machine Learning",
            use_container_width=True
        ):

            st.session_state.pending_question = (
                "Explain Machine Learning for beginners."
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

    # Display conversation

    for index, message in enumerate(
        st.session_state.messages
    ):

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message["role"] == "assistant":

                rating = st.feedback(
                    "thumbs",
                    key=f"rating_{index}"
                )

                if rating is not None:

                    st.session_state.feedback[index] = rating

    # User input

    question = st.chat_input(
        "Ask your AI question here..."
    )

    if "pending_question" in st.session_state:

        question = st.session_state.pop(
            "pending_question"
        )

    if question:

        # Show user message

        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        save_message("user", question)

        with st.chat_message("user"):

            st.markdown(question)

        # Generate response

        with st.chat_message("assistant"):

            with st.spinner("AI Mentor is thinking..."):

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
# 12. KNOWLEDGE LIBRARY PAGE
# ==========================================

elif st.session_state.page == "Library":

    st.subheader("🧠 Knowledge Library")

    st.write(
        "Add new information and allow AI Mentor "
        "to retrieve it during future conversations."
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

                except Exception as error:

                    st.error(
                        f"Could not read PDF: {error}"
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
# 13. LEARNING PAGE
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
# 14. ABOUT PAGE
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
        "Personal knowledge library",
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
        "AI Mentor | Version 1.0"
    )


# ==========================================
# 15. FOOTER
# ==========================================

st.divider()

st.markdown(
    """
    <p style='text-align:center;color:#8291ad;font-size:13px;'>

    🤖 AI Mentor | Your Personal AI Expert

    <br>

    Powered by Artificial Intelligence

    </p>
    """,
    unsafe_allow_html=True
)
