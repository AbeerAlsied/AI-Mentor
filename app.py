import os
import sqlite3
from datetime import datetime

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


# ==========================================
# 1. CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="AI Mentor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "/tmp/ai_mentor_v2.db"
MODEL_NAME = "gpt-4o-mini"


# ==========================================
# 2. LANGUAGES
# ==========================================

LANGUAGES = {
    "العربية": "ar",
    "English": "en"
}

TEXT = {
    "ar": {
        "home": "الرئيسية",
        "chat": "المحادثة الذكية",
        "library": "المكتبة المعرفية",
        "history": "سجل المحادثات",
        "about": "عن المنصة",
        "subtitle": "مساعدك الذكي للتعلم والمعرفة",
        "welcome": "مرحباً بك في AI Mentor",
        "welcome_text": "منصتك الذكية للتعلم والإجابة عن الأسئلة وفهم المعلومات.",
        "start": "ابدأ المحادثة",
        "new_chat": "محادثة جديدة",
        "question": "اكتب سؤالك هنا...",
        "clear": "مسح المحادثة",
        "upload": "رفع ملف PDF",
        "upload_success": "تم رفع الملف بنجاح.",
        "upload_error": "تعذر استخراج النص من الملف.",
        "no_key": "لم يتم العثور على OpenAI API Key. يرجى إضافته في Secrets.",
        "thinking": "جاري التفكير...",
        "error": "حدث خطأ أثناء الاتصال بالذكاء الاصطناعي.",
        "history_title": "المحادثات السابقة",
        "no_history": "لا توجد محادثات محفوظة حتى الآن.",
        "about_title": "عن AI Mentor",
        "about_text": "AI Mentor منصة تعليمية ذكية تستخدم الذكاء الاصطناعي لمساعدة المستخدمين في التعلم وفهم المعلومات والإجابة عن الأسئلة.",
        "feedback": "هل كانت الإجابة مفيدة؟",
        "yes": "نعم، مفيدة",
        "no": "تحتاج تحسين",
        "saved": "شكراً لك، تم حفظ تقييمك.",
        "library_title": "المكتبة المعرفية",
        "library_text": "ارفعي ملفات PDF ليستفيد المساعد من محتواها.",
        "no_docs": "لم يتم رفع أي ملفات بعد.",
        "delete": "حذف",
        "choose_language": "اختاري اللغة",
        "db_error": "حدث خطأ في قاعدة البيانات.",
        "open": "فتح المحادثة",
        "features": "المميزات الرئيسية",
        "technologies": "التقنيات المستخدمة",
        "footer": "AI Mentor | مساعدك الذكي للتعلم"
    },

    "en": {
        "home": "Home",
        "chat": "AI Chat",
        "library": "Knowledge Library",
        "history": "Chat History",
        "about": "About",
        "subtitle": "Your Intelligent Learning Assistant",
        "welcome": "Welcome to AI Mentor",
        "welcome_text": "Your intelligent platform for learning and discovering information.",
        "start": "Start Chatting",
        "new_chat": "New Chat",
        "question": "Type your question here...",
        "clear": "Clear Chat",
        "upload": "Upload PDF",
        "upload_success": "File uploaded successfully.",
        "upload_error": "Could not extract text from the file.",
        "no_key": "OpenAI API Key not found. Add it to Secrets.",
        "thinking": "Thinking...",
        "error": "An error occurred while connecting to AI.",
        "history_title": "Previous Conversations",
        "no_history": "No saved conversations yet.",
        "about_title": "About AI Mentor",
        "about_text": "AI Mentor is an intelligent educational platform powered by artificial intelligence.",
        "feedback": "Was this answer helpful?",
        "yes": "Yes, Helpful",
        "no": "Needs Improvement",
        "saved": "Thank you! Your feedback was saved.",
        "library_title": "Knowledge Library",
        "library_text": "Upload PDF files to help the assistant use their content.",
        "no_docs": "No files uploaded yet.",
        "delete": "Delete",
        "choose_language": "Choose Language",
        "db_error": "A database error occurred.",
        "open": "Open Conversation",
        "features": "Main Features",
        "technologies": "Technologies",
        "footer": "AI Mentor | Your Intelligent Learning Assistant"
    }
}


