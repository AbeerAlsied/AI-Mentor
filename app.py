import os
import re
import sqlite3
from datetime import datetime

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


# ==========================================
# 1. PAGE CONFIGURATION
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
# 2. LANGUAGE SETTINGS
# ==========================================

LANGUAGES = {
    "العربية": "ar",
    "English": "en"
}

if "language" not in st.session_state:
    st.session_state.language = "ar"

lang = st.session_state.language

TEXT = {
    "ar": {
        "title": "AI Mentor",
        "subtitle": "مساعدك الذكي للتعلم والمعرفة",
        "home": "الرئيسية",
        "chat": "المحادثة الذكية",
        "library": "المكتبة المعرفية",
        "history": "سجل المحادثات",
        "about": "عن المنصة",
        "welcome": "مرحباً بك في AI Mentor",
        "welcome_text": "منصتك الذكية للتعلم والإجابة عن الأسئلة وفهم المعلومات.",
        "start": "ابدأ المحادثة",
        "question": "اكتب سؤالك هنا...",
        "send": "إرسال السؤال",
        "clear": "مسح المحادثة",
        "upload": "ارفع ملف PDF",
        "upload_success": "تم رفع الملف وقراءة محتواه بنجاح.",
        "upload_error": "حدث خطأ أثناء قراءة الملف.",
        "no_key": "لم يتم العثور على OpenAI API Key. يرجى إضافته في Secrets.",
        "thinking": "جاري التفكير...",
        "history_title": "المحادثات السابقة",
        "no_history": "لا توجد محادثات محفوظة حتى الآن.",
        "about_title": "عن AI Mentor",
        "about_text": "AI Mentor منصة تعليمية ذكية تستخدم الذكاء الاصطناعي لمساعدة المستخدمين في التعلم وفهم المعلومات والإجابة عن الأسئلة.",
        "feedback": "هل كانت الإجابة مفيدة؟",
        "yes": "نعم، مفيدة",
        "no": "تحتاج تحسين",
        "saved": "تم حفظ تقييمك، شكراً لك.",
        "library_title": "المكتبة المعرفية",
        "library_text": "ارفعي ملفات PDF ليتمكن المساعد من الاستفادة من محتواها عند الإجابة.",
        "no_docs": "لم يتم رفع أي ملفات بعد.",
        "delete": "حذف",
        "new_chat": "محادثة جديدة",
        "chat_title": "المحادثة الذكية",
        "error": "حدث خطأ أثناء الاتصال بالذكاء الاصطناعي.",
        "footer": "AI Mentor | Your Personal AI Learning Assistant",
        "choose_language": "اختاري اللغة",
        "source": "مصدر المعرفة",
        "general": "المعرفة العامة",
        "document": "الملفات المرفوعة"
    },

    "en": {
        "title": "AI Mentor",
        "subtitle": "Your Intelligent Learning Assistant",
        "home": "Home",
        "chat": "AI Chat",
        "library": "Knowledge Library",
        "history": "Chat History",
        "about": "About",
        "welcome": "Welcome to AI Mentor",
        "welcome_text": "Your intelligent platform for learning, understanding, and discovering information.",
        "start": "Start Chatting",
        "question": "Type your question here...",
        "send": "Send Question",
        "clear": "Clear Chat",
        "upload": "Upload PDF",
        "upload_success": "File uploaded and processed successfully.",
        "upload_error": "Error while reading the file.",
        "no_key": "OpenAI API Key not found. Please add it to Secrets.",
        "thinking": "Thinking...",
        "history_title": "Previous Conversations",
        "no_history": "No saved conversations yet.",
        "about_title": "About AI Mentor",
        "about_text": "AI Mentor is an intelligent educational platform that uses artificial intelligence to help users learn, understand information, and answer questions.",
        "feedback": "Was this answer helpful?",
        "yes": "Yes, Helpful",
        "no": "Needs Improvement",
        "saved": "Your feedback has been saved. Thank you!",
        "library_title": "Knowledge Library",
        "library_text": "Upload PDF files so the assistant can use their content when answering.",
        "no_docs": "No files uploaded yet.",
        "delete": "Delete",
        "new_chat": "New Chat",
        "chat_title": "AI Chat",
        "error": "An error occurred while connecting to AI.",
        "footer": "AI Mentor | Your Personal AI Learning Assistant",
        "choose_language": "Choose Language",
        "source": "Knowledge Source",
        "general": "General Knowledge",
        "document": "Uploaded Documents"
    }
}

T = TEXT[lang]


