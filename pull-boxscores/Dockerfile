FROM python:3.12-alpine

COPY ./requirements.txt .
COPY ./pull_boxscores.py .

# RUN apk -U add chromium udev ttf-freefont
RUN pip install -r requirements.txt

CMD [ "python", "pull_boxscores.py" ]
