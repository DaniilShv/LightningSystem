"""Сгенерировать API-ключ: python -m lighting.runtime.gen_key

Ключ вставляется в device/.env (API_KEY=...) и в настройки клиента.
"""

import secrets

if __name__ == "__main__":
    print(secrets.token_urlsafe(24))
