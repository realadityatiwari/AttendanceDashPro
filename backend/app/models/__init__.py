# Expose all models here so Alembic can easily import them via Base
from .user import User, Section
from .academic import AcademicSession, Semester, Subject, StudentEnrollment
from .timetable import TimetableEntry, ClassSession
from .attendance import AttendanceRecord
from .event import AcademicEvent
from .quiz import QuizCycle, EligibilityPolicy, QuizSchedule
from .laboratory import LaboratoryExperiment, LaboratoryRecord
from .feedback import Feedback
from .preference import UserPreference
from .notification import Notification
