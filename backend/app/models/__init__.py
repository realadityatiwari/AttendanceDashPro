# Expose all models here so Alembic can easily import them via Base
from .user import User, Section, Subsection
from .admin_scope import AdminScope
from .academic import AcademicSession, Semester, Subject, StudentEnrollment, StudentElectiveChoice
from .timetable import TimetableEntry, ClassSession
from .occurrence import OccurrenceOutcome
from .attendance import AttendanceRecord
from .event import AcademicEvent
from .quiz import QuizCycle, EligibilityPolicy, QuizSchedule
from .laboratory import LaboratoryExperiment, LaboratoryRecord
from .feedback import Feedback
from .preference import UserPreference
from .notification import Notification
