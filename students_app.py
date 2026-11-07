import csv
from pathlib import Path

from sqlalchemy import create_engine, String, Integer, select, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ---------- 1. Модель данных ----------

class Base(DeclarativeBase):
    pass


class StudentGrade(Base):
    """Запись таблицы students.csv: студент, факультет, курс и оценка."""
    __tablename__ = "student_grades"
    __table_args__ = (
        UniqueConstraint(
            "last_name", "first_name", "faculty", "course",
            name="uq_student_faculty_course"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    faculty: Mapped[str] = mapped_column(String(100), nullable=False)
    course: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (f"<StudentGrade {self.last_name} {self.first_name}, "
                f"{self.faculty}, {self.course}: {self.grade}>")


# ---------- 2. Класс операций INSERT и SELECT ----------

class StudentRepository:
    def __init__(self, db_url: str = "sqlite:///students.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)

    # --- INSERT ---
    def insert(self, record: dict) -> None:
        """Добавляет одну запись. Если студент уже проходил этот курс
        на этом факультете — обновляет оценку (чтобы избежать дублей)."""
        with Session(self.engine) as session:
            existing = session.execute(
                select(StudentGrade).where(
                    StudentGrade.last_name == record["last_name"],
                    StudentGrade.first_name == record["first_name"],
                    StudentGrade.faculty == record["faculty"],
                    StudentGrade.course == record["course"],
                )
            ).scalar_one_or_none()
            if existing:
                existing.grade = record["grade"]
            else:
                session.add(StudentGrade(**record))
            session.commit()

    def insert_many(self, records: list[dict]) -> None:
        for record in records:
            self.insert(record)

    # --- SELECT ---
    def select_all(self) -> list[StudentGrade]:
        with Session(self.engine) as session:
            return list(session.scalars(select(StudentGrade)))

    # ---------- 4. Методы для списков и статистики ----------

    def students_by_faculty(self, faculty: str) -> list[str]:
        """Список студентов (фамилия + имя) по названию факультета."""
        with Session(self.engine) as session:
            stmt = (
                select(StudentGrade.last_name, StudentGrade.first_name)
                .where(StudentGrade.faculty == faculty)
                .distinct()
                .order_by(StudentGrade.last_name, StudentGrade.first_name)
            )
            return [f"{ln} {fn}" for ln, fn in session.execute(stmt)]

    def unique_courses(self) -> list[str]:
        """Список уникальных курсов."""
        with Session(self.engine) as session:
            stmt = select(StudentGrade.course).distinct().order_by(StudentGrade.course)
            return list(session.scalars(stmt))

    def students_failing_course(self, course: str, threshold: int = 30) -> list[dict]:
        """Студенты по выбранному курсу с оценкой ниже threshold."""
        with Session(self.engine) as session:
            stmt = (
                select(StudentGrade.last_name, StudentGrade.first_name, StudentGrade.grade)
                .where(StudentGrade.course == course, StudentGrade.grade < threshold)
                .order_by(StudentGrade.grade)
            )
            return [
                {"last_name": ln, "first_name": fn, "grade": g}
                for ln, fn, g in session.execute(stmt)
            ]

    def average_grade_by_faculty(self, faculty: str) -> float | None:
        """Средний балл по факультету."""
        from sqlalchemy import func
        with Session(self.engine) as session:
            avg = session.scalar(
                select(func.avg(StudentGrade.grade))
                .where(StudentGrade.faculty == faculty)
            )
            return round(avg, 2) if avg is not None else None


# ---------- 3. Заполнение модели из students.csv ----------

def load_students_from_csv(repo: StudentRepository, path: str = "students.csv") -> None:
    """Читает CSV и вставляет записи в базу через репозиторий."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        records = [
            {
                "last_name": row["Фамилия"].strip(),
                "first_name": row["Имя"].strip(),
                "faculty": row["Факультет"].strip(),
                "course": row["Курс"].strip(),
                "grade": int(row["Оценка"]),
            }
            for row in reader
        ]
    repo.insert_many(records)
    print(f"Загружено строк: {len(records)}")


# ---------- Демонстрация ----------

if __name__ == "__main__":
    repo = StudentRepository()
    load_students_from_csv(repo, "students.csv")

    print("\nСтуденты АВТФ:", repo.students_by_faculty("АВТФ"))
    print("\nУникальные курсы:", repo.unique_courses())
    print("\nПровалившие Мат. Анализ (<30):",
          repo.students_failing_course("Мат. Анализ"))
    print("\nСредний балл по ФТФ:", repo.average_grade_by_faculty("ФТФ"))
