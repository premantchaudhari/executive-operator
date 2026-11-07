FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0
WORKDIR /app
RUN useradd --uid 10001 --create-home operator && mkdir /app/data && chown operator /app/data
COPY operator_app /app/operator_app
USER operator
EXPOSE 8080
CMD ["python", "-m", "operator_app.server"]
