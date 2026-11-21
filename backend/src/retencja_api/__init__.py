def main() -> None:
    import uvicorn

    uvicorn.run("retencja_api.api:app", host="0.0.0.0", port=8000)
