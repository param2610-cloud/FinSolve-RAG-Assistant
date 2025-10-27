"""
rag engine - vector store and document processing
based on working rag.ipynb implementation
"""
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import Generator, List, Optional, Tuple
import os
import json
import re
from datetime import datetime
from shutil import rmtree

# initialize embeddings - using same model as notebook
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"}
)

# vector store
vector_store = None


def sanitize_text(text: str) -> str:
    """
    Sanitize text to handle encoding issues and problematic characters
    """
    if not text:
        return ""
    
    try:
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove other control characters except common whitespace
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # Normalize unicode characters
        text = text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Replace multiple newlines with double newline
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
    except Exception as e:
        print(f"⚠️ Error sanitizing text: {e}")
        # Return cleaned version even if error occurs
        return text.encode('ascii', errors='ignore').decode('ascii')
    
    return text


def load_documents_with_metadata():
    """load documents with department metadata - from notebook"""
    documents = []
    dept_mapping = {
        "resources/data/finance": "finance",
        "resources/data/hr": "hr",
        "resources/data/engineering": "engineering",
        "resources/data/marketing": "marketing",
        "resources/data/general": "general"
    }
    
    for folder, dept in dept_mapping.items():
        if os.path.exists(folder):
            try:
                # Load markdown files from directory
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        if file.endswith('.md'):
                            filepath = os.path.join(root, file)
                            try:
                                # Read file with explicit UTF-8 encoding and error handling
                                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                
                                # Sanitize content
                                content = sanitize_text(content)
                                
                                if content:  # Only add if there's actual content
                                    from langchain_core.documents import Document
                                    doc = Document(
                                        page_content=content,
                                        metadata={
                                            'department': dept,
                                            'source': filepath.replace("\\", "/"),
                                            'filename': file
                                        }
                                    )
                                    documents.append(doc)
                                    print(f"✓ Loaded: {file} from {dept}")
                            except Exception as e:
                                print(f"⚠️ Error loading {filepath}: {e}")
                                continue
            except Exception as e:
                print(f"⚠️ Warning loading documents from {folder}: {e}")
                continue
    
    print(f"✓ Total documents loaded: {len(documents)}")
    return documents


def initialize_vector_store():
    """initialize vector store - matches notebook implementation"""
    global vector_store
    
    persist_directory = "resources/database/vector_store"
    documents = load_documents_with_metadata()
    current_sources = {doc.metadata.get("source") for doc in documents if doc.metadata.get("source")}
    
    need_rebuild = not os.path.exists(persist_directory)
    
    if not need_rebuild:
        print("Vector store already exists. Loading from disk...")
        vector_store = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings,
            collection_name="company_docs"
        )
        try:
            existing = vector_store.get(include=["metadatas"])
            stored_sources = {
                (meta or {}).get("source")
                for meta in existing.get("metadatas", [])
                if meta and meta.get("source")
            }
        except Exception as exc:
            print(f"⚠️ Unable to inspect existing vector store ({exc}). Rebuilding...")
            stored_sources = set()
        
        if current_sources and not current_sources.issubset(stored_sources):
            print("Detected new or missing documents. Refreshing vector store...")
            need_rebuild = True
    
    if need_rebuild:
        print("Creating new vector store...")
        rmtree(persist_directory, ignore_errors=True)
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        splits = text_splitter.split_documents(documents)
        
        vector_store = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=persist_directory,
            collection_name="company_docs"
        )
        print(f"Vector store created with {len(splits)} documents.")
    
    return vector_store


