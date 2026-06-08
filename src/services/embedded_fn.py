import os
from typing import Dict
import httpx
import tempfile
import csv
import tiktoken
# pyrefly: ignore [missing-import]
from bs4 import BeautifulSoup
# pyrefly: ignore [missing-import]
from io import BytesIO
from docx import Document
from pypdf import PdfReader
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from qdrant_client.models import Distance, VectorParams
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.utils.config import config

model_cost = {
    "text-embedding-3-small": 0.01 ,# per 1M tokens
    "text-embedding-3-large": 0.02, # per 1M tokens
    "text-embedding-ada-002": 0.01 # per 1M tokens
}

def count_tokens(text: str, model_name: str = "text-embedding-3-small") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))




def read_file_url(url: str):

    try:
        response = httpx.get(url, timeout=60)

        if response.status_code != 200:
            return None

        content_type = response.headers.get("content-type", "").lower()

        # PDF

        if url.endswith(".pdf") or "pdf" in content_type:

            pdf_file = BytesIO(response.content)

            pdf_reader = PdfReader(pdf_file)

            text = ""

            for page in pdf_reader.pages:
                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"

            return {
                "type": "pdf",
                "content": text
            }

        # TXT

        elif url.endswith(".txt") or "text/plain" in content_type:

            return {
                "type": "text",
                "content": response.text
            }

        # CSV

        elif url.endswith(".csv") or "csv" in content_type:

            csv_text = response.text

            reader = csv.reader(csv_text.splitlines())

            rows = []

            for row in reader:
                rows.append(", ".join(row))

            return {
                "type": "csv",
                "content": "\n".join(rows)
            }

        # DOCX

        elif url.endswith(".docx") or \
            "wordprocessingml.document" in content_type:

            temp_docx = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".docx"
            )

            temp_docx.write(response.content)
            temp_docx.close()

            doc = Document(temp_docx.name)

            text = "\n".join(
                para.text for para in doc.paragraphs
            )

            os.unlink(temp_docx.name)

            return {
                "type": "docx",
                "content": text
            }

        # HTML / WEBSITE

        elif "html" in content_type or \
            url.startswith("https"):

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            # Remove script/style
            for tag in soup(["script", "style", "noscript"]):
                tag.extract()

            text = soup.get_text(separator="\n")

            # Get links
            links = []

            for a in soup.find_all("a", href=True):
                links.append(a["href"])

            # Get images
            images = []

            for img in soup.find_all("img", src=True):
                images.append(img["src"])

            return {
                "type": "html",
                "content": text.strip(),
                "links": links,
                "images": images
            }

        # ----------------------------------------
        # FALLBACK
        # ----------------------------------------

        return {
            "type": "unknown",
            "content": response.text
        }

    except Exception as e:

        print(f"Error reading file: {e}")

        return None


# funciton is used to split the text into chunks get the chunck size  based upon the embedding model and chunk overlap 
# we will first calculate 
def text_chunker(text: str,chunkSize = 800,chunkOverlap = 200 ):    
    text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=chunkSize,
    chunk_overlap=chunkOverlap,
    separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = text_splitter.split_text(text)
    return chunks


# funciton is used to calculate the cost 
def calculate_cost(chunks, model_name):
    total_tokens = sum(count_tokens(chunk, model_name) for chunk in chunks)
    total_cost = (total_tokens/1000000) * model_cost[model_name]
    return {
        "total_tokens": total_tokens,
        "total_cost": f"${total_cost:.8f}"
    }


# funciton is used to calculate the token and cost of embedding for a uploaded documents/ web url Steps read the file from url -> chunking -> split the document -> tokenise the document -> calculate the cost  

async def embedding_cost_calculate(url: str, embed_model: str):
    # get the file from url 
    print ("calcualete the cost for ", url, embed_model)
    file_content = read_file_url(url)
    
    if not file_content:
        return None     
    chunked = text_chunker(file_content["content"])
    #calculate the token for the chunck
    # calculate the cost 
    cost = calculate_cost(chunked, embed_model)
    return cost

#function is used to get the Embedding based upon the provider from user table
async def get_embeddings(llm_details:dict):
    
    if llm_details["provider"] == "openAI":
        return OpenAIEmbeddings(
        model=llm_details["embedding_model"],
        openai_api_key=llm_details["api_key"]
        )
    elif llm_details["provider"] == "google":
        return GoogleGenerativeAIEmbeddings(
        model=llm_details["embedding_model"],
        google_api_key=llm_details["api_key"]
        ) 

