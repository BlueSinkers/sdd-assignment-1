# Teams microservice — Madrid Hoops Assignment 2
FROM python:3.12-slim

ENV PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser \
 && chown -R appuser:appuser /app

# Dependencies first so source edits do not bust the pip cache.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py db.py auth.py ./
COPY teams/ ./teams/
COPY migrations/ ./migrations/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "app.py"]
