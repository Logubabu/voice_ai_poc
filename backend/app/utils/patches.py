import asyncio
from app.utils.logging import logger

def apply_aioice_patches():
    """Patches aioice and asyncio datagram transport to prevent closed-socket AttributeError tracebacks during WebRTC disconnects."""
    try:
        import aioice.stun
        if hasattr(aioice.stun.Transaction, "_Transaction__retry"):
            original_retry = aioice.stun.Transaction._Transaction__retry

            def safe_retry(self):
                try:
                    protocol = getattr(self, "_Transaction__protocol", None)
                    if protocol:
                        transport = getattr(protocol, "transport", None)
                        if transport is None or getattr(transport, "_sock", None) is None or getattr(transport, "_loop", None) is None:
                            return
                    original_retry(self)
                except (AttributeError, RuntimeError, OSError):
                    pass

            aioice.stun.Transaction._Transaction__retry = safe_retry
            logger.info("[PATCH] Patched aioice.stun.Transaction.__retry for safe socket teardown.")
    except Exception as e:
        logger.warning(f"[PATCH] Notice patching aioice: {e}")

    try:
        from asyncio.selector_events import _SelectorDatagramTransport
        original_fatal_error = _SelectorDatagramTransport._fatal_error

        def safe_fatal_error(self, exc, message='Fatal error on datagram transport'):
            if getattr(self, "_loop", None) is None or getattr(self, "_sock", None) is None:
                return
            try:
                original_fatal_error(self, exc, message)
            except (AttributeError, RuntimeError):
                pass

        _SelectorDatagramTransport._fatal_error = safe_fatal_error
        logger.info("[PATCH] Patched asyncio._SelectorDatagramTransport._fatal_error for safe loop shutdown.")
    except Exception as e:
        logger.warning(f"[PATCH] Notice patching asyncio datagram transport: {e}")

    try:
        from app.config import config
        if config.RTC_PORT_START and config.RTC_PORT_END:
            apply_aioice_port_range_patch(config.RTC_PORT_START, config.RTC_PORT_END)
    except Exception as e:
        logger.warning(f"[PATCH] Notice checking RTC port range: {e}")


def apply_aioice_port_range_patch(port_start: int = 50000, port_end: int = 50020):
    """Patches BaseEventLoop.create_datagram_endpoint in asyncio to bind UDP sockets within a specified port range for Docker/NAT."""
    try:
        import asyncio.base_events
        orig_create_datagram = asyncio.base_events.BaseEventLoop.create_datagram_endpoint

        # Avoid double patching
        if getattr(asyncio.base_events.BaseEventLoop, "_port_range_patched", False):
            return

        _next_port = port_start

        async def custom_create_datagram(self, protocol_factory, local_addr=None, **kwargs):
            nonlocal _next_port
            # When aioice asks for an ephemeral port (port 0), try the specified port range
            if local_addr and len(local_addr) == 2 and local_addr[1] == 0:
                total_ports = port_end - port_start + 1
                for _ in range(total_ports):
                    attempt_port = _next_port
                    _next_port = port_start if _next_port >= port_end else _next_port + 1
                    try:
                        return await orig_create_datagram(
                            self, protocol_factory, local_addr=(local_addr[0], attempt_port), **kwargs
                        )
                    except OSError:
                        continue
            return await orig_create_datagram(self, protocol_factory, local_addr=local_addr, **kwargs)

        asyncio.base_events.BaseEventLoop.create_datagram_endpoint = custom_create_datagram
        asyncio.base_events.BaseEventLoop._port_range_patched = True
        logger.info(f"[PATCH] Patched asyncio BaseEventLoop.create_datagram_endpoint to UDP port range {port_start}-{port_end}.")
    except Exception as e:
        logger.warning(f"[PATCH] Notice applying aioice port range patch: {e}")


def setup_asyncio_exception_handler():
    """Configures global asyncio exception handler to suppress closed STUN/UDP socket warnings."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    def handle_exception(loop, context):
        exception = context.get("exception")
        message = context.get("message", "")
        exc_str = str(exception) if exception else ""
        if isinstance(exception, AttributeError) and ("sendto" in exc_str or "call_exception_handler" in exc_str):
            # Suppress teardown race condition in closed STUN sockets
            return
        if "Transaction.__retry" in message or "sendto" in message:
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(handle_exception)
    logger.info("[PATCH] Global asyncio exception handler configured.")