# ==========================================
# 3. SESSION STATE
# ==========================================

defaults = {
    "language": "ar",
    "navigation": "الرئيسية",
    "conversation_id": None,
    "messages": [],
    "last_answer": "",
    "feedback_given": False
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

lang = st.session_state.language
T = TEXT[lang]


# ==========================================
# 4. DATABASE
# ==========================================

def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def initialize_database():
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                content TEXT,
                uploaded_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                rating TEXT,
                created_at TEXT
            )
        """)


try:
    initialize_database()
except sqlite3.Error as e:
    st.error(TEXT[lang]["db_error"])
    st.exception(e)
    st.stop()


# ==========================================
# 5. DATABASE OPERATIONS
# ==========================================

def create_conversation():
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO conversations (title, created_at)
            VALUES (?, ?)
        """, (
            "New Conversation",
            datetime.now().isoformat()
        ))
        return cursor.lastrowid


def save_message(conversation_id, role, content):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO messages
            (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            conversation_id,
            role,
            content,
            datetime.now().isoformat()
        ))


def load_conversations():
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, title, created_at
            FROM conversations
            ORDER BY id DESC
        """).fetchall()


def load_messages(conversation_id):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id
        """, (conversation_id,)).fetchall()

    return [
        {"role": row[0], "content": row[1]}
        for row in rows
    ]


# ==========================================
# 6. FEEDBACK
# ==========================================

def save_feedback(message, rating):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO feedback
            (message, rating, created_at)
            VALUES (?, ?, ?)
        """, (
            message,
            rating,
            datetime.now().isoformat()
        ))

    st.session_state.feedback_given = True


# ==========================================
# 7. CONVERSATION MANAGEMENT
# ==========================================

def start_new_chat():
    conversation_id = create_conversation()

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = []
    st.session_state.last_answer = ""
    st.session_state.feedback_given = False


def start_chat_and_navigate():
    start_new_chat()
    st.session_state.navigation = TEXT[
        st.session_state.language
    ]["chat"]


def open_conversation(conversation_id):
    messages = load_messages(conversation_id)

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = messages

    st.session_state.last_answer = next(
        (
            message["content"]
            for message in reversed(messages)
            if message["role"] == "assistant"
        ),
        ""
    )

    st.session_state.feedback_given = False

    st.session_state.navigation = TEXT[
        st.session_state.language
    ]["chat"]


def change_language():
    selected = st.session_state.language_selector
    st.session_state.language = LANGUAGES[selected]

    st.session_state.navigation = TEXT[
        st.session_state.language
    ]["home"]


# ==========================================
# 8. OPENAI API
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
# 9. PDF PROCESSING
# ==========================================

def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    extracted_text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            extracted_text += page_text + "\n"

    return extracted_text


def save_document(filename, content):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO documents
            (filename, content, uploaded_at)
            VALUES (?, ?, ?)
        """, (
            filename,
            content,
            datetime.now().isoformat()
        ))


def get_documents():
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, filename, uploaded_at
            FROM documents
            ORDER BY id DESC
        """).fetchall()


def get_document_context():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT filename, content
            FROM documents
            ORDER BY id DESC
        """).fetchall()

    context = ""

    for filename, content in rows:
        context += f"\nDocument: {filename}\n"
        context += content[:12000]

    return context[:30000]


def delete_document(doc_id):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM documents WHERE id = ?",
            (doc_id,)
        )


# ==========================================
# 10. AI RESPONSE
# ==========================================

