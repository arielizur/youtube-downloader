FROM python:3.11-slim

# הגדרת תיקיית העבודה בתוך השרת
WORKDIR /app

# העתקת קובץ התלויות והתקנתן
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# התקנת הדפדפן של Playwright יחד עם תלויות מערכת ההפעלה שנדרשות לו
RUN playwright install --with-deps chromium

# העתקת שאר קבצי הפרויקט לשרת
COPY . .

# הגדרת פורט (בפלטפורמות ענן כמו Render לרוב מוגדר משתנה סביבה PORT)
ENV PORT=8000
EXPOSE $PORT

ENV PYTHONPATH=/app

# פקודת ההפעלה של השרת
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
