# Alternative zum Render-Blueprint: laeuft auf jeder Plattform, die ein
# Container-Image startet, und lokal mit
#   docker build -t eid-poll . && docker run -p 8731:8731 -e PORT=8731 eid-poll
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Die Plattform gibt den Port vor; 8731 ist nur der lokale Rueckfallwert.
ENV PORT=8731 \
    EIDPOLL_PUBLIC=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8731

CMD ["sh", "-c", "uvicorn web:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
