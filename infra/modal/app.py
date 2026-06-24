from __future__ import annotations

import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.115",
        "uvicorn>=0.30",
        "boto3>=1.34",
        "pydantic>=2.7",
        "pydantic-settings>=2.2",
        "PyYAML>=6.0",
        "genblaze",
        "genblaze-gmicloud",
        "genblaze-replicate",
    )
    .add_local_dir(".", remote_path="/app")
)

app = modal.App("crucible-api", image=image)


@app.function(
    secrets=[modal.Secret.from_name("crucible-secrets")],
    timeout=900,
)
@modal.asgi_app()
def fastapi_app():
    import sys

    sys.path.insert(0, "/app/packages/crucible-core/src")
    sys.path.insert(0, "/app/apps/api/src")

    from crucible_api.main import app as api

    return api
