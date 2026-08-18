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


def _print_error(msg="", *args, **kwargs):
    # The real st.error renders visibly in the app UI. In headless/eval mode
    # there's no UI, so without this, call_structured()'s "AI request failed"
    # messages vanish silently — which is exactly what made a real API
    # failure look like "0 fixtures evaluated, nothing to report" instead of
    # a visible error. Print instead of no-op so it shows up in the log.
    print(f"[st.error] {msg}")


def _spinner(*args, **kwargs):
    return _NoopContextManager()


def _cache_resource(func=None, **kwargs):
    # Support both @st.cache_resource and @st.cache_resource(...)
    if func is not None:
        return func

    def decorator(f):
        return f

    return decorator


class _Stub:
    """Fallback for any streamlit attribute we haven't explicitly shimmed
    above. Third-party packages (streamlit_authenticator's import chain, in
    particular) reference streamlit decorators like @st.cache_data at class
    -definition time, i.e. at IMPORT time, not just when actually run — so
    this has to survive being used as a decorator, with or without
    arguments, not just as a plain no-op function call."""

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and not kwargs and callable(args[0]):
            return args[0]  # used as @st.something directly on a function/class
        return self  # used as @st.something(...) -> the returned decorator


def _module_getattr(name):
    return _Stub()


shim = types.ModuleType("streamlit")
shim.set_page_config = _noop
shim.error = _print_error
shim.warning = _print_error
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

# streamlit_authenticator does `import streamlit.components.v1 as components` at its
# own module level, which needs a real submodule structure (not just attributes on a
# flat fake module) to resolve. auth.py only imports classes from it during a headless
# eval run — never instantiates/calls them — so a no-op stand-in is enough here.
_components_v1 = types.ModuleType("streamlit.components.v1")
_components_v1.html = _noop
_components_v1.declare_component = lambda *a, **k: _noop
_components = types.ModuleType("streamlit.components")
_components.v1 = _components_v1
shim.components = _components

shim.__getattr__ = _module_getattr  # PEP 562 — catches anything not explicitly defined above
