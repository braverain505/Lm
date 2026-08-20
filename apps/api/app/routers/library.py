"""Library API endpoints: book catalogue and borrowings."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from ..core.deps import DbSession, require_permission
from ..core.permissions import LIBRARY_VIEW, LIBRARY_MANAGE
from ..schemas.library import (
    BookIn,
    BookOut,
    BorrowingIn,
    BorrowingOut,
    BorrowingReturnIn,
)
from ..services.library_service import (
    check_out,
    create_book,
    get_book,
    list_books,
    list_borrowings,
    mark_returned,
    update_book,
)


router = APIRouter(prefix="/library", tags=["library"])


# ──────────────────────────────────────────────────────────────────────
# Books
# ──────────────────────────────────────────────────────────────────────


@router.get("/books", response_model=list[BookOut])
def list_books_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(LIBRARY_VIEW)),
    available_only: bool = Query(False),
):
    return list_books(db, ctx.school.id, available_only=available_only)


@router.post("/books", response_model=BookOut, status_code=201)
def create_book_endpoint(
    payload: BookIn,
    db: DbSession,
    ctx=Depends(require_permission(LIBRARY_MANAGE)),
):
    book = create_book(db, ctx.school.id, data=payload)
    db.commit()
    return BookOut.model_validate(book)


@router.get("/books/{book_id}", response_model=BookOut)
def get_book_endpoint(
    book_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(LIBRARY_VIEW)),
):
    return BookOut.model_validate(get_book(db, book_id, ctx.school.id))


@router.put("/books/{book_id}", response_model=BookOut)
def update_book_endpoint(
    book_id: uuid.UUID,
    payload: BookIn,
    db: DbSession,
    ctx=Depends(require_permission(LIBRARY_MANAGE)),
):
    book = update_book(db, book_id, ctx.school.id, data=payload)
    db.commit()
    return BookOut.model_validate(book)


# ──────────────────────────────────────────────────────────────────────
# Borrowings
# ──────────────────────────────────────────────────────────────────────


@router.get("/borrowings", response_model=list[BorrowingOut])
def list_borrowings_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(LIBRARY_VIEW)),
    status: str | None = Query(None),
    overdue: bool = Query(False),
):
    return list_borrowings(
        db, ctx.school.id, status=status, overdue=overdue, today=date.today()
    )


@router.post("/borrowings", response_model=BorrowingOut, status_code=201)
def check_out_endpoint(
    payload: BorrowingIn,
    db: DbSession,
    ctx=Depends(require_permission(LIBRARY_MANAGE)),
):
    borrowing = check_out(db, ctx.school.id, data=payload, borrowed_on=date.today())
    db.commit()
    return borrowing


@router.post("/borrowings/{borrowing_id}/return", response_model=BorrowingOut)
def return_endpoint(
    borrowing_id: uuid.UUID,
    payload: BorrowingReturnIn,
    db: DbSession,
    ctx=Depends(require_permission(LIBRARY_MANAGE)),
):
    result = mark_returned(
        db,
        borrowing_id,
        ctx.school.id,
        returned_on=payload.returned_on or date.today(),
        notes=payload.notes,
    )
    db.commit()
    return result
