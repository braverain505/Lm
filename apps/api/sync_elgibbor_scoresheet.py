"""Apply El Gibbor's saved nursery scoresheet to the current term.

The school set nursery to 1st CA 15 / 2nd CA 15 / Exam 70, and the setting saved —
but the term's components never moved, because the term-wide lock saw Primary's
*published* results and refused to touch anything at all. With the lock now scoped
per section, re-applying the saved scoresheet syncs nursery and leaves primary
exactly as it is.

Idempotent: components are matched by key/name, so running it twice changes
nothing the second time.

    set -a; . ~/.clearis-prod.env; set +a
    ~/clearis/.venv/bin/python sync_elgibbor_scoresheet.py --dry-run
    ~/clearis/.venv/bin/python sync_elgibbor_scoresheet.py --yes
"""
from __future__ import annotations

import argparse

from sqlalchemy import select, text

from app.core.database import SessionLocal
from app.models import School
from app.services import results_service, sections_service

SCHOOL_NAME = "El Gibbor Academy"


def _components(db, school_id, term_id, *, section):
    from app.models import AssessmentComponent

    return list(
        db.scalars(
            select(AssessmentComponent)
            .where(
                AssessmentComponent.school_id == school_id,
                AssessmentComponent.term_id == term_id,
                AssessmentComponent.class_arm_id.is_(None),
                AssessmentComponent.section == section,
                AssessmentComponent.is_active.is_(True),
            )
            .order_by(AssessmentComponent.sort_order)
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply El Gibbor's saved scoresheet now.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.yes:
        parser.error("pass --dry-run or --yes")

    db = SessionLocal()
    try:
        db.execute(text("SET statement_timeout = '300s'"))
        school = db.scalar(select(School).where(School.name == SCHOOL_NAME))
        if school is None:
            raise SystemExit(f"{SCHOOL_NAME} not found.")

        saved = results_service.scoresheet_for(db, school.id)
        if saved is None:
            raise SystemExit("This school has never saved a scoresheet.")
        term = results_service._current_term(db, school.id)
        if term is None:
            raise SystemExit("No current term.")

        print(f"{school.name} — {term.name}")
        print("saved scoresheet:")
        print("  default:", [(r['name'], r['max_score']) for r in saved['default']])
        for section, rows in saved['sections'].items():
            if rows:
                print(f"  {section}:", [(r['name'], r['max_score']) for r in rows])

        before = {
            section: [(c.name, float(c.max_score)) for c in _components(db, school.id, term.id, section=section)]
            for section in (None, *sections_service.SECTIONS)
        }
        print("\ncomponents before:")
        for section, rows in before.items():
            print(f"  {section or 'school-wide':<12} {rows}")

        state = results_service.update_scoresheet(
            db,
            school.id,
            {
                "mode": sections_service.mode_for(db, school.id),
                "default": saved["default"],
                "sections": saved["sections"],
            },
        )

        after = {
            section: [(c.name, float(c.max_score)) for c in _components(db, school.id, term.id, section=section)]
            for section in (None, *sections_service.SECTIONS)
        }
        print("\ncomponents after:")
        for section, rows in after.items():
            changed = "  <-- changed" if rows != before[section] else ""
            print(f"  {section or 'school-wide':<12} {rows}{changed}")

        print(
            f"\nlocks: school-wide={state['locked_default']} "
            f"sections={state['locked_sections']}"
        )

        if args.dry_run:
            db.rollback()
            print("\nDry run — nothing was written.")
            return
        db.commit()
        print("\nDone.")
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()