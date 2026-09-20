# Lab E-Log v0.1

A simple multi-user electronic lab log built with Python/Flask and SQLite.

## Requirements

Python 3.10+ recommended.

## Run locally

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the application:

```bash
python app.py
```

Open:

http://127.0.0.1:5000

The SQLite database `lab_elog.db` is created automatically.

## Current features

- Create lab log entries
- Author
- Date/time
- Log type
- Status
- Subsystem
- Equipment
- Tags
- Problem/objective
- Work performed
- Result
- Next action
- Full-text-like search across important fields
- Filter by author, type, and status
- View individual entries
- Edit entries

## Planned next steps

1. User login/authentication
2. Better search
3. File attachments
4. Comments
5. Equipment pages
6. Issue pages and linking
7. Audit/revision history
8. Database migration support for Oracle
9. University deployment
10. HTTPS and backups
