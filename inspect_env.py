"""
Reads .env, strips all hidden/non-ASCII characters from values, rewrites cleanly.
"""
import re

env_path = r"C:\Users\avivb\OneDrive\Desktop\CyberProAIProjects\pedagogical_assistant_ui\.env"

with open(env_path, 'rb') as f:
    raw = f.read()

print("Original file bytes (hex):", raw.hex())
print("Original file text:")
print(repr(raw.decode('utf-8', errors='replace')))
