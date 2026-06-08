from . import agents as agents
from . import embedded as embedded

def init_routes(app):
    app.include_router(agents.router)
    app.include_router(embedded.router)

    return app