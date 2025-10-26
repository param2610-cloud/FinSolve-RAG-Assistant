"""
query processor - spacy based query analysis
from notebook rag.ipynb
"""
import spacy
from typing import Dict, List, Any
import re

# department keywords from notebook
DEPARTMENT_KEYWORDS = {
    "finance": ["finance", "financial", "revenue", "expense", "budget", "cost", "profit", "quarter", "q1", "q2", "q3", "q4", "quarterly", "annual", "payment", "invoice"],
    "marketing": ["marketing", "campaign", "customer", "acquisition", "conversion", "roi", "ad", "advertisement", "brand", "social media", "engagement"],
    "hr": ["employee", "hr", "human resource", "salary", "payroll", "performance", "rating", "leave", "attendance", "hiring", "recruitment", "onboarding"],
    "engineering": [
        "engineering", "technical", "technology", "tech", "tech stack", "tech-stack", "stack", "architecture",
        "development", "devops", "infrastructure", "api", "apis", "microservice", "microservices",
        "deployment", "security", "framework", "frameworks", "platform", "platforms", "language", "languages",
        "tooling"
    ],
    "general": ["policy", "handbook", "guideline", "benefit", "office", "company", "event"]
}


class QueryProcessor:
    """proces natural language queries - from notebook"""
    
    def __init__(self, nlp_model=None):
        if nlp_model:
            self.nlp = nlp_model
        else:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except:
                self.nlp = None
                print("warning: spacy model not loaded. query processing disabled")
    
    def sanitize_query(self, query: str) -> str:
        """clean and normalize the query"""
        # remove extra whitespace
        query = " ".join(query.split())
        
        # remove special characters except alphanumeric and common punctuation
        query = re.sub(r'[^\w\s\?\.\,\-]', '', query)
        
        return query.strip()
    
    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """extract named entities from query"""
        if not self.nlp:
            return {
                "persons": [],
                "orgs": [],
                "dates": [],
                "money": [],
                "numbers": [],
                "locations": []
            }
        
        doc = self.nlp(query)
        entities = {
            "persons": [],
            "orgs": [],
            "dates": [],
            "money": [],
            "numbers": [],
            "locations": []
        }
        
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                entities["persons"].append(ent.text)
            elif ent.label_ == "ORG":
                entities["orgs"].append(ent.text)
            elif ent.label_ == "DATE":
                entities["dates"].append(ent.text)
            elif ent.label_ == "MONEY":
                entities["money"].append(ent.text)
            elif ent.label_ in ["CARDINAL", "QUANTITY"]:
                entities["numbers"].append(ent.text)
            elif ent.label_ in ["GPE", "LOC"]:
                entities["locations"].append(ent.text)
        
        return entities
    
    def lemmatize_query(self, query: str) -> str:
        """lemmatize query for better matching"""
        if not self.nlp:
            return query
        
        doc = self.nlp(query)
        lemmatized = " ".join([token.lemma_ for token in doc if not token.is_stop])
        return lemmatized
    
    def detect_intent(self, query: str) -> Dict[str, Any]:
        """detect query intent and target department - from notebook"""
        if not self.nlp:
            return {
                "query_type": "document_search",
                "target_departments": [],
                "is_comparison": False,
                "is_aggregation": False,
                "temporal_scope": None,
                "confidence": 0.0
            }
        
        doc = self.nlp(query.lower())
        
        intent = {
            "query_type": "unknown",
            "target_departments": [],
            "is_comparison": False,
            "is_aggregation": False,
            "temporal_scope": None,
            "confidence": 0.0
        }
        
        query_lower = query.lower()
        
        # detect department based on keywords
        dept_scores = {}
        for dept, keywords in DEPARTMENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                dept_scores[dept] = score
        
        if dept_scores:
            max_score = max(dept_scores.values())
            intent["target_departments"] = [dept for dept, score in dept_scores.items() if score >= max_score * 0.7]
            intent["confidence"] = min(max_score / 5, 1.0)
        
        # explicit boost for technology-related queries
        tech_terms = [
            "tech", "technology", "tech stack", "tech-stack", "stack", "framework", "frameworks",
            "programming language", "languages", "platform", "platforms", "tooling"
        ]
        if any(term in query_lower for term in tech_terms):
            if "engineering" not in intent["target_departments"]:
                intent["target_departments"].append("engineering")
            intent["confidence"] = max(intent["confidence"], 0.7)
            if intent["query_type"] == "unknown":
                intent["query_type"] = "document_search"
        
        # detect query type
        if any(word in query_lower for word in ["employee", "salary", "payroll", "attendance", "performance rating"]):
            intent["query_type"] = "hr_data"
        elif any(word in query_lower for word in ["policy", "handbook", "guideline", "procedure"]):
            intent["query_type"] = "document_search"
        elif any(word in query_lower for word in ["compare", "versus", "vs", "difference between"]):
            intent["is_comparison"] = True
            intent["query_type"] = "comparison"
        elif any(word in query_lower for word in ["total", "sum", "average", "count", "how many"]):
            intent["is_aggregation"] = True
        
        # detect temporal scope
        if any(word in query_lower for word in ["q1", "q2", "q3", "q4", "quarter"]):
            intent["temporal_scope"] = "quarterly"
        elif any(word in query_lower for word in ["2024", "2025", "year", "annual"]):
            intent["temporal_scope"] = "annual"
        
        # default to document search if we identified departments but no explicit type
        if intent["query_type"] == "unknown" and intent["target_departments"]:
            intent["query_type"] = "document_search"
        
        # ensure departments are unique and ordered
        intent["target_departments"] = list(dict.fromkeys(intent["target_departments"]))
        
        return intent
    
    def expand_query(self, query: str) -> List[str]:
        """generate query variations for better retrieval"""
        if not self.nlp:
            return [query]
        
        doc = self.nlp(query)
        
        # original query
        queries = [query]
        
        # lemmatized version
        lemmatized = " ".join([token.lemma_ for token in doc if not token.is_punct])
        if lemmatized != query:
            queries.append(lemmatized)
        
        # extract key noun phrases
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        if noun_phrases:
            queries.append(" ".join(noun_phrases))
        
        return queries[:3]  # limit to 3 variations
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """complete query processing pipeline - from notebook"""
        # step 1: sanitize
        clean_query = self.sanitize_query(query)
        
        # step 2: extract entities
        entities = self.extract_entities(clean_query)
        
        # step 3: detect intent
        intent = self.detect_intent(clean_query)
        
        # step 4: lemmatize for search
        lemmatized = self.lemmatize_query(clean_query)
        
        # step 5: generate query variations
        query_variations = self.expand_query(clean_query)
        
        return {
            "original_query": query,
            "clean_query": clean_query,
            "lemmatized_query": lemmatized,
            "query_variations": query_variations,
            "entities": entities,
            "intent": intent
        }


# global instance
try:
    nlp = spacy.load("en_core_web_sm")
    query_processor = QueryProcessor(nlp)
    print("✅ QueryProcessor initialized successfully!")
except:
    query_processor = QueryProcessor(None)
    print("⚠️ QueryProcessor initialized without spaCy model")
