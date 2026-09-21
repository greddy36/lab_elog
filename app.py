from flask import Flask, render_template, request, redirect, url_for, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, desc
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

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

class LogEntry(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(250), nullable=False)
	log_type = db.Column(db.String(50), nullable=False, default="Work")
	subsystem = db.Column(db.String(100), nullable=True)

	work_performed = db.Column(db.Text, nullable=True)
	result = db.Column(db.Text, nullable=True)

	created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
	updated_at = db.Column(
		db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
	)

	author_id = db.Column(db.Integer, db.ForeignKey("author.id"), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    text = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    author_id = db.Column(
        db.Integer,
        db.ForeignKey("author.id"),
        nullable=False
    )

    log_entry_id = db.Column(
        db.Integer,
        db.ForeignKey("log_entry.id"),
        nullable=False
    )
    # Attachment
    attachment_filename = db.Column(db.String(255), nullable=True)
    attachment_stored_filename = db.Column(db.String(255), nullable=True)
    
    author = db.relationship("Author")
    log_entry = db.relationship(
        "LogEntry",
        backref=db.backref(
            "comments",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

class Attachment(db.Model):
	id = db.Column(db.Integer, primary_key=True)

	filename = db.Column(db.String(255), nullable=False)
	stored_filename = db.Column(db.String(255), nullable=False)

	uploaded_at = db.Column(
		db.DateTime,
		default=datetime.utcnow,
		nullable=False
	)

	log_entry_id = db.Column(
		db.Integer,
		db.ForeignKey("log_entry.id"),
		nullable=False
	)

	log_entry = db.relationship(
		"LogEntry",
		backref=db.backref(
		    "attachments",
		    lazy=True,
		    cascade="all, delete-orphan"
		)
)

# -----------------------------
# Helpers
# -----------------------------

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

# -----------------------------
# Routes
# -----------------------------

@app.route("/")
def index():
	query = request.args.get("q", "").strip()
	author_id = request.args.get("author", type=int)
	log_type = request.args.get("type", "").strip()

	date_from = request.args.get("date_from", "").strip()
	date_to = request.args.get("date_to", "").strip()
	
	logs_query = LogEntry.query
	
	if query:
		pattern = f"%{query}%"

		logs_query = logs_query.join(Author).outerjoin(Comment).filter(
		    or_(
		        LogEntry.title.ilike(pattern),
		        LogEntry.work_performed.ilike(pattern),
		        LogEntry.result.ilike(pattern),
		        LogEntry.subsystem.ilike(pattern),
		        Author.name.ilike(pattern),
		        Comment.text.ilike(pattern),
		    )
		).distinct()

	if author_id:
		logs_query = logs_query.filter(LogEntry.author_id == author_id)

	if log_type:
		logs_query = logs_query.filter(LogEntry.log_type == log_type)

	# Date range filtering
	if date_from:
		start_date = datetime.strptime(date_from, "%Y-%m-%d")
		logs_query = logs_query.filter(LogEntry.created_at >= start_date)

	if date_to:
		# Include the entire "to" day
		end_date = datetime.strptime(date_to, "%Y-%m-%d")
		end_date = end_date.replace(hour=23, minute=59, second=59)
		logs_query = logs_query.filter(LogEntry.created_at <= end_date)

	logs = logs_query.order_by(desc(LogEntry.created_at)).all()

	authors = Author.query.order_by(Author.name).all()

	return render_template(
		"index.html",
		logs=logs,
		authors=authors,
		query=query,
		selected_author=author_id,
		selected_type=log_type,
		date_from=date_from,
		date_to=date_to,
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
			work_performed=request.form.get("work_performed", "").strip(),
			result=request.form.get("result", "").strip(),
			author=author,
		)

		if not entry.title:
			return render_template(
				"new_log.html",
				error="Title is required."
			)


		db.session.add(entry)
		db.session.commit()

		return redirect(url_for("view_log", log_id=entry.id))

	return render_template("new_log.html", error=None)


@app.route("/log/<int:log_id>")
def view_log(log_id):
    log = db.get_or_404(LogEntry, log_id)

    authors = Author.query.order_by(Author.name).all()

    return render_template(
        "view_log.html",
        log=log,
        authors=authors
    )

@app.route("/log/<int:log_id>/comment", methods=["POST"])
def add_comment(log_id):

    log = db.get_or_404(LogEntry, log_id)

    author_name = request.form.get("author_name", "").strip()
    text = request.form.get("text", "").strip()

    file = request.files.get("file")

    if not author_name or not text:
        return redirect(url_for("view_log", log_id=log_id))

    # Find existing author or create a new one
    author = Author.query.filter_by(name=author_name).first()

    if not author:
        author = Author(name=author_name)
        db.session.add(author)
        db.session.flush()

    # Create comment
    comment = Comment(
        text=text,
        author_id=author.id,
        log_entry_id=log.id
    )

    # Handle optional attachment
    if file and file.filename != "":

        original_filename = file.filename
        safe_filename = secure_filename(original_filename)

        stored_filename = f"{uuid.uuid4().hex}_{safe_filename}"

        # Store comment attachments inside the log's folder
        log_folder = os.path.join(
            UPLOAD_FOLDER,
            str(log_id)
        )

        os.makedirs(log_folder, exist_ok=True)

        file.save(
            os.path.join(
                log_folder,
                stored_filename
            )
        )

        comment.attachment_filename = original_filename
        comment.attachment_stored_filename = stored_filename

    db.session.add(comment)
    db.session.commit()

    return redirect(url_for("view_log", log_id=log_id))

UPLOAD_FOLDER = os.path.join(
os.path.dirname(os.path.abspath(__file__)),
"uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/log/<int:log_id>/attachment", methods=["POST"])
def upload_attachment(log_id):

	log = db.get_or_404(LogEntry, log_id)

	file = request.files.get("file")

	if not file or file.filename == "":
		return redirect(url_for("view_log", log_id=log_id))

	original_filename = file.filename
	safe_filename = secure_filename(original_filename)

	# Give the stored file a unique name
	stored_filename = f"{uuid.uuid4().hex}_{safe_filename}"

	# Keep attachments organized by log entry
	log_folder = os.path.join(
		UPLOAD_FOLDER,
		str(log_id)
	)

	os.makedirs(log_folder, exist_ok=True)

	file.save(
		os.path.join(log_folder, stored_filename)
	)

	attachment = Attachment(
		filename=original_filename,
		stored_filename=stored_filename,
		log_entry_id=log.id
	)

	db.session.add(attachment)
	db.session.commit()

	return redirect(url_for("view_log", log_id=log_id))

@app.route("/comment/<int:comment_id>/attachment")
def download_comment_attachment(comment_id):

    comment = db.get_or_404(Comment, comment_id)

    if not comment.attachment_stored_filename:
        return redirect(
            url_for("view_log", log_id=comment.log_entry_id)
        )

    directory = os.path.join(
        UPLOAD_FOLDER,
        str(comment.log_entry_id)
    )

    return send_from_directory(
        directory,
        comment.attachment_stored_filename,
        download_name=comment.attachment_filename
    )
# -----------------------------
# Startup
# -----------------------------

with app.app_context():
	db.create_all()


if __name__ == "__main__":
	app.run(host="127.0.0.1", port=5000, debug=True)
