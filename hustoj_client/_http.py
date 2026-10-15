"""HTTP helpers built on the standard library only.

The client intentionally has zero third-party dependencies: HUSTOJ is usually
served over plain HTTP on a campus network where pip access may be unavailable,
and a scanning/automation box often has no package index access at all.
"""
import re
import html
from urllib import request, parse, error
from http.cookiejar import CookieJar

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

#: Prefix of the marker string returned when a request fails.
FETCH_ERROR_PREFIX = "<!-- FETCH_ERROR: "


class FetchError(Exception):
    """Raised by fetch_or_raise when a request cannot be completed."""


def new_jar():
    """Return a fresh CookieJar.

    Note:
        http.cookiejar.CookieJar defines __len__, so an **empty jar is falsy**.
        Never write "cookie_jar or CookieJar()" -- it silently builds a new jar
        on every call and drops the session. Use
        "cookie_jar if cookie_jar is not None else CookieJar()" instead, which
        is exactly what fetch() does below.
    """
    return CookieJar()


def fetch(url, cookie_jar=None, data=None, headers=None, timeout=25, method=None):
    """Fetch a URL and return the body as text.

    Never raises for network problems: on failure it returns a string beginning
    with FETCH_ERROR_PREFIX, which the parsers treat simply as "no results".
    Use fetch_or_raise when you want an exception instead.

    Args:
        url: Absolute URL.
        cookie_jar: A CookieJar used to persist the session. A fresh jar is
            created when this is None (see new_jar for why the naive
            or-fallback is a bug).
        data: Dict or pre-encoded bytes. A dict is urlencoded and sent as POST.
        headers: Extra request headers merged over the defaults.
        timeout: Socket timeout in seconds.
        method: Force "GET" or "POST"; inferred from data otherwise.
    """
    h = {"User-Agent": DEFAULT_UA}
    if headers:
        h.update(headers)

    if isinstance(data, dict):
        data = parse.urlencode(data).encode()

    if method is None:
        method = "POST" if data is not None else "GET"

    jar = cookie_jar if cookie_jar is not None else CookieJar()
    opener = request.build_opener(request.HTTPCookieProcessor(jar))
    req = request.Request(url, data=data, headers=h, method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except error.URLError as e:
        return FETCH_ERROR_PREFIX + str(e) + " -->"
    except OSError as e:  # socket timeouts and friends
        return FETCH_ERROR_PREFIX + str(e) + " -->"


def fetch_or_raise(url, **kwargs):
    """Like fetch, but raise FetchError on failure."""
    body = fetch(url, **kwargs)
    if body.startswith(FETCH_ERROR_PREFIX):
        raise FetchError(body)
    return body


def strip_tags(text):
    """Drop script/style blocks and tags, unescape entities, squeeze blank lines.

    HUSTOJ renders problem statements inside Bootstrap panels; after extracting
    the inner HTML of a panel this turns it into plain text safe to print or
    store in JSON.
    """
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()
