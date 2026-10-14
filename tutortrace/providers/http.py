"""Bounded JSON transport; no SDK dependency, redirects or error-body leaks."""

import json
import socket
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from tutortrace.providers.llm import InferenceError, InferenceTimeout, ModelUnavailable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, payload=None, *, timeout=120, api_key="", local=False):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = Request(url, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    handlers = [NoRedirect()]
    if local:
        handlers.append(ProxyHandler({}))
    try:
        with build_opener(*handlers).open(request, timeout=timeout) as response:
            data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise InferenceError("Provider response exceeded the size limit.")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise InferenceError("Provider returned an invalid response envelope.")
        return result
    except HTTPError as exc:
        if exc.code == 404:
            raise ModelUnavailable("Model or endpoint was not found. Check the configured model and URL.") from exc
        if exc.code in (401, 403):
            raise InferenceError("Provider authentication failed. Check the configured API credential.") from exc
        raise InferenceError(f"Inference service returned HTTP {exc.code}. No AI answer was produced.") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise InferenceTimeout("Inference timed out. Try a shorter context or a smaller available model.") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise InferenceTimeout("Inference timed out. Please retry when the provider is available.") from exc
        raise ModelUnavailable("Cannot reach inference. Start Ollama or check the provider connection.") from exc
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InferenceError("Provider returned malformed JSON.") from exc
    except (OSError, HTTPException) as exc:
        raise InferenceError("The inference connection failed. No AI answer was produced.") from exc