def retrieve_documents(processed_query: dict, allowed_depts: List[str]) -> Tuple[List, List[str], bool]:
    """retrieve and deduplicate documents based on query - from notebook"""
    intent = processed_query["intent"]
    used_fallback = False
    
    # determine search scope based on detected departments and permissions
    search_depts = intent["target_departments"] if intent["target_departments"] else allowed_depts
    search_depts = [d for d in search_depts if d in allowed_depts]
    
    # ensure we have at least the allowed departments to search
    if not search_depts:
        search_depts = allowed_depts
    
    query_variations = processed_query.get("query_variations") or [processed_query.get("clean_query", "")]
    query_variations = [q for q in query_variations if q]
    
    def run_retrieval(departments: Optional[List[str]]) -> List:
        search_kwargs = {"k": 4}
        if departments:
            search_kwargs["filter"] = {"department": {"$in": departments}}
        docs = []
        for query_var in query_variations:
            retriever = vector_store.as_retriever(
                search_type="similarity",
                search_kwargs=search_kwargs
            )
            docs.extend(retriever.invoke(query_var))
        return docs
    
    def deduplicate(docs: List) -> List:
        seen_sources = set()
        unique = []
        for doc in docs:
            metadata = doc.metadata or {}
            source = metadata.get("source") or metadata.get("file_path") or metadata.get("path")
            if not source:
                source = metadata.get("document_id") or metadata.get("id")
            if not source:
                source = doc.page_content[:120]
            if source in seen_sources:
                continue
            seen_sources.add(source)
            unique.append(doc)
        return unique
    
    effective_depts = search_depts
    unique_docs = deduplicate(run_retrieval(search_depts))
    
    # first fallback: broaden to all allowed departments
    if not unique_docs and allowed_depts:
        used_fallback = True
        effective_depts = allowed_depts
        unique_docs = deduplicate(run_retrieval(allowed_depts))
    
    # final fallback: drop department filter entirely
    if not unique_docs:
        used_fallback = True
        effective_depts = allowed_depts
        unique_docs = deduplicate(run_retrieval(None))
    
    return unique_docs, effective_depts, used_fallback


def generate_llm_response(processed_query: dict, context: str, user_role: str, search_depts: List[str]) -> Generator[str, None, None]:
    """generate streaming llm response - from notebook"""
    entities = processed_query["entities"]
    intent = processed_query["intent"]
    
    # create enhanced prompt with spacy insights
    prompt_template = ChatPromptTemplate.from_template("""
You are an AI assistant for FinSolve Technologies.

**User Role:** {role}
**Accessible Departments:** {departments}
**Query Type:** {query_type}
**Detected Entities:** {entities}

**Context from company documents:**
{context}

**Question:** {question}

**Instructions:**
1. Answer based ONLY on the provided context
2. Format response in clear markdown with headers, bullet points, and emphasis
3. Cite specific sources by document name
4. If comparing data, use tables or structured format
5. If information is missing, clearly state that

**Answer:**
""")
    
    # initialize llm with streaming
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.3,
        streaming=True,
        groq_api_key=os.getenv("GROQ_API_KEY")
    )
    
    entities_str = ", ".join([f"{k}: {v}" for k, v in entities.items() if v])
    
    prompt = prompt_template.format(
        role=user_role,
        departments=", ".join(search_depts),
        query_type=intent["query_type"],
        entities=entities_str if entities_str else "None",
        context=context,
        question=processed_query["clean_query"]
    )
    
    # stream response
    for chunk in llm.stream(prompt):
        if hasattr(chunk, 'content'):
            yield chunk.content


