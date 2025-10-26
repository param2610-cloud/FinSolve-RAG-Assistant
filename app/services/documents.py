"""
document management service
handles document upload and processing for rag
"""
from flask import Blueprint, request, jsonify
from app.services.auth import require_auth
from datetime import datetime
import os

docs_bp = Blueprint('documents', __name__)


@docs_bp.route('/upload', methods=['POST'])
@require_auth
def upload_document():
    """upload document to rag system - manager only"""
    from app.utils.rag_engine import vector_store
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    # check if user is manager
    if request.user['role'] not in ['manager', 'Manager']:
        return jsonify({"error": "access denied"}), 403
    
    # check if file present
    if 'file' not in request.files:
        return jsonify({"error": "no file provided"}), 400
    
    file = request.files['file']
    department = request.form.get('department', '').strip().lower()
    
    # validation
    if file.filename == '':
        return jsonify({"error": "no file selected"}), 400
    
    if department not in ['finance', 'hr', 'engineering', 'marketing', 'general']:
        return jsonify({"error": "invalid department"}), 400
    
    # check file extension
    allowed_extensions = {'.md', '.txt'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({"error": "invalid file type"}), 400
    
    try:
        # create dept directory if doesnt exist
        dept_dir = f"resources/data/{department}"
        os.makedirs(dept_dir, exist_ok=True)
        
        # save file
        filename = file.filename
        filepath = os.path.join(dept_dir, filename)
        
        
        # check if file already exists
        if os.path.exists(filepath):
            return jsonify({"error": f"file already exists"}), 400
        
        file.save(filepath)
        
        # load and proces the document
        loader = TextLoader(filepath)
        docs = loader.load()
        
        # add metadata
        for doc in docs:
            doc.metadata['department'] = department
            doc.metadata['source'] = filepath.replace("\\", "/")
            doc.metadata['uploaded_by'] = request.user['id']
            doc.metadata['uploaded_at'] = datetime.now().isoformat()
        
        # split documeents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        splits = text_splitter.split_documents(docs)
        
        # add to vector store
        if vector_store is None:
            return jsonify({"error": "vector store not initialized"}), 500
        
        vector_store.add_documents(splits)
        
        return jsonify({
            "message": "document uploaded successfully",
            "document": {
                "filename": filename,
                "department": department,
                "chunks_created": len(splits),
                "uploaded_at": datetime.now().isoformat()
            }
        }), 201
        
    except Exception as e:
        # cleanup file if processing failed
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": f"failed to process document: {str(e)}"}), 500
