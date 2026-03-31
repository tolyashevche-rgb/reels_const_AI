"""
CLI скрипт для індексації книг з папки files/ у ChromaDB.

Використання:
    python -m app.indexer
    python -m app.indexer --reset    # очистити і переіндексувати
"""
import os
import sys
import argparse

from app.chroma_store import client, get_collection, CHROMA_DIR

FILES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "files",
)

# Маппінг: підпапка files/ → колекція ChromaDB
FOLDER_TO_COLLECTION = {
    "marketing": "marketing_knowledge",
    "child_dev": "child_dev_knowledge",
    "editorial": "editorial_guide",
}


# ─── File readers ───

def read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        print(f"  [!] Skipping PDF {os.path.basename(path)} — pip install pypdf")
        return ""


def read_docx(path: str) -> str:
    try:
        import docx
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        print(f"  [!] Skipping DOCX {os.path.basename(path)} — pip install python-docx")
        return ""


READERS = {
    ".txt": read_txt,
    ".pdf": read_pdf,
    ".docx": read_docx,
}


def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    reader = READERS.get(ext)
    if reader:
        return reader(path)
    print(f"  [!] Unsupported format: {os.path.basename(path)}")
    return ""


# ─── Chunker ───

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Розбиває текст на chunks з перекриттям."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


# ─── Index one folder ───

def index_folder(folder: str, collection_name: str, reset: bool = False):
    folder_path = os.path.join(FILES_DIR, folder)
    if not os.path.exists(folder_path):
        print(f"  Folder {folder_path} does not exist, skipping")
        return

    collection = get_collection(collection_name)

    if reset:
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            print(f"  Cleared {len(existing['ids'])} existing chunks")

    files = [f for f in os.listdir(folder_path) if not f.startswith(".")]
    if not files:
        print(f"  No files in {folder_path}")
        return

    total_chunks = 0
    for filename in files:
        filepath = os.path.join(folder_path, filename)
        if not os.path.isfile(filepath):
            continue

        text = read_file(filepath)
        if not text:
            continue

        chunks = chunk_text(text)
        if not chunks:
            continue

        ids = [f"{filename}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": filename,
                "collection": collection_name,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        collection.add(documents=chunks, ids=ids, metadatas=metadatas)
        total_chunks += len(chunks)
        print(f"  + {filename}: {len(chunks)} chunks")

    print(f"  Total: {total_chunks} chunks → {collection_name}")


# ─── Main ───

def main():
    parser = argparse.ArgumentParser(description="Index books into ChromaDB")
    parser.add_argument("--reset", action="store_true", help="Clear existing data before indexing")
    args = parser.parse_args()

    print("=== ChromaDB Book Indexer ===")
    print(f"Files directory: {FILES_DIR}")
    print(f"ChromaDB path:   {CHROMA_DIR}\n")

    for folder, collection_name in FOLDER_TO_COLLECTION.items():
        print(f"[{folder}] -> {collection_name}")
        index_folder(folder, collection_name, reset=args.reset)
        print()

    print("Done!")


if __name__ == "__main__":
    main()