def generate_ai_response(question, conversation_history):

    if client is None:
        return T["no_key"]

    document_context = get_document_context()

    if lang == "ar":
        system_prompt = """
أنت AI Mentor، مساعد ذكي متخصص في التعلم والمعرفة.

التعليمات:
1. أجب بلغة المستخدم نفسها.
2. افهم اللهجات العربية بما فيها السودانية.
3. قدم إجابات واضحة ومنظمة.
4. اشرح المفاهيم الصعبة بأمثلة بسيطة.
5. لا تخترع معلومات.
6. استخدم الملفات المرفوعة عندما يكون السؤال متعلقاً بها.
7. وضح للمستخدم إذا لم تجد الإجابة في الملف.
8. كن ودوداً ومهنياً.
9. ساعد المستخدم على التعلم والفهم.
"""
    else:
        system_prompt = """
You are AI Mentor, an intelligent learning assistant.

Instructions:
1. Reply in the user's language.
2. Provide clear and organized answers.
3. Explain difficult concepts using simple examples.
4. Never invent information.
5. Use uploaded documents when relevant.
6. Explain when information is unavailable.
7. Be friendly and professional.
"""

    if document_context:
        system_prompt += f"""

Uploaded documents:

{document_context}

Use these documents when relevant.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
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
# 11. DESIGN
# ==========================================

st.markdown("""
<style>

