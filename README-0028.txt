Patch 0028
- Fix unmatched ')' in /projects endpoint URL.
- Add missing imports (base64, hashlib) used by token decryption helper.
- Keeps 0026/0027 improvements (token discovery/decrypt + save-token endpoint).
Files:
- backend/app/api/jira.py