#function to get the vector store based upon the provider
async def get_vector_store(details:dict, embeddings):
    if details["db_type"] == "qdrant":
        client = QdrantClient(
            url=f"http://{config.vector_store_url}:{config.vector_store_port}",
            api_key=config.vector_store_api_key
        )
        #check the client exist or not
        if client.collection_exists(collection_name=details["collection"]):
            return QdrantVectorStore(
                client=client,
                collection_name=details["collection"],
                embedding=embeddings,
            )
        else:
            # Dynamically fetch vector size from embedding function
            sample_emb = embeddings.embed_query("test")
            vector_size = len(sample_emb)
            
            client.create_collection(
                collection_name=details["collection"],
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            return QdrantVectorStore(
                client=client,
                collection_name=details["collection"],
                embedding=embeddings,
            )
    elif details["db_type"] == "chromadb": 
        import chromadb
        from langchain_community.vectorstores import Chroma
        # Connect to Chroma HTTP client
        client = chromadb.HttpClient(
            host=config.vector_store_url,
            port=config.vector_store_port
        )
        return Chroma(
            client=client,
            collection_name=details["collection"],
            embedding_function=embeddings
        ) 
            
async def ingest_data_into_vector_db(llm_details:dict, url: str):
    from src.services.data import DataService
    from datetime import datetime
    import sys
    import traceback
    file_id = llm_details.get("file_id")
    print(f"[INGEST] Started background ingestion for file_id={file_id}, url={url}", flush=True)
    try:
        if file_id:
            print(f"[INGEST] Updating database status to 2 for file_id={file_id}", flush=True)
            await DataService.update_by_id(file_id, {
                "status": 2,
                "updated_at": datetime.now()
            })
            
        import uuid
        # get the file from url 
        print(f"[INGEST] Reading file contents from URL={url}...", flush=True)
        file_content = read_file_url(url)
        if not file_content:
            print(f"[INGEST] Failed to read file content from URL.", flush=True)
            if file_id:
                await DataService.update_by_id(file_id, {
                    "status": 4,
                    "updated_at": datetime.now()
                })
            return None     
            
        print(f"[INGEST] File content read successfully. Content type: {file_content.get('type')}. Character count: {len(file_content.get('content', ''))}", flush=True)
        chunks = text_chunker(file_content["content"])
        print(f"[INGEST] Text chunked successfully into {len(chunks)} chunks.", flush=True)
        
        print(f"[INGEST] Initializing embeddings config: {llm_details}...", flush=True)
        embeddings = await get_embeddings(llm_details)
        print(f"[INGEST] Embeddings initialized successfully.", flush=True)
        
        print(f"[INGEST] Fetching vector store connection...", flush=True)
        vectorstore = await get_vector_store({
            "db_type":config.vector_store_type,
            "collection":f"kb_{llm_details['kb_id']}",
            }, embeddings)
        print(f"[INGEST] Vector store connection obtained successfully.", flush=True)
            
        metadatas = [{"kb_id": llm_details["kb_id"], "file_id": llm_details["file_id"], "page_number": i,"file_name": llm_details["file_name"], "url": url} for i, _ in enumerate(chunks)]
        ids = [str(uuid.uuid4()) for _ in chunks]
        
        print(f"[INGEST] Inserting chunks into vector store...", flush=True)
        vectorstore.add_texts(
            texts=chunks,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[INGEST] Chunks successfully added to vector store.", flush=True)
        
        if file_id:
            print(f"[INGEST] Updating database status to 3 (completed) for file_id={file_id}", flush=True)
            await DataService.update_by_id(file_id, {
                "status": 3,
                "total_chunks": len(chunks),
                "updated_at": datetime.now()
            })
        print(f"[INGEST] Finished background ingestion for file_id={file_id} successfully.", flush=True)
        return True
        
    except Exception as e:
        print(f"[INGEST] Error ingesting data into vector db: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        if file_id:
            try:
                await DataService.update_by_id(file_id, {
                    "status": 4,
                    "updated_at": datetime.now()
                })
            except Exception as db_err:
                print(f"[INGEST] Failed to update failed status in database: {db_err}", flush=True)
        return None

