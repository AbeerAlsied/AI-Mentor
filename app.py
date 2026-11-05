import os
import re
import sqlite3
import uuid
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
# 2. PURPLE THEME
# ==========================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Cairo', sans-serif;
}

.stApp {
    background: linear-gradient(
        135deg,
        #100b24 0%,
        #191033 50%,
        #241345 100%
    );
    color: #ffffff;
}

header {
    background: transparent !important;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg,
        #21133f,
        #120d29
    );
    border-right: 1px solid #513b82;
}

section[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

.hero {
    background: linear-gradient(
        120deg,
        #38206e,
        #6337a5,
        #8a55c7
    );
    padding: 38px 20px;
    border-radius: 25px;
    text-align: center;
    border: 1px solid #a58add;
    box-shadow: 0 10px 35px rgba(0,0,0,0.3);
    margin-bottom: 30px;
}

.hero h1 {
    color: white;
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 8px;
}

.hero h3 {
    color: #eee5ff;
    font-size: 19px;
}

.hero p {
    color: #f5edff;
    font-size: 16px;
}

.section-title {
    color: #d9c2ff;
    font-size: 25px;
    font-weight: 800;
    margin-top: 20px;
}

.info-card {
    background: linear-gradient(
        135deg,
        #2c1b50,
        #44266e
    );
    border: 1px solid #7656a8;
    border-radius: 18px;
    padding: 20px;
    margin-bottom: 15px;
}

.info-card h3 {
    color: #e4d2ff;
}

.info-card p {
    color: #f0eaff;
}

.stButton > button {
    background: linear-gradient(
        90deg,
        #7544bb,
        #a16bdf
    );
    color: white !important;
    border: none;
    border-radius: 12px;
    font-weight: bold;
    padding: 9px 18px;
    transition: 0.3s;
}

.stButton > button:hover {
    background: linear-gradient(
        90deg,
        #9361d3,
        #bb8cf0
    );
    border: 1px solid white;
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] {
    background-color: #21163c !important;
    color: white !important;
    border: 1px solid #7956ad !important;
    border-radius: 12px !important;
}

.stTextInput label,
.stTextArea label,
.stSelectbox label {
    color: #e3d5ff !important;
}

.stChatMessage {
    background: #291b46;
    border: 1px solid #60458c;
    border-radius: 15px;
}

[data-testid="stMetric"] {
    background: #2b1c49;
    border: 1px solid #694b96;
    padding: 15px;
    border-radius: 15px;
}

.stTabs [data-baseweb="tab"] {
    color: white;
}

hr {
    border-color: #674a91;
}

footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 3. DATABASE
# ==========================================

def get_connection():
    return sqlite3.connect(DB_NAME, timeout=30)


def initialize_database():

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                rating INTEGER,
                created_at TEXT
            )
        """)


initialize_database()


# ==========================================
# 4. SESSION MANAGEMENT
# ==========================================

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# ==========================================
# 5. DATABASE FUNCTIONS
# ==========================================

def save_message(role, content):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO conversations
            (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            st.session_state.session_id,
            role,
            content,
            datetime.now().isoformat()
        ))


def load_messages():

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT role, content
            FROM conversations
            WHERE session_id = ?
            ORDER BY id
        """, (st.session_state.session_id,)).fetchall()

    return [
        {"role": row[0], "content": row[1]}
        for row in rows
    ]


def save_knowledge(title, content):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO knowledge
            (title, content, created_at)
            VALUES (?, ?, ?)
        """, (
            title,
            content,
            datetime.now().isoformat()
        ))


def get_knowledge():

    with get_connection() as conn:

        return conn.execute("""
            SELECT id, title, content, created_at
            FROM knowledge
            ORDER BY id DESC
        """).fetchall()


def delete_knowledge(item_id):

    with get_connection() as conn:

        conn.execute(
            "DELETE FROM knowledge WHERE id = ?",
            (item_id,)
        )


def save_feedback(rating):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO feedback
            (session_id, rating, created_at)
            VALUES (?, ?, ?)
        """, (
            st.session_state.session_id,
            rating,
            datetime.now().isoformat()
        ))


