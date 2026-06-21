class _FExpr:
    def startswith(self, *_args, **_kwargs):
        return self
    def __invert__(self):
        return self
    def __and__(self, _other):
        return self
    def __rand__(self, _other):
        return self
    def __eq__(self, _other):
        return self

class _F:
    def __getattr__(self, _name):
        return _FExpr()

F = _F()

class Router:
    def message(self, *_args, **_kwargs):
        def decorator(func):
            return func
        return decorator
    def callback_query(self, *_args, **_kwargs):
        def decorator(func):
            return func
        return decorator