def stream_rag_response(question: str, user_role: str, processed_query: dict, chat_memory=None) -> Generator[str, None, None]:
    """complete streaming rag response - matches notebook implementation"""
    from app.services.users import ROLE_PERMISSIONS
    from app.utils.hr_helper import query_hr_data_extended
    
    allowed_depts = ROLE_PERMISSIONS.get(user_role, ["general"])
    intent = processed_query["intent"]
    entities = processed_query["entities"]
    
    # display query analysis
    yield json.dumps({"type": "start"}) + "\n"
    yield json.dumps({"type": "token", "content": "## 🔍 Query Analysis\n\n"}) + "\n"
    yield json.dumps({"type": "token", "content": f"**Original Query:** {processed_query['original_query']}\n\n"}) + "\n"
    
    if intent["target_departments"]:
        yield json.dumps({"type": "token", "content": f"**Detected Departments:** {', '.join(intent['target_departments'])}\n\n"}) + "\n"
    
    if intent["query_type"] != "unknown":
        yield json.dumps({"type": "token", "content": f"**Query Type:** {intent['query_type'].replace('_', ' ').title()}\n\n"}) + "\n"
    
    if entities["dates"]:
        yield json.dumps({"type": "token", "content": f"**Time Period:** {', '.join(entities['dates'])}\n\n"}) + "\n"
    
    yield json.dumps({"type": "token", "content": "---\n\n"}) + "\n"
    
    # hr data query handling
    if intent["query_type"] == "hr_data":
        if "hr" in allowed_depts:
            yield json.dumps({"type": "token", "content": "🔍 **Querying HR Database...**\n\n"}) + "\n"
            status, hr_df = query_hr_data_extended(question, user_role, processed_query)
            yield json.dumps({"type": "token", "content": f"{status}\n\n"}) + "\n"
            
            if hr_df is not None:
                yield json.dumps({"type": "token", "content": "### 📊 HR Data Res   ults\n\n"}) + "\n"
                
                # send structured CSV payload so frontend can render a clean HTML table
                try:
                    records = hr_df.fillna('').to_dict(orient='records')
                    columns = list(hr_df.columns)
                    yield json.dumps({
                        "type": "csv",
                        "status": "HR Data Results",
                        "data": records,
                        "columns": columns
                    }) + "\n"
                except Exception:
                    # fallback to plain text table if conversion fails
                    yield json.dumps({"type": "token", "content": f"```\n{hr_df.to_string(index=False)}\n```\n\n"}) + "\n"
            
            yield json.dumps({"type": "done"}) + "\n"
            return
        else:
            yield json.dumps({"type": "token", "content": "❌ **Access Denied:** You don't have permission to access HR data.\n\n"}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return
    
    # document-based rag
    yield json.dumps({"type": "token", "content": "🔍 **Searching documents...**\n\n"}) + "\n"
    
    # retrieve documents
    unique_docs, search_depts, used_fallback = retrieve_documents(processed_query, allowed_depts)
    
    if not allowed_depts and not search_depts:
        yield json.dumps({"type": "token", "content": "⚠️ **No accessible departments found for this user.**\n\n"}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"
        return
    
    search_depts_display = list(dict.fromkeys(search_depts)) if search_depts else []
    if search_depts_display:
        yield json.dumps({"type": "token", "content": f"**Searching in:** {', '.join(search_depts_display)}\n\n"}) + "\n"
    
    if used_fallback:
        yield json.dumps({"type": "token", "content": "ℹ️ **Expanded search scope due to limited initial matches.**\n\n"}) + "\n"
    
    if not unique_docs:
        yield json.dumps({"type": "token", "content": "⚠️ **No relevant information found in accessible documents.**\n\n"}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"
        return
    
    yield json.dumps({"type": "token", "content": f"📄 **Found {len(unique_docs)} relevant documents**\n\n"}) + "\n"
    
    # prepare context
    context = "\n\n".join([
        f"Source: {doc.metadata.get('source', 'Unknown')}\nDepartment: {doc.metadata.get('department', 'Unknown')}\n{doc.page_content}"
        for doc in unique_docs[:5]
    ])
    
    yield json.dumps({"type": "token", "content": "💬 **Generating response...**\n\n---\n\n"}) + "\n"
    
    # generate llm response
    for chunk in generate_llm_response(processed_query, context, user_role, search_depts_display or allowed_depts):
        yield json.dumps({"type": "token", "content": chunk}) + "\n"
    
    # add sources
    yield json.dumps({"type": "token", "content": "\n\n---\n\n### 📚 Sources\n\n"}) + "\n"
    for i, doc in enumerate(unique_docs[:5], 1):
        source = doc.metadata.get('source', 'Unknown').split('/')[-1]
        dept = doc.metadata.get('department', 'Unknown')
        yield json.dumps({"type": "token", "content": f"{i}. **{source}** (Department: {dept})\n"}) + "\n"
    
    yield json.dumps({"type": "done"}) + "\n"
