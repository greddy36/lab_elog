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


class Equipment(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(150), nullable=False, unique=True)

log_equipment = db.Table(
	"log_equipment",
	db.Column("log_id", db.Integer, db.ForeignKey("log_entry.id"), primary_key=True),
	db.Column("equipment_id", db.Integer, db.ForeignKey("equipment.id"), primary_key=True),
)


class LogEntry(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String(250), nullable=False)
	log_type = db.Column(db.String(50), nullable=False, default="Work")
	subsystem = db.Column(db.String(100), nullable=True)
	status = db.Column(db.String(50), nullable=False, default="Open")

	description = db.Column(db.Text, nullable=True)
	work_performed = db.Column(db.Text, nullable=True)
	result = db.Column(db.Text, nullable=True)
	next_action = db.Column(db.Text, nullable=True)

	created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
	updated_at = db.Column(
		db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
	)

	author_id = db.Column(db.Integer, db.ForeignKey("author.id"), nullable=False)

	equipment = db.relationship("Equipment", secondary=log_equipment, lazy="subquery")


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


def get_or_create_equipment(equipment_string):
	equipment = []

	for raw in equipment_string.split(","):
		name = raw.strip()
		if not name:
			continue

		item = Equipment.query.filter_by(name=name).first()
		if not item:
			item = Equipment(name=name)
			db.session.add(item)
			db.session.flush()

		equipment.append(item)

	return equipment


# -----------------------------
# Routes
# -----------------------------

@app.route("/")
def index():
	query = request.args.get("q", "").strip()
	author_id = request.args.get("author", type=int)
	log_type = request.args.get("type", "").strip()
	status = request.args.get("status", "").strip()

	date_from = request.args.get("date_from", "").strip()
	date_to = request.args.get("date_to", "").strip()
	
	logs_query = LogEntry.query
	
	if query:
		pattern = f"%{query}%"
		logs_query = logs_query.join(Author).outerjoin(LogEntry.tags).filter(
			or_(
				LogEntry.title.ilike(pattern),
				LogEntry.description.ilike(pattern),
				LogEntry.work_performed.ilike(pattern),
				LogEntry.result.ilike(pattern),
				LogEntry.next_action.ilike(pattern),
				LogEntry.subsystem.ilike(pattern),
				Author.name.ilike(pattern),
			)
		).distinct()

	if author_id:
		logs_query = logs_query.filter(LogEntry.author_id == author_id)

	if log_type:
		logs_query = logs_query.filter(LogEntry.log_type == log_type)

	if status:
		logs_query = logs_query.filter(LogEntry.status == status)
	
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
		selected_status=status,
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
			status=request.form.get("status", "Open"),
			description=request.form.get("description", "").strip(),
			work_performed=request.form.get("work_performed", "").strip(),
			result=request.form.get("result", "").strip(),
			next_action=request.form.get("next_action", "").strip(),
			author=author,
		)

		if not entry.title:
			return render_template(
				"new_log.html",
				error="Title is required."
			)

		entry.equipment = get_or_create_equipment(
			request.form.get("equipment", "")
		)

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
		entry.status = request.form.get("status", "Open")
		entry.description = request.form.get("description", "").strip()
		entry.work_performed = request.form.get("work_performed", "").strip()
		entry.result = request.form.get("result", "").strip()
		entry.next_action = request.form.get("next_action", "").strip()
		entry.author = author

		entry.equipment = get_or_create_equipment(
			request.form.get("equipment", "")
		)

		db.session.commit()

		return redirect(url_for("view_log", log_id=entry.id))

	return render_template("edit_log.html", entry=entry, error=None)


# -----------------------------
# Startup
# -----------------------------

with app.app_context():
	db.create_all()


if __name__ == "__main__":
	app.run(host="127.0.0.1", port=5000, debug=True)