# ==========================================
# 6. KNOWLEDGE SEARCH
# ==========================================

def search_knowledge(question):

    items = get_knowledge()

    question_words = set(
        re.findall(r'\w+', question.lower())
    )

    results = []

    for item in items:

        title = item[1]
        content = item[2]

        text = (title + " " + content).lower()

        words = set(re.findall(r'\w+', text))

        score = len(question_words.intersection(words))

        if score > 0:
            results.append((score, title, content))

    results.sort(reverse=True, key=lambda x: x[0])

    selected = results[:3]

    return "\n\n".join([
        f"العنوان: {title}\nالمحتوى: {content[:4000]}"
        for score, title, content in selected
    ])


# ==========================================
# 7. PDF READER
# ==========================================

def read_pdf(uploaded_file):

    reader = PdfReader(uploaded_file)

    pages = []

    for page in reader.pages:

        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


# ==========================================
# 8. OPENAI CONFIGURATION
# ==========================================

def get_api_key():

    try:
        return st.secrets["OPENAI_API_KEY"]

    except Exception:
        return os.getenv("OPENAI_API_KEY")


def get_ai_response(question, history):

    api_key = get_api_key()

    if not api_key:
        return (
            "مفتاح OpenAI API غير موجود. "
            "أضيفي OPENAI_API_KEY في Streamlit Secrets."
        )

    try:

        client = OpenAI(api_key=api_key)

        knowledge_context = search_knowledge(question)

        system_prompt = """
You are AI Mentor, a specialized Artificial Intelligence assistant.

Your specialization is ONLY Artificial Intelligence and related fields.

You help users learn about:

- Artificial Intelligence
- Machine Learning
- Deep Learning
- Neural Networks
- Generative AI
- Natural Language Processing
- Computer Vision
- Python for AI
- AI tools and projects
- AI ethics and applications

LANGUAGE RULES:

1. Understand Arabic and English.
2. Understand Sudanese Arabic dialect.
3. Understand Egyptian, Gulf, Levantine and Maghrebi dialects.
4. Reply using the same language as the user.
5. If the user speaks Sudanese Arabic, reply naturally in Sudanese Arabic.
6. Never criticize spelling or dialect.
7. Explain difficult concepts simply and clearly.

SCOPE RULE:

If a question is unrelated to Artificial Intelligence,
politely explain that you are specialized in AI
and invite the user to ask an AI-related question.

Do not claim that you trained yourself using saved information.
Saved information is reference knowledge only.

Be helpful, accurate and educational.
"""

        if knowledge_context:

            system_prompt += """

USER KNOWLEDGE LIBRARY:

The following information was saved by the user.
Use it when relevant to answer the question.

""" + knowledge_context

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        for message in history[-10:]:

            if message["role"] in ["user", "assistant"]:

                messages.append(message)

        messages.append({
            "role": "user",
            "content": question
        })

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            max_tokens=1500
        )

        return response.choices[0].message.content

    except Exception:
        return (
            "حدث خطأ أثناء الاتصال بخدمة الذكاء الاصطناعي. "
            "راجعي إعدادات API Key والاتصال بالإنترنت."
        )


# ==========================================
# 9. SIDEBAR
# ==========================================

with st.sidebar:

    st.markdown(
        "<h2 style='text-align:center;'>🤖 AI Mentor</h2>",
        unsafe_allow_html=True
    )

    st.markdown("---")

    page = st.radio(
        "القائمة الرئيسية",
        [
            "🏠 Home",
            "💬 AI Assistant",
            "📚 Knowledge Library",
            "🎓 Learning Center",
            "ℹ️ About"
        ]
    )

    st.markdown("---")

    if st.button("➕ محادثة جديدة", use_container_width=True):

        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []

        st.rerun()

    st.markdown("---")

    if get_api_key():
        st.success("AI Service Ready")
    else:
        st.warning("API Key غير مضبوط")


