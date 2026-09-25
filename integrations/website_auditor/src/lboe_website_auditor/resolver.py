"""Safe URL resolution with DNS and redirect SSRF checks."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from lboe_domain import WebsiteResolutionResult


class SSRFBlocked(ValueError):
    pass


def _blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or address in {"169.254.169.254", "100.100.100.200"}
    )


def validate_public_url(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SSRFBlocked("unsupported or invalid URL scheme")
    host = parsed.hostname.rstrip(".")
    if host.casefold() in {"localhost", "metadata.google.internal"}:
        raise SSRFBlocked("local or metadata host blocked")
    try:
        addresses = {
            str(item[4][0])
            for item in socket.getaddrinfo(
                host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
            )
        }
    except socket.gaierror as exc:
        raise SSRFBlocked("DNS resolution failed") from exc
    if not addresses or any(_blocked_ip(address) for address in addresses):
        raise SSRFBlocked("private or special-use address blocked")
    return parsed._replace(fragment="").geturl()


class WebsiteResolver:
    def __init__(self, timeout_seconds: float = 15.0, client: httpx.AsyncClient | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    async def resolve(self, url: str) -> WebsiteResolutionResult:
        checked_url = url
        redirects: list[str] = []
        try:
            current = validate_public_url(url)
        except SSRFBlocked as exc:
            return WebsiteResolutionResult(requested_url=url, status="blocked", error=str(exc))
        client = self.client or httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=False)
        close = self.client is None
        try:
            for _ in range(8):
                response = await client.get(current)
                checked_url = current
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        break
                    current = validate_public_url(urljoin(current, location))
                    redirects.append(current)
                    if current in redirects[:-1]:
                        return WebsiteResolutionResult(
                            requested_url=url, normalized_url=checked_url, status="redirect_loop", redirects=redirects
                        )
                    continue
                status = "healthy" if 200 <= response.status_code < 400 else "http_error"
                return WebsiteResolutionResult(
                    requested_url=url,
                    normalized_url=validate_public_url(url),
                    final_url=current,
                    http_status=response.status_code,
                    status=status,
                    redirects=redirects,
                )
            return WebsiteResolutionResult(
                requested_url=url, normalized_url=checked_url, status="redirect_loop", redirects=redirects
            )
        except SSRFBlocked as exc:
            return WebsiteResolutionResult(
                requested_url=url, normalized_url=checked_url, status="blocked", error=str(exc), redirects=redirects
            )
        except httpx.ConnectError as exc:
            message = str(exc).lower()
            return WebsiteResolutionResult(
                requested_url=url,
                normalized_url=checked_url,
                status="dns_failure"
                if "resolve" in message
                else ("tls_failure" if "ssl" in message or "certificate" in message else "unreachable"),
                error=type(exc).__name__,
                redirects=redirects,
            )
        except httpx.TimeoutException:
            return WebsiteResolutionResult(
                requested_url=url,
                normalized_url=checked_url,
                status="unreachable",
                error="timeout",
                redirects=redirects,
            )
        except httpx.TransportError as exc:
            return WebsiteResolutionResult(
                requested_url=url,
                normalized_url=checked_url,
                status="tls_failure" if "ssl" in str(exc).lower() else "unreachable",
                error=type(exc).__name__,
                redirects=redirects,
            )
        finally:
            if close:
                await client.aclose()