.stApp {
    background: linear-gradient(
        135deg,
        #10091F,
        #1B1033,
        #241044
    );
    color: white;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3, h4, p, label {
    color: #FFFFFF !important;
}

section[data-testid="stSidebar"] {
    background: #160D29;
    border-right: 1px solid #7045A6;
}

.stButton > button {
    background-color: #A855F7 !important;
    color: #FFFFFF !important;
    border: 2px solid #C084FC !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: 10px 18px !important;
    transition: 0.3s ease;
}

.stButton > button:hover {
    background-color: #7E22CE !important;
    color: #FFFFFF !important;
    border-color: #E9D5FF !important;
}

.stChatInput textarea {
    background: #2B1B45 !important;
    color: white !important;
}

.stTextInput input,
.stTextArea textarea {
    background: #2B1B45 !important;
    color: white !important;
    border: 1px solid #A855F7 !important;
    border-radius: 10px !important;
}

div[data-baseweb="select"] {
    background: #2B1B45 !important;
}

div[data-baseweb="select"] * {
    color: white !important;
}

.stRadio label {
    color: white !important;
}

.mentor-card {
    background: linear-gradient(
        135deg,
        #352052,
        #25143D
    );
    border: 1px solid #8755B8;
    border-radius: 18px;
    padding: 25px;
    margin-bottom: 18px;
    min-height: 180px;
}

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

div[data-testid="stChatMessage"] {
    background: #291B40;
    border: 1px solid #65438A;
    border-radius: 15px;
    padding: 12px;
    margin-bottom: 12px;
}

div[data-testid="stFileUploader"] {
    background: #25173A;
    border: 1px dashed #A855F7;
    border-radius: 15px;
    padding: 15px;
}

.footer {
    text-align: center;
    color: #D8C9EB;
    padding: 20px;
    margin-top: 30px;
    border-top: 1px solid #55358B;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 12. SIDEBAR AND NAVIGATION
# ==========================================

with st.sidebar:

    st.markdown("""
    <h1 style="text-align:center;color:#C084FC;">
        🤖 AI Mentor
    </h1>
    """, unsafe_allow_html=True)

    st.markdown(
        f"<p style='text-align:center'>{T['subtitle']}</p>",
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown("### 🌐 " + T["choose_language"])

    st.selectbox(
        "Language",
        ["العربية", "English"],
        index=0 if lang == "ar" else 1,
        label_visibility="collapsed",
        key="language_selector",
        on_change=change_language
    )

    st.divider()

    pages = [
        T["home"],
        T["chat"],
        T["library"],
        T["history"],
        T["about"]
    ]

    if st.session_state.navigation not in pages:
        st.session_state.navigation = T["home"]

    page = st.radio(
        "Navigation",
        pages,
        key="navigation",
        label_visibility="collapsed"
    )

    st.divider()

    st.button(
        "➕ " + T["new_chat"],
        key="sidebar_new_chat",
        use_container_width=True,
        on_click=start_chat_and_navigate
    )

    st.markdown(
        f"<div class='footer'>{T['footer']}</div>",
        unsafe_allow_html=True
    )


# ==========================================
# 13. HOME PAGE
# ==========================================

if page == T["home"]:

    st.markdown(f"""
    <div class="hero">
        <h1 style="font-size:42px;">🤖 AI Mentor</h1>
        <h2>{T['welcome']}</h2>
        <p style="font-size:18px;">{T['welcome_text']}</p>
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

    st.button(
        "🚀 " + T["start"],
        key="home_start_chat",
        use_container_width=True,
        on_click=start_chat_and_navigate
    )


# ==========================================
# 14. CHAT PAGE
# ==========================================

elif page == T["chat"]:

    st.title("💬 " + T["chat"])
    st.caption(T["subtitle"])

    if st.session_state.conversation_id is None:
        try:
            start_new_chat()
        except sqlite3.Error as e:
            st.error(T["db_error"])
            st.exception(e)
            st.stop()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(T["question"])

    if question:

        with st.chat_message("user"):
            st.markdown(question)

        try:

            save_message(
                st.session_state.conversation_id,
                "user",
                question
            )

            st.session_state.messages.append({
                "role": "user",
                "content": question
            })

            with st.chat_message("assistant"):

                with st.spinner(T["thinking"]):

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
            st.session_state.feedback_given = False

        except Exception as e:
            st.error(T["error"])
            st.caption(str(e))

    # FEEDBACK

    if st.session_state.last_answer:

        st.divider()
        st.markdown("### ⭐ " + T["feedback"])

        if not st.session_state.feedback_given:

            col1, col2 = st.columns(2)

            with col1:
                st.button(
                    "👍 " + T["yes"],
                    key="positive_feedback",
                    on_click=save_feedback,
                    args=(
                        st.session_state.last_answer,
                        "Positive"
                    )
                )

            with col2:
                st.button(
                    "👎 " + T["no"],
                    key="negative_feedback",
                    on_click=save_feedback,
                    args=(
                        st.session_state.last_answer,
                        "Negative"
                    )
                )

        else:
            st.success(T["saved"])

    # CLEAR CHAT

    st.button(
        "🗑️ " + T["clear"],
        key="clear_chat",
        on_click=start_chat_and_navigate
    )


# ==========================================
# 15. KNOWLEDGE LIBRARY
# ==========================================

elif page == T["library"]:

    st.title("📚 " + T["library_title"])
    st.write(T["library_text"])

    uploaded_file = st.file_uploader(
        T["upload"],
        type=["pdf"],
        key="pdf_uploader"
    )

    if uploaded_file is not None:

        if st.button(
            "📤 " + T["upload"],
            key="upload_pdf_button"
        ):

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

            except Exception as e:
                st.error(T["upload_error"])
                st.caption(str(e))

    st.divider()

    st.subheader("📁 " + T["library_title"])

    documents = get_documents()

    if documents:

        for doc_id, filename, uploaded_at in documents:

            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"📄 **{filename}**")
                st.caption(uploaded_at[:16])

            with col2:

                st.button(
                    "🗑️ " + T["delete"],
                    key=f"delete_{doc_id}",
                    on_click=delete_document,
                    args=(doc_id,)
                )

    else:
        st.info(T["no_docs"])


# ==========================================
# 16. CHAT HISTORY
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

                st.button(
                    "📖 " + T["open"],
                    key=f"open_{conversation_id}",
                    on_click=open_conversation,
                    args=(conversation_id,)
                )

    else:
        st.info(T["no_history"])


# ==========================================
# 17. ABOUT PAGE
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

        <h3>✨ {T['features']}</h3>

        <ul>
            <li>Artificial Intelligence Assistance</li>
            <li>Arabic and English Support</li>
            <li>PDF Document Processing</li>
            <li>Conversation History</li>
            <li>User Feedback</li>
        </ul>

        <h3>🛠️ {T['technologies']}</h3>

        <p>
            Python | Streamlit | OpenAI API | SQLite | PyPDF
        </p>

        <h3>Version 2.2</h3>

    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 18. FOOTER
# ==========================================

st.markdown("""
<div class="footer">
    🤖 AI Mentor
    <br>
    Powered by Artificial Intelligence
</div>
""", unsafe_allow_html=True)
