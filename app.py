from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, desc
from datetime import datetime
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///lab_elog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# -----------------------------
# Database models
# -----------------------------

class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    email = db.Column(db.String(200), nullable=True)

    logs = db.relationship("LogEntry", backref="author", lazy=True)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)

log_tags = db.Table(
    "log_tags",
    db.Column("log_id", db.Integer, db.ForeignKey("log_entry.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)



class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    log_type = db.Column(db.String(50), nullable=False, default="Work")
    subsystem = db.Column(db.String(100), nullable=True)
    result = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    author_id = db.Column(db.Integer, db.ForeignKey("author.id"), nullable=False)

    tags = db.relationship("Tag", secondary=log_tags, lazy="subquery")


#----------------------Helpers------------------------------------------

def get_or_create_author(name):
    name = name.strip()
    if not name:
        return None

    author = Author.query.filter_by(name=name).first()
    if not author:
        author = Author(name=name)
        db.session.add(author)
        db.session.flush()
    return author


def get_or_create_tags(tag_string):
    tags = []

    for raw in tag_string.split(","):
        name = raw.strip()
        if not name:
            continue

        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()

        tags.append(tag)

    return tags


#-----------------Routes----------------------------

@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    author_id = request.args.get("author", type=int)
    log_type = request.args.get("type", "").strip()

    logs_query = LogEntry.query

    if query:
        pattern = f"%{query}%"
        logs_query = logs_query.join(Author).outerjoin(LogEntry.tags).filter(
            or_(
                LogEntry.title.ilike(pattern),
                LogEntry.result.ilike(pattern),
                LogEntry.subsystem.ilike(pattern),
                Author.name.ilike(pattern),
                Tag.name.ilike(pattern),
            )
        ).distinct()

    if author_id:
        logs_query = logs_query.filter(LogEntry.author_id == author_id)

    if log_type:
        logs_query = logs_query.filter(LogEntry.log_type == log_type)


    logs = logs_query.order_by(desc(LogEntry.created_at)).all()

    authors = Author.query.order_by(Author.name).all()

    return render_template(
        "index.html",
        logs=logs,
        authors=authors,
        query=query,
        selected_author=author_id,
        selected_type=log_type,
    )


@app.route("/new", methods=["GET", "POST"])
def new_log():
    if request.method == "POST":
        author_name = request.form.get("author", "").strip()

        if not author_name:
            return render_template(
                "new_log.html",
                error="Author is required."
            )

        author = get_or_create_author(author_name)

        entry = LogEntry(
            title=request.form.get("title", "").strip(),
            log_type=request.form.get("log_type", "Work"),
            subsystem=request.form.get("subsystem", "").strip(),
            result=request.form.get("result", "").strip(),
            author=author,
        )

        if not entry.title:
            return render_template(
                "new_log.html",
                error="Title is required."
            )

        entry.tags = get_or_create_tags(request.form.get("tags", ""))

        db.session.add(entry)
        db.session.commit()

        return redirect(url_for("view_log", log_id=entry.id))

    return render_template("new_log.html", error=None)


@app.route("/log/<int:log_id>")
def view_log(log_id):
    entry = db.session.get(LogEntry, log_id)

    if entry is None:
        abort(404)

    return render_template("view_log.html", entry=entry)


@app.route("/log/<int:log_id>/edit", methods=["GET", "POST"])
def edit_log(log_id):
    entry = db.session.get(LogEntry, log_id)

    if entry is None:
        abort(404)

    if request.method == "POST":
        author = get_or_create_author(request.form.get("author", ""))

        if not author:
            return render_template(
                "edit_log.html",
                entry=entry,
                error="Author is required."
            )

        entry.title = request.form.get("title", "").strip()
        entry.log_type = request.form.get("log_type", "Work")
        entry.subsystem = request.form.get("subsystem", "").strip()
        entry.result = request.form.get("result", "").strip()
        entry.author = author

        entry.tags = get_or_create_tags(request.form.get("tags", ""))

        db.session.commit()

        return redirect(url_for("view_log", log_id=entry.id))

    return render_template("edit_log.html", entry=entry, error=None)


#-----------Startup----------------------------------------

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
