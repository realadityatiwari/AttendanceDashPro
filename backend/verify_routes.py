import sys
from app.main import app

def get_routes(app_or_router, prefix=""):
    routes = []
    # If it is an _IncludedRouter, recurse on original_router
    if hasattr(app_or_router, "original_router"):
        sub_prefix = prefix + getattr(app_or_router.include_context, "prefix", "")
        return get_routes(app_or_router.original_router, sub_prefix)

    for r in getattr(app_or_router, "routes", []):
        if hasattr(r, "methods") and hasattr(r, "path"):
            routes.append(f"{r.methods} {prefix}{r.path}")
        if type(r).__name__ == "_IncludedRouter":
            routes.extend(get_routes(r, prefix))
        elif hasattr(r, "app"):
            routes.extend(get_routes(r.app, prefix + getattr(r, "path", "")))
    return routes

routes = get_routes(app)

print("REGISTERED ROUTES:")
for route in routes:
    print(route)
