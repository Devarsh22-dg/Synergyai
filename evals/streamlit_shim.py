"""A minimal stand-in for the `streamlit` module so synergyai_app.py can be
imported and its AI functions called outside a real Streamlit run (e.g. from
the nightly eval harness or a test script). Every UI call becomes a no-op;
nothing here should ever be imported by the actual app.

Install it BEFORE importing synergyai_app:

    import sys
    from evals.streamlit_shim import shim
    sys.modules["streamlit"] = shim
    import synergyai_app  # noqa: E402
"""
import contextlib
import types


class _NoopContextManager:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def _noop(*args, **kwargs):
    return None


def _spinner(*args, **kwargs):
    return _NoopContextManager()


def _cache_resource(func=None, **kwargs):
    # Support both @st.cache_resource and @st.cache_resource(...)
    if func is not None:
        return func

    def decorator(f):
        return f

    return decorator


shim = types.ModuleType("streamlit")
shim.set_page_config = _noop
shim.error = _noop
shim.warning = _noop
shim.info = _noop
shim.success = _noop
shim.caption = _noop
shim.write = _noop
shim.markdown = _noop
shim.spinner = _spinner
shim.stop = lambda: (_ for _ in ()).throw(SystemExit("st.stop() called during eval run"))
shim.cache_resource = _cache_resource
shim.session_state = _SessionState()
shim.secrets = types.SimpleNamespace(get=lambda *a, **k: None)
