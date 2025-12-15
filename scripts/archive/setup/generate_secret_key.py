"""
Generate a secure secret key for Flask
Run this and copy the output to your .env file as FLASK_SECRET_KEY
"""
import secrets

print("=" * 60)
print("Flask Secret Key Generator")
print("=" * 60)
print("\nYour secure secret key:")
print(secrets.token_hex(32))
print("\nCopy this value to your .env file as FLASK_SECRET_KEY")
print("=" * 60)
