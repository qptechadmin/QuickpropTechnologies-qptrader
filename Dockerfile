FROM python:3.9
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
#EXPOSE 5000
#CMD ["python", "app.py"]
EXPOSE 8000
CMD gunicorn --bind 0.0.0.0:8000 app:app


