"""
Test all API connections
Run this to verify your setup is complete
"""
import os
import sys
from dotenv import load_dotenv

# Ensure UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

def test_neon():
    print("Testing Neon PostgreSQL...")
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"[OK] Neon connected: {version[:50]}...")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[FAIL] Neon failed: {e}")
        return False

def test_anthropic():
    print("\nTesting Anthropic API...")
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'API working'"}]
        )
        print(f"[OK] Anthropic connected: {message.content[0].text}")
        return True
    except Exception as e:
        print(f"[FAIL] Anthropic failed: {e}")
        return False

def test_openai():
    print("\nTesting OpenAI API...")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input="test"
        )
        dim = len(response.data[0].embedding)
        print(f"[OK] OpenAI connected: Embedding dimension {dim}")
        return True
    except Exception as e:
        print(f"[FAIL] OpenAI failed: {e}")
        return False

def test_chroma():
    print("\nTesting Chroma...")
    try:
        import chromadb
        client = chromadb.PersistentClient(path="./chroma_db")
        collection = client.get_or_create_collection("test")
        collection.add(documents=["test"], ids=["1"])
        results = collection.query(query_texts=["test"], n_results=1)
        print(f"[OK] Chroma connected: Retrieved {len(results['documents'][0])} docs")
        client.delete_collection("test")
        return True
    except Exception as e:
        print(f"[FAIL] Chroma failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing API Connections")
    print("=" * 60)

    # Install required packages first
    print("\nEnsure these packages are installed:")
    print("pip install psycopg2-binary anthropic openai chromadb python-dotenv")
    print()

    results = {
        "Neon": test_neon(),
        "Anthropic": test_anthropic(),
        "OpenAI": test_openai(),
        "Chroma": test_chroma()
    }

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for service, status in results.items():
        status_icon = "[OK]  " if status else "[FAIL]"
        print(f"{status_icon} {service}: {'Working' if status else 'Failed'}")

    all_passed = all(results.values())
    if all_passed:
        print("\n[SUCCESS] All services configured correctly! Ready to start development.")
    else:
        print("\n[WARNING] Some services failed. Check error messages above.")
