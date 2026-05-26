def __getattr__(name):
    if name == "CartographerPlugin":
        from cartographer.plugin import CartographerPlugin
        return CartographerPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["CartographerPlugin"]