# ==========================================
# 3. DATABASE
# ==========================================

def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            content TEXT,
            uploaded_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            rating TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


initialize_database()


# ==========================================
# 4. OPENAI API CONNECTION
# ==========================================

def get_api_key():

    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    return os.environ.get("OPENAI_API_KEY", "")


def get_client():

    api_key = get_api_key()

    if not api_key:
        return None

    return OpenAI(api_key=api_key)


client = get_client()


# ==========================================
# 5. SESSION STATE
# ==========================================

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""


# ==========================================
# 6. DATABASE FUNCTIONS
# ==========================================

def create_conversation():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO conversations (title, created_at) VALUES (?, ?)",
        ("New Conversation", datetime.now().isoformat())
    )

    conversation_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return conversation_id


def save_message(conversation_id, role, content):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages
        (conversation_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        conversation_id,
        role,
        content,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def load_conversations():

    conn = get_connection()

    rows = conn.execute("""
        SELECT id, title, created_at
        FROM conversations
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def load_messages(conversation_id):

    conn = get_connection()

    rows = conn.execute("""
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id
    """, (conversation_id,)).fetchall()

    conn.close()

    return [{"role": r[0], "content": r[1]} for r in rows]


def save_feedback(message, rating):

    conn = get_connection()

    conn.execute("""
        INSERT INTO feedback (message, rating, created_at)
        VALUES (?, ?, ?)
    """, (message, rating, datetime.now().isoformat()))

    conn.commit()
    conn.close()


# ==========================================
# 7. PDF PROCESSING
# ==========================================

def extract_pdf_text(uploaded_file):

    reader = PdfReader(uploaded_file)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


def save_document(filename, content):

    conn = get_connection()

    conn.execute("""
        INSERT INTO documents
        (filename, content, uploaded_at)
        VALUES (?, ?, ?)
    """, (
        filename,
        content,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_documents():

    conn = get_connection()

    rows = conn.execute("""
        SELECT id, filename, uploaded_at
        FROM documents
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def get_document_context():

    conn = get_connection()

    rows = conn.execute("""
        SELECT filename, content
        FROM documents
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    context = ""

    for filename, content in rows:
        context += f"\nDocument: {filename}\n"
        context += content[:12000]

    return context[:30000]


# ==========================================
# 8. AI RESPONSE
# ==========================================

def generate_ai_response(question, conversation_history):

    if client is None:
        return T["no_key"]

    document_context = get_document_context()

    if lang == "ar":

        system_prompt = """
أنت AI Mentor، مساعد ذكي متخصص في التعلم والمعرفة.

قواعدك:

1. أجب بلغة المستخدم نفسها.
2. افهم اللهجات العربية، بما فيها اللهجة السودانية.
3. قدم إجابات واضحة ومنظمة وسهلة الفهم.
4. اشرح المفاهيم الصعبة بأمثلة بسيطة.
5. لا تخترع معلومات عند عدم التأكد.
6. إذا كان السؤال متعلقاً بملف مرفوع، استخدم محتواه.
7. إذا لم تجد الإجابة في الملف، وضح ذلك للمستخدم.
8. كن ودوداً ومهنياً.
9. لا تخرج عن دورك كمساعد ذكي للتعلم والمعرفة.
"""

    else:

        system_prompt = """
You are AI Mentor, an intelligent learning and knowledge assistant.

Your rules:

1. Reply in the same language used by the user.
2. Provide clear and well-organized answers.
3. Explain difficult concepts using simple examples.
4. Never invent information.
5. Use uploaded document content when relevant.
6. If the answer is not available in a document, explain that.
7. Be friendly and professional.
8. Focus on learning and knowledge assistance.
"""

    if document_context:

        system_prompt += f"""

Uploaded knowledge library:

{document_context}

Use this content when it is relevant to the user's question.
"""

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    messages.extend(conversation_history[-12:])

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


# ==========================================
# 9. CUSTOM DESIGN
# ==========================================

st.markdown("""
<style>

/* Main background */

.stApp {
    background:
        linear-gradient(
            135deg,
            #10091F 0%,
            #1B1033 45%,
            #241044 100%
        );

    color: #FFFFFF;
}

/* Main content */

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Text */

h1, h2, h3, h4, p, label {
    color: #FFFFFF !important;
}

/* Sidebar */

section[data-testid="stSidebar"] {
    background: #160D29;
    border-right: 1px solid #55358B;
}

/* Buttons */

.stButton > button {
    background: #A855F7 !important;
    color: #FFFFFF !important;
    border: 1px solid #C084FC !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: 10px 18px !important;
    transition: 0.3s ease;
}

.stButton > button:hover {
    background: #7E22CE !important;
    color: #FFFFFF !important;
    border: 1px solid #E9D5FF !important;
    transform: translateY(-2px);
}

/* Inputs */

.stTextInput input,
.stTextArea textarea {
    background: #2B1B45 !important;
    color: #FFFFFF !important;
    border: 1px solid #9B6BD3 !important;
    border-radius: 10px !important;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: #D8C9EB !important;
}

/* Selectbox */

div[data-baseweb="select"] {
    background: #2B1B45 !important;
    border-radius: 10px;
}

div[data-baseweb="select"] * {
    color: #FFFFFF !important;
}

/* Cards */

.mentor-card {
    background: linear-gradient(
        135deg,
        #352052,
        #25143D
    );

    border: 1px solid #7045A6;
    border-radius: 18px;
    padding: 25px;
    margin-bottom: 18px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.2);
}

/* Hero */

.hero {
    background: linear-gradient(
        120deg,
        #54258B,
        #8B45C6,
        #A855F7
    );

    padding: 45px 25px;
    border-radius: 22px;
    text-align: center;
    margin-bottom: 25px;
}

/* Chat messages */

div[data-testid="stChatMessage"] {
    background: #291B40;
    border: 1px solid #65438A;
    border-radius: 15px;
    padding: 12px;
    margin-bottom: 12px;
}

/* File uploader */

div[data-testid="stFileUploader"] {
    background: #25173A;
    border: 1px dashed #A855F7;
    border-radius: 15px;
    padding: 15px;
}

/* Success messages */

div[data-testid="stAlert"] {
    border-radius: 12px;
}

/* Footer */

.footer {
    text-align: center;
    color: #C4B5D9;
    padding: 25px;
    margin-top: 35px;
    border-top: 1px solid #55358B;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 10. SIDEBAR
# ==========================================

with st.sidebar:

    st.markdown(
        "<h1 style='text-align:center;color:#C084FC;'>🤖 AI Mentor</h1>",
        unsafe_allow_html=True
    )

    st.markdown(
        f"<p style='text-align:center;color:#D8C9EB;'>{T['subtitle']}</p>",
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown(f"### 🌐 {T['choose_language']}")

    selected_language = st.selectbox(
        "Language",
        ["العربية", "English"],
        index=0 if lang == "ar" else 1,
        label_visibility="collapsed"
    )

    new_language = LANGUAGES[selected_language]

    if new_language != lang:

        st.session_state.language = new_language
        st.rerun()

    st.divider()

    page = st.radio(
        "Navigation",
        [
            T["home"],
            T["chat"],
            T["library"],
            T["history"],
            T["about"]
        ],
        label_visibility="collapsed"
    )

    st.divider()

    if st.button("➕ " + T["new_chat"], use_container_width=True):

        st.session_state.conversation_id = create_conversation()
        st.session_state.messages = []
        st.session_state.last_answer = ""

        st.rerun()

    st.markdown(
        f"<div class='footer'>{T['footer']}</div>",
        unsafe_allow_html=True
    )


# ==========================================
# 11. HOME PAGE
# ==========================================

if page == T["home"]:

    st.markdown(f"""
    <div class="hero">
        <h1 style="font-size:42px;">🤖 AI Mentor</h1>
        <h2>{T['welcome']}</h2>
        <p style="font-size:18px;">
            {T['welcome_text']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="mentor-card">
            <h2>🧠</h2>
            <h3>Smart AI</h3>
            <p>Intelligent answers and explanations.</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="mentor-card">
            <h2>📚</h2>
            <h3>Learning</h3>
            <p>Learn and understand new concepts.</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="mentor-card">
            <h2>📄</h2>
            <h3>PDF Support</h3>
            <p>Upload documents and ask questions.</p>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    if st.button("🚀 " + T["start"], use_container_width=True):

        st.session_state.conversation_id = create_conversation()
        st.session_state.messages = []

        st.rerun()


# ==========================================
# 12. CHAT PAGE
# ==========================================

elif page == T["chat"]:

    st.title("💬 " + T["chat_title"])

    st.caption(T["subtitle"])

    if st.session_state.conversation_id is None:

        st.session_state.conversation_id = create_conversation()

    if not st.session_state.messages:

        st.session_state.messages = load_messages(
            st.session_state.conversation_id
        )

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

    question = st.chat_input(T["question"])

    if question:

        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        save_message(
            st.session_state.conversation_id,
            "user",
            question
        )

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):

            with st.spinner(T["thinking"]):

                try:

                    answer = generate_ai_response(
                        question,
                        st.session_state.messages[:-1]
                    )

                    st.markdown(answer)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                    save_message(
                        st.session_state.conversation_id,
                        "assistant",
                        answer
                    )

                    st.session_state.last_answer = answer

                except Exception as e:

                    st.error(T["error"])

                    st.caption(str(e))

    if st.session_state.last_answer:

        st.divider()

        st.markdown("### ⭐ " + T["feedback"])

        col1, col2 = st.columns(2)

        with col1:

            if st.button("👍 " + T["yes"]):

                save_feedback(
                    st.session_state.last_answer,
                    "Positive"
                )

                st.success(T["saved"])

        with col2:

            if st.button("👎 " + T["no"]):

                save_feedback(
                    st.session_state.last_answer,
                    "Negative"
                )

                st.success(T["saved"])

    if st.button("🗑️ " + T["clear"]):

        st.session_state.conversation_id = create_conversation()
        st.session_state.messages = []
        st.session_state.last_answer = ""

        st.rerun()


# ==========================================
# 13. KNOWLEDGE LIBRARY
# ==========================================

elif page == T["library"]:

    st.title("📚 " + T["library_title"])

    st.write(T["library_text"])

    uploaded_file = st.file_uploader(
        T["upload"],
        type=["pdf"]
    )

    if uploaded_file is not None:

        if st.button("📤 " + T["upload"]):

            try:

                pdf_text = extract_pdf_text(uploaded_file)

                if pdf_text.strip():

                    save_document(
                        uploaded_file.name,
                        pdf_text
                    )

                    st.success(T["upload_success"])

                else:

                    st.warning(T["upload_error"])

            except Exception:

                st.error(T["upload_error"])

    st.divider()

    st.subheader("📁 " + T["library_title"])

    documents = get_documents()

    if documents:

        for doc_id, filename, uploaded_at in documents:

            col1, col2 = st.columns([4, 1])

            with col1:

                st.markdown(
                    f"📄 **{filename}**"
                )

                st.caption(uploaded_at[:16])

            with col2:

                if st.button(
                    "🗑️ " + T["delete"],
                    key=f"delete_{doc_id}"
                ):

                    conn = get_connection()

                    conn.execute(
                        "DELETE FROM documents WHERE id = ?",
                        (doc_id,)
                    )

                    conn.commit()
                    conn.close()

                    st.rerun()

    else:

        st.info(T["no_docs"])


# ==========================================
# 14. CHAT HISTORY
# ==========================================

elif page == T["history"]:

    st.title("🕘 " + T["history_title"])

    conversations = load_conversations()

    if conversations:

        for conversation_id, title, created_at in conversations:

            with st.expander(
                f"💬 {title} - {created_at[:16]}"
            ):

                messages = load_messages(conversation_id)

                if messages:

                    for message in messages:

                        role = (
                            "👤 User"
                            if message["role"] == "user"
                            else "🤖 AI Mentor"
                        )

                        st.markdown(f"**{role}**")

                        st.write(message["content"])

                if st.button(
                    "📖 Open Conversation",
                    key=f"open_{conversation_id}"
                ):

                    st.session_state.conversation_id = conversation_id
                    st.session_state.messages = messages
                    st.session_state.last_answer = next(
                        (
                            m["content"]
                            for m in reversed(messages)
                            if m["role"] == "assistant"
                        ),
                        ""
                    )

                    st.rerun()

    else:

        st.info(T["no_history"])


# ==========================================
# 15. ABOUT PAGE
# ==========================================

elif page == T["about"]:

    st.title("ℹ️ " + T["about_title"])

    st.markdown(f"""
    <div class="mentor-card">

        <h2>🤖 AI Mentor</h2>

        <p style="font-size:18px;">
            {T['about_text']}
        </p>

        <hr>

        <h3>✨ Main Features</h3>

        <ul>
            <li>Artificial Intelligence Assistance</li>
            <li>Arabic and English Support</li>
            <li>PDF Document Processing</li>
            <li>Conversation History</li>
            <li>User Feedback</li>
        </ul>

        <h3>🛠️ Technologies</h3>

        <p>
            Python | Streamlit | OpenAI API | SQLite | PyPDF
        </p>

        <h3>Version 1.2</h3>

    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 16. FOOTER
# ==========================================

st.markdown("""
<div class="footer">
    🤖 AI Mentor | Powered by Artificial Intelligence
</div>
""", unsafe_allow_html=True)
