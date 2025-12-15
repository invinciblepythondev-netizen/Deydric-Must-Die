"""
Configuration management for Deydric Must Die

Loads environment variables and provides configuration classes for different environments.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration with common settings."""

    # Flask Core
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('NEON_DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Test connections before using them
        'pool_recycle': 3600,  # Recycle connections every hour (Neon timeout is typically 5-10 min idle)
        'pool_size': 10,
        'max_overflow': 20,
        'connect_args': {
            'connect_timeout': 10,  # 10 second connection timeout
            'keepalives': 1,  # Enable TCP keepalives
            'keepalives_idle': 30,  # Send keepalive after 30s idle
            'keepalives_interval': 10,  # Retry keepalive every 10s
            'keepalives_count': 5  # Retry 5 times before giving up
        }
    }

    # LLM Providers
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    AIMLAPI_API_KEY = os.getenv('AIMLAPI_API_KEY')
    TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')

    # Local Model Configuration
    LOCAL_MODEL_ENABLED = os.getenv('LOCAL_MODEL_ENABLED', 'false').lower() == 'true'
    LOCAL_MODEL_ENDPOINT = os.getenv('LOCAL_MODEL_ENDPOINT', 'http://localhost:11434')

    # Vector Database (Chroma)
    CHROMA_PERSIST_DIR = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
    CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
    CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))

    # Vector Database (Pinecone - optional)
    PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
    PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT', 'us-east-1-aws')
    PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME', 'deydric-memories')

    # Embeddings
    EMBEDDINGS_MODEL = os.getenv('EMBEDDINGS_MODEL', 'text-embedding-3-small')
    EMBEDDINGS_DIMENSION = int(os.getenv('EMBEDDINGS_DIMENSION', 1536))

    # LLM Model Configuration
    PRIMARY_LLM_PROVIDER = os.getenv('PRIMARY_LLM_PROVIDER', 'anthropic')
    PRIMARY_LLM_MODEL = os.getenv('PRIMARY_LLM_MODEL', 'claude-3-5-sonnet-20241022')
    SUMMARY_LLM_MODEL = os.getenv('SUMMARY_LLM_MODEL', 'claude-3-5-haiku-20241022')
    FALLBACK_LLM_PROVIDER = os.getenv('FALLBACK_LLM_PROVIDER', 'openai')
    FALLBACK_LLM_MODEL = os.getenv('FALLBACK_LLM_MODEL', 'gpt-4o-mini')

    # Game Configuration
    MAX_TURNS_WORKING_MEMORY = int(os.getenv('MAX_TURNS_WORKING_MEMORY', 10))
    SUMMARIZE_EVERY_N_TURNS = int(os.getenv('SUMMARIZE_EVERY_N_TURNS', 10))
    MAX_CONTEXT_TOKENS = int(os.getenv('MAX_CONTEXT_TOKENS', 15000))

    # Session Configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_FILE_DIR = './flask_session'

    @classmethod
    def validate_required_config(cls):
        """Validate that all required configuration is present."""
        required_vars = [
            ('SQLALCHEMY_DATABASE_URI', 'NEON_DATABASE_URL'),
            ('ANTHROPIC_API_KEY', 'ANTHROPIC_API_KEY'),
            ('OPENAI_API_KEY', 'OPENAI_API_KEY'),
        ]

        missing = []
        for attr, env_var in required_vars:
            if not getattr(cls, attr):
                missing.append(env_var)

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please check your .env file."
            )


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False

    # More verbose logging in development
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'false').lower() == 'true'


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False

    # Stricter session security in production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Production database settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 20,
        'max_overflow': 40
    }


class TestingConfig(Config):
    """Testing environment configuration."""
    DEBUG = True
    TESTING = True

    # Use a separate test database
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', Config.SQLALCHEMY_DATABASE_URI)

    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """
    Get configuration for the specified environment.

    Args:
        env (str): Environment name ('development', 'production', 'testing')
                   If None, uses FLASK_ENV environment variable or 'development'

    Returns:
        Config subclass
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')

    return config.get(env, config['default'])