# ==========================================
# 10. HOME PAGE
# ==========================================

if page == "🏠 Home":

    st.markdown("""
    <div class="hero">
        <h1>🤖 AI Mentor</h1>
        <h3>Your Personal Artificial Intelligence Expert</h3>
        <p>Ask. Learn. Explore. Grow.</p>
        <p>العربية | English | Arabic Dialects</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">✨ Welcome to AI Mentor</div>',
        unsafe_allow_html=True
    )

    st.write(
        "مرحباً بك في مرشد الذكاء الاصطناعي. "
        "منصة تعليمية ذكية تساعدك على فهم واستكشاف عالم AI."
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("""
        <div class="info-card">
            <h3>🤖 AI Assistant</h3>
            <p>اسأل عن الذكاء الاصطناعي واحصل على إجابات ذكية.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="info-card">
            <h3>📚 Knowledge Library</h3>
            <p>احفظ معلوماتك وملفاتك للرجوع إليها لاحقاً.</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:

        st.markdown("""
        <div class="info-card">
            <h3>🎓 Learning Center</h3>
            <p>تعلم مفاهيم الذكاء الاصطناعي بطريقة مبسطة.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="info-card">
            <h3>🌍 Multilingual Support</h3>
            <p>تحدث بالعربية والإنجليزية ولهجات عربية مختلفة.</p>
        </div>
        """, unsafe_allow_html=True)


# ==========================================
# 11. AI ASSISTANT PAGE
# ==========================================

elif page == "💬 AI Assistant":

    st.markdown("""
    <div class="hero">
        <h1>💬 AI Assistant</h1>
        <h3>Ask anything about Artificial Intelligence</h3>
        <p>اسأل عن الذكاء الاصطناعي بأي لغة أو لهجة.</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.messages:

        st.markdown("### 💡 Suggested Questions")

        questions = [
            "What is Artificial Intelligence?",
            "شنو الفرق بين AI و Machine Learning؟",
            "Explain Neural Networks simply.",
            "كيف أبدأ أتعلم الذكاء الاصطناعي؟"
        ]

        cols = st.columns(2)

        for index, question in enumerate(questions):

            with cols[index % 2]:

                if st.button(question, use_container_width=True):
                    st.session_state.pending_question = question
                    st.rerun()

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

    user_question = st.chat_input(
        "اكتب سؤالك هنا... Ask anything about AI"
    )

    if st.session_state.pending_question:

        user_question = st.session_state.pending_question

        st.session_state.pending_question = None

    if user_question:

        st.session_state.messages.append({
            "role": "user",
            "content": user_question
        })

        save_message("user", user_question)

        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):

            with st.spinner("AI Mentor is thinking..."):

                answer = get_ai_response(
                    user_question,
                    st.session_state.messages[:-1]
                )

                st.markdown(answer)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        save_message("assistant", answer)

        st.rerun()

    if st.session_state.messages:

        st.markdown("---")

        st.markdown("### ⭐ Rate this conversation")

        rating = st.feedback("thumbs")

        if rating is not None:

            if st.button("Submit Feedback"):

                save_feedback(rating)

                st.success("Thank you for your feedback!")


# ==========================================
# 12. KNOWLEDGE LIBRARY
# ==========================================

elif page == "📚 Knowledge Library":

    st.markdown("""
    <div class="hero">
        <h1>📚 Knowledge Library</h1>
        <h3>Your Personal AI Knowledge Base</h3>
        <p>احفظ معلوماتك واسترجعها عند الحاجة.</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs([
        "➕ Add Knowledge",
        "📖 Saved Knowledge"
    ])

    with tab1:

        title = st.text_input(
            "Knowledge Title"
        )

        content = st.text_area(
            "Write your information here",
            height=180
        )

        if st.button("💾 Save Knowledge"):

            if title.strip() and content.strip():

                save_knowledge(title, content)

                st.success("تم حفظ المعلومات بنجاح.")

            else:

                st.warning("يرجى إدخال العنوان والمحتوى.")

        st.markdown("---")

        st.markdown("### 📄 Upload PDF")

        uploaded_file = st.file_uploader(
            "Upload a PDF document",
            type=["pdf"]
        )

        if uploaded_file:

            if st.button("Read and Save PDF"):

                try:

                    pdf_text = read_pdf(uploaded_file)

                    if pdf_text.strip():

                        save_knowledge(
                            uploaded_file.name,
                            pdf_text[:50000]
                        )

                        st.success(
                            "تم استخراج النص وحفظه بنجاح."
                        )

                    else:

                        st.warning(
                            "لم يتم العثور على نص قابل للاستخراج في الملف."
                        )

                except Exception:

                    st.error(
                        "تعذر قراءة الملف. تأكدي من سلامة ملف PDF."
                    )

    with tab2:

        items = get_knowledge()

        if not items:

            st.info("لا توجد معلومات محفوظة حتى الآن.")

        for item in items:

            with st.expander(item[1]):

                st.write(item[2][:5000])

                if st.button(
                    "🗑️ Delete",
                    key=f"delete_{item[0]}"
                ):

                    delete_knowledge(item[0])

                    st.rerun()


# ==========================================
# 13. LEARNING CENTER
# ==========================================

elif page == "🎓 Learning Center":

    st.markdown("""
    <div class="hero">
        <h1>🎓 Learning Center</h1>
        <h3>Explore the World of Artificial Intelligence</h3>
        <p>ابدأ رحلتك التعليمية في الذكاء الاصطناعي.</p>
    </div>
    """, unsafe_allow_html=True)

    topics = {
        "🤖 Artificial Intelligence":
            "Artificial Intelligence is the ability of computer systems to perform tasks that normally require human intelligence.",

        "🧠 Machine Learning":
            "Machine Learning is a branch of AI that enables computers to learn patterns from data.",

        "🔬 Deep Learning":
            "Deep Learning uses multi-layer neural networks to learn complex patterns.",

        "🕸️ Neural Networks":
            "Neural Networks are computational systems inspired by the structure of the human brain.",

        "✨ Generative AI":
            "Generative AI creates new content such as text, images, audio and code.",

        "💬 Natural Language Processing":
            "NLP helps computers understand, process and generate human language.",

        "👁️ Computer Vision":
            "Computer Vision enables machines to interpret and understand visual information."
    }

    for topic, description in topics.items():

        with st.expander(topic):

            st.write(description)


# ==========================================
# 14. ABOUT PAGE
# ==========================================

elif page == "ℹ️ About":

    st.markdown("""
    <div class="hero">
        <h1>🤖 About AI Mentor</h1>
        <h3>Your Personal Artificial Intelligence Expert</h3>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="info-card">
        <h3>🌟 Project Overview</h3>
        <p>
        AI Mentor is an intelligent educational assistant
        specialized in Artificial Intelligence.
        It helps users explore AI concepts and learn
        about modern AI technologies.
        </p>
    </div>

    <div class="info-card">
        <h3>🎯 Project Goal</h3>
        <p>
        Making Artificial Intelligence knowledge
        easier and more accessible to everyone.
        </p>
    </div>

    <div class="info-card">
        <h3>🛠️ Technologies</h3>
        <p>
        Python | Streamlit | OpenAI API | SQLite | PyPDF
        </p>
    </div>

    <div class="info-card">
        <h3>👩‍💻 Developer</h3>
        <p><b>Abeer Alsied</b></p>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 15. FOOTER
# ==========================================

st.markdown("---")

st.markdown("""
<div style="
    text-align:center;
    padding:20px;
    color:#cbb7eb;
">
    <h4>🤖 AI Mentor</h4>
    Your Personal Artificial Intelligence Expert
    <br><br>
    Made with ❤️ using Python and Artificial Intelligence
    <br>
    Version 1.2
</div>
""", unsafe_allow_html=True)
