# app/utils/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared limiter instance for all routers.
# Using one instance ensures rate-limit state is consistent and
# makes it trivial to switch to a Redis backend in the future.
limiter = Limiter(key_func=get_remote_address)
