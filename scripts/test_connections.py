"""
Test all service connections defined in .env

Checks:
1. PostgreSQL database (Neon)
2. Anthropic API (Claude)
3. OpenAI API
4. AIML API
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import psycopg2
import requests

# Load environment variables
load_dotenv()


def test_database():
    """Test PostgreSQL connection."""
    print("\n" + "="*70)
    print("DATABASE CONNECTION TEST (Neon PostgreSQL)")
    print("="*70)

    try:
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_name = os.getenv('DB_NAME')
        db_port = os.getenv('DB_PORT', '5432')

        print(f"Host: {db_host}")
        print(f"Database: {db_name}")
        print(f"User: {db_user}")
        print(f"Port: {db_port}")
        print("\nAttempting connection...")

        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port=db_port,
            sslmode='require',
            connect_timeout=10
        )

        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
        table_count = cursor.fetchone()[0]

        print(f"\n[SUCCESS] Connected successfully!")
        print(f"PostgreSQL version: {version[:50]}...")
        print(f"Tables in public schema: {table_count}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"\n[FAILED] Connection error: {str(e)}")
        return False


def test_anthropic():
    """Test Anthropic API connection."""
    print("\n" + "="*70)
    print("ANTHROPIC API TEST (Claude)")
    print("="*70)

    try:
        api_key = os.getenv('ANTHROPIC_API_KEY')

        if not api_key or api_key == 'sk-ant-...':
            print("[SKIPPED] API key not configured")
            return None

        print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
        print("\nAttempting API call...")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        data = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 10,
            "messages": [
                {"role": "user", "content": "Say 'test'"}
            ]
        }

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=15
        )

        if response.status_code == 200:
            result = response.json()
            content = result['content'][0]['text']
            print(f"\n[SUCCESS] API connection successful!")
            print(f"Model: {result['model']}")
            print(f"Response: {content}")
            return True
        else:
            print(f"\n[FAILED] API returned status {response.status_code}")
            print(f"Error: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n[FAILED] Connection error: {str(e)}")
        return False


def test_openai():
    """Test OpenAI API connection."""
    print("\n" + "="*70)
    print("OPENAI API TEST")
    print("="*70)

    try:
        api_key = os.getenv('OPENAI_API_KEY')

        if not api_key or api_key == 'sk-...':
            print("[SKIPPED] API key not configured")
            return None

        print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
        print("\nAttempting API call...")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "Say 'test'"}
            ],
            "max_tokens": 10
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"\n[SUCCESS] API connection successful!")
            print(f"Model: {result['model']}")
            print(f"Response: {content}")
            return True
        else:
            print(f"\n[FAILED] API returned status {response.status_code}")
            print(f"Error: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n[FAILED] Connection error: {str(e)}")
        return False


def test_aimlapi():
    """Test AIML API connection."""
    print("\n" + "="*70)
    print("AIML API TEST")
    print("="*70)

    try:
        api_key = os.getenv('AIMLAPI_API_KEY')

        if not api_key or api_key == 'your-aimlapi-key-here':
            print("[SKIPPED] API key not configured")
            return None

        print(f"API Key: {api_key[:16]}...{api_key[-8:]}")
        print("\nAttempting API call...")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "mistralai/Mistral-7B-Instruct-v0.2",
            "messages": [
                {"role": "user", "content": "Say 'test'"}
            ],
            "max_tokens": 10
        }

        response = requests.post(
            "https://api.aimlapi.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"\n[SUCCESS] API connection successful!")
            print(f"Model: {result['model']}")
            print(f"Response: {content}")
            return True
        else:
            print(f"\n[FAILED] API returned status {response.status_code}")
            print(f"Error: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n[FAILED] Connection error: {str(e)}")
        return False


def main():
    """Run all connection tests."""
    print("="*70)
    print("CONNECTION STATUS TEST")
    print("="*70)
    print("\nTesting all services defined in .env file...")

    results = {
        "Database (Neon PostgreSQL)": test_database(),
        "Anthropic API (Claude)": test_anthropic(),
        "OpenAI API": test_openai(),
        "AIML API": test_aimlapi()
    }

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    for service, status in results.items():
        if status is True:
            status_str = "[SUCCESS]"
        elif status is False:
            status_str = "[FAILED]"
        else:
            status_str = "[SKIPPED]"

        print(f"{status_str:12} {service}")

    print("\n" + "="*70)

    # Check Together.ai status
    together_key = os.getenv('TOGETHER_API_KEY')
    if not together_key or together_key == 'your-together-key-here':
        print("\nNOTE: Together.ai API key is not configured (commented out in .env)")

    successful = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    print(f"\nTotal: {successful} successful, {failed} failed, {skipped} skipped")
    print("="*70)


if __name__ == "__main__":
    main()
