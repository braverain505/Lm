"""Library service layer: books and borrowings."""

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import Book, Borrowing, Staff, Student
from ..schemas.library import BookIn, BorrowingIn


# --- Books --------------------------------------------------------------------------
def list_books(db: Session, school_id: uuid.UUID, *, available_only: bool = False) -> list[Book]:
    stmt = select(Book).where(Book.school_id == school_id)
    if available_only:
        stmt = stmt.where(Book.available_copies > 0)
    stmt = stmt.order_by(Book.title)
    return list(db.scalars(stmt))


def get_book(db: Session, book_id: uuid.UUID, school_id: uuid.UUID) -> Book:
    book = db.get(Book, book_id)
    if book is None or book.school_id != school_id:
        raise NotFoundError("Book not found")
    return book


def create_book(db: Session, school_id: uuid.UUID, *, data: BookIn) -> Book:
    if data.isbn:
        existing = db.scalar(
            select(Book).where(Book.school_id == school_id, Book.isbn == data.isbn)
        )
        if existing:
            raise ValidationError("A book with this ISBN already exists")
    book = Book(
        school_id=school_id,
        title=data.title,
        author=data.author,
        isbn=data.isbn,
        category=data.category,
        publisher=data.publisher,
        year=data.year,
        total_copies=data.total_copies,
        available_copies=data.total_copies,
        is_active=data.is_active,
    )
    db.add(book)
    db.flush()
    return book


def update_book(db: Session, book_id: uuid.UUID, school_id: uuid.UUID, *, data: BookIn) -> Book:
    book = get_book(db, book_id, school_id)
    if data.isbn:
        other = db.scalar(
            select(Book).where(
                Book.school_id == school_id, Book.isbn == data.isbn, Book.id != book_id
            )
        )
        if other:
            raise ValidationError("Another book with this ISBN already exists")

    delta_copies = data.total_copies - book.total_copies
    new_available = book.available_copies + delta_copies
    if new_available < 0:
        raise ValidationError(
            "Cannot reduce copies below the number currently on loan "
            f"({book.total_copies - book.available_copies} on loan)"
        )

    book.title = data.title
    book.author = data.author
    book.isbn = data.isbn
    book.category = data.category
    book.publisher = data.publisher
    book.year = data.year
    book.total_copies = data.total_copies
    book.available_copies = new_available
    book.is_active = data.is_active
    db.flush()
    return book


# --- Borrowings ---------------------------------------------------------------------
def _borrowing_dict(db: Session, school_id: uuid.UUID, b: Borrowing) -> dict:
    book_title = None
    book = db.get(Book, b.book_id)
    if book and book.school_id == school_id:
        book_title = book.title

    borrower_name = None
    if b.borrower_type == "student" and b.student_id:
        s = db.get(Student, b.student_id)
        if s and s.school_id == school_id:
            borrower_name = s.full_name
    elif b.borrower_type == "staff" and b.staff_id:
        st = db.get(Staff, b.staff_id)
        if st and st.school_id == school_id:
            borrower_name = st.full_name

    return {
        "id": b.id,
        "book_id": b.book_id,
        "borrower_type": b.borrower_type,
        "student_id": b.student_id,
        "staff_id": b.staff_id,
        "borrowed_on": b.borrowed_on,
        "due_on": b.due_on,
        "returned_on": b.returned_on,
        "status": b.status,
        "notes": b.notes,
        "created_at": b.created_at,
        "book_title": book_title,
        "borrower_name": borrower_name,
    }


def check_out(
    db: Session, school_id: uuid.UUID, *, data: BorrowingIn, borrowed_on: date
) -> dict:
    book = get_book(db, data.book_id, school_id)
    if not book.is_active:
        raise ValidationError("This book has been deactivated")
    if book.available_copies < 1:
        raise ValidationError("No copies of this book are currently available")

    if data.borrower_type == "student":
        if not data.student_id:
            raise ValidationError("student_id is required for student borrowings")
        s = db.get(Student, data.student_id)
        if s is None or s.school_id != school_id:
            raise NotFoundError("Student not found")
    elif data.borrower_type == "staff":
        if not data.staff_id:
            raise ValidationError("staff_id is required for staff borrowings")
        st = db.get(Staff, data.staff_id)
        if st is None or st.school_id != school_id:
            raise NotFoundError("Staff member not found")
    else:
        raise ValidationError("borrower_type must be 'student' or 'staff'")

    book.available_copies -= 1
    db.flush()

    borrowing = Borrowing(
        school_id=school_id,
        book_id=book.id,
        borrower_type=data.borrower_type,
        student_id=data.student_id,
        staff_id=data.staff_id,
        borrowed_on=borrowed_on,
        due_on=data.due_on,
        status="borrowed",
        notes=data.notes,
    )
    db.add(borrowing)
    db.flush()
    return _borrowing_dict(db, school_id, borrowing)


def mark_returned(
    db: Session,
    borrowing_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    returned_on: date,
    notes: str | None,
) -> dict:
    b = db.get(Borrowing, borrowing_id)
    if b is None or b.school_id != school_id:
        raise NotFoundError("Borrowing record not found")
    if b.status == "returned":
        raise ConflictError("This book has already been returned")

    book = db.get(Book, b.book_id)
    if book and book.school_id == school_id:
        book.available_copies += 1
        db.flush()

    b.status = "returned"
    b.returned_on = returned_on
    if notes:
        b.notes = notes
    db.flush()
    return _borrowing_dict(db, school_id, b)


def list_borrowings(
    db: Session,
    school_id: uuid.UUID,
    *,
    status: str | None = None,
    overdue: bool = False,
    today: date | None = None,
) -> list[dict]:
    stmt = select(Borrowing).where(Borrowing.school_id == school_id)
    if status:
        stmt = stmt.where(Borrowing.status == status)
    if overdue:
        today = today or date.today()
        stmt = stmt.where(
            Borrowing.status == "borrowed",
            Borrowing.due_on < today,
        )
    stmt = stmt.order_by(Borrowing.due_on)
    return [_borrowing_dict(db, school_id, b) for b in db.scalars(stmt)]