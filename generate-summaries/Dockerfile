FROM python:3.12-alpine

COPY ./requirements.txt .
COPY ./generate_summaries.py .

RUN pip install -r requirements.txt

CMD [ "python", "generate_summaries.py" ]
