from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    # Bind to loopback by default; set HOST=0.0.0.0 to expose externally.
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port)
